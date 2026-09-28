from __future__ import annotations

import json
import re
import time
import uuid

from openai import OpenAI

from .config import (
    _DEFAULT_SETTINGS,
    load_chat_settings,
    save_chat_settings as persist_chat_settings,
)
from .crypto_service import CryptoService
from .database import IndexDatabase
from .models import (
    AppSettings,
    ChatFeedbackRecord,
    ChatFeedbackRequest,
    ChatRequest,
    ChatRequestRecord,
    ChatResponse,
    ChatSettings,
)
from .services.thread_pool import run_in_worker_pool
from .vector_store.protocol import VectorStore
from .worker import embed_texts


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-/\.]+")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
_LOG_ANSWER_MAX = 16000
_LOG_COMMENT_MAX = 4000


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text or ""))


def _normalize_rerank_weights(
    similarity: float,
    lexical: float,
    numeric: float,
) -> tuple[float, float, float]:
    """Normalize non-negative weights so they sum to 1. Fallback: similarity-only."""
    w_sim = max(0.0, float(similarity))
    w_lex = max(0.0, float(lexical))
    w_num = max(0.0, float(numeric))
    total = w_sim + w_lex + w_num
    if total <= 0.0:
        return 1.0, 0.0, 0.0
    return w_sim / total, w_lex / total, w_num / total


def _rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int,
    *,
    similarity_weight: float = 0.90,
    lexical_weight: float = 0.05,
    numeric_weight: float = 0.05,
) -> list[dict]:
    """Blend vector similarity with optional lexical/numeric signals (weights from ChatSettings)."""
    if not chunks:
        return []

    w_sim, w_lex, w_num = _normalize_rerank_weights(
        similarity_weight, lexical_weight, numeric_weight
    )
    q_tokens = _tokenize(query) if w_lex > 0.0 else set()
    q_numbers = _extract_numbers(query) if w_num > 0.0 else set()

    scored: list[tuple[float, dict]] = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        sim = float(chunk.get("similarity", 0.0) or 0.0)
        lexical = 0.0
        numeric = 0.0
        if w_lex > 0.0 and q_tokens:
            c_tokens = _tokenize(text)
            lexical = len(q_tokens & c_tokens) / len(q_tokens)
        if w_num > 0.0 and q_numbers:
            c_numbers = _extract_numbers(text)
            numeric = len(q_numbers & c_numbers) / len(q_numbers)

        score = (w_sim * sim) + (w_lex * lexical) + (w_num * numeric)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[: max(1, top_k)]]


def _trim_context_text(text: str, max_chars: int = 1200) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


def _truncate_text(text: str | None, max_chars: int) -> str | None:
    if text is None:
        return None
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


def _summarize_chunks(chunks: list[dict]) -> list[dict]:
    return [
        {
            "fileName": chunk.get("fileName"),
            "chunkIndex": chunk.get("chunkIndex"),
            "documentId": chunk.get("documentId"),
            "similarity": chunk.get("similarity"),
        }
        for chunk in chunks
    ]


class ChatService:
    def __init__(
        self,
        vector_service: VectorStore,
        crypto_service: CryptoService,
        database: IndexDatabase,
    ) -> None:
        self._vs = vector_service
        self._crypto = crypto_service
        self._db = database
        self._settings: AppSettings = _DEFAULT_SETTINGS.model_copy(deep=True)
        self._chat_settings = load_chat_settings()

    def update_settings(self, app_settings: AppSettings) -> None:
        self._settings = app_settings

    def get_settings(self) -> AppSettings:
        return self._settings

    def set_vector_store(self, vector_service: VectorStore) -> None:
        """Muss nach IngestService._rebuild_vector_store() aufgerufen werden (gleiche DB-Datei / gleicher Store)."""
        self._vs = vector_service

    def get_chat_settings(self) -> ChatSettings:
        return self._chat_settings

    def update_chat_settings(self, chat_settings: ChatSettings) -> None:
        self._chat_settings = persist_chat_settings(chat_settings)

    def list_chat_requests(
        self,
        *,
        environment_id: str | None = None,
        limit: int = 100,
    ) -> list[ChatRequestRecord]:
        return self._db.list_chat_requests(environment_id=environment_id, limit=limit)

    def submit_feedback(
        self,
        request_id: str,
        feedback: ChatFeedbackRequest,
    ) -> ChatFeedbackRecord:
        existing = self._db.get_chat_request(request_id)
        if existing is None:
            raise LookupError(f"Chat-Anfrage {request_id} nicht gefunden.")
        comment = _truncate_text(feedback.comment, _LOG_COMMENT_MAX)
        return self._db.upsert_chat_feedback(
            feedback_id=str(uuid.uuid4()),
            request_id=request_id,
            helpful=feedback.helpful,
            rating=feedback.rating,
            comment=comment,
        )

    def _log_chat_request(
        self,
        *,
        request_id: str,
        request: ChatRequest,
        history: list,
        answer: str,
        context_chunks: list[dict],
        metrics: dict[str, float | int],
        status: str,
        error_message: str | None,
        elapsed_ms: int,
    ) -> None:
        active_env = self._settings.get_active_postgres()
        self._db.insert_chat_request(
            request_id=request_id,
            environment_id=active_env.environment_id,
            message=_truncate_text(request.message, _LOG_ANSWER_MAX) or "",
            history_json=json.dumps(
                [msg.model_dump(by_alias=True) for msg in history],
                ensure_ascii=False,
            ),
            language=request.language,
            answer=_truncate_text(answer, _LOG_ANSWER_MAX),
            context_summary_json=json.dumps(
                _summarize_chunks(context_chunks),
                ensure_ascii=False,
            ),
            metrics_json=json.dumps(metrics, ensure_ascii=False),
            llm_model=self._chat_settings.llm_model,
            top_k=self._chat_settings.top_k,
            client_source=(request.client_source or "").strip() or None,
            status=status,
            error_message=error_message,
            elapsed_ms=elapsed_ms,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        query = request.message
        history = request.history or []
        preferred_language = request.language

        query_embedding = await run_in_worker_pool(
            embed_texts, self._settings.embedding_model, [query]
        )
        if not query_embedding.get("ok") or not query_embedding.get("vectors"):
            elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
            answer = "Embedding der Anfrage fehlgeschlagen."
            metrics: dict[str, float | int] = {"elapsedMs": elapsed_ms}
            self._log_chat_request(
                request_id=request_id,
                request=request,
                history=history,
                answer=answer,
                context_chunks=[],
                metrics=metrics,
                status="error",
                error_message="embedding_failed",
                elapsed_ms=elapsed_ms,
            )
            return ChatResponse(
                answer=answer,
                context_chunks=[],
                encrypted_payload="",
                metrics=metrics,
                request_id=request_id,
            )

        query_vector = query_embedding["vectors"][0]

        active_pg = self._settings.get_active_postgres()
        configured_candidate = self._chat_settings.retrieval_candidate_k
        if configured_candidate is not None and int(configured_candidate) > 0:
            candidate_k = max(int(self._chat_settings.top_k), int(configured_candidate))
        else:
            candidate_k = max(self._chat_settings.top_k, min(self._chat_settings.top_k * 4, 30))
        candidate_chunks = self._vs.similarity_search(
            table_name=active_pg.db_table_name,
            query_vector=query_vector,
            top_k=candidate_k,
        )
        context_chunks = _rerank_chunks(
            query=query,
            chunks=candidate_chunks,
            top_k=self._chat_settings.top_k,
            similarity_weight=self._chat_settings.rerank_similarity_weight,
            lexical_weight=self._chat_settings.rerank_lexical_weight,
            numeric_weight=self._chat_settings.rerank_numeric_weight,
        )

        context_text = "\n\n---\n\n".join(
            f"[{chunk['fileName']} | Chunk {chunk['chunkIndex']}]\n{_trim_context_text(chunk['text'])}"
            for chunk in context_chunks
        )

        encrypted_payload = self._crypto.encrypt_json(
            {
                "query": query,
                "context_chunks": context_chunks,
                "history": [msg.model_dump(by_alias=True) for msg in history],
            }
        )

        if preferred_language == "de":
            language_instruction = (
                "MANDATORY OUTPUT LANGUAGE: German (Deutsch). "
                "Your entire final answer MUST be in German only."
            )
            language_user_suffix = "WICHTIG: Antworte ausschliesslich auf Deutsch."
        elif preferred_language == "en":
            language_instruction = (
                "MANDATORY OUTPUT LANGUAGE: English. "
                "Your entire final answer MUST be in English only."
            )
            language_user_suffix = "IMPORTANT: Reply strictly in English only."
        else:
            language_instruction = (
                "IMPORTANT: Always respond in the same language the user writes in."
            )
            language_user_suffix = ""

        system_prompt = (
            f"{self._chat_settings.system_prompt}\n\n"
            f"{language_instruction}\n"
            "Use ONLY the following context to answer. "
            "If the context does not contain relevant information, say so explicitly.\n"
            "For factual questions (numbers, commands, limits), prefer exact values from context and cite the chunk/file names.\n"
            "If context snippets disagree, mention the conflict instead of guessing.\n\n"
            f"--- CONTEXT ---\n{context_text}\n--- END CONTEXT ---"
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        user_content = query if not language_user_suffix else f"{query}\n\n{language_user_suffix}"
        messages.append({"role": "user", "content": user_content})

        error_message: str | None = None
        try:
            client = OpenAI(
                api_key=self._chat_settings.llm_api_key,
                base_url=self._chat_settings.llm_base_url or None,
            )
            completion = await run_in_worker_pool(
                client.chat.completions.create,
                model=self._chat_settings.llm_model,
                messages=messages,
                temperature=self._chat_settings.temperature,
                max_tokens=self._chat_settings.max_tokens,
            )
            answer = completion.choices[0].message.content or ""
            usage = getattr(completion, "usage", None)
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
        except Exception as exc:
            answer = f"LLM-Anfrage fehlgeschlagen: {exc}"
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            error_message = str(exc)

        elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
        tokens_per_second = (
            round((completion_tokens / (elapsed_ms / 1000.0)), 2)
            if completion_tokens > 0
            else 0.0
        )
        metrics = {
            "elapsedMs": elapsed_ms,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
            "tokensPerSecond": tokens_per_second,
        }
        status = "error" if error_message else "ok"

        self._log_chat_request(
            request_id=request_id,
            request=request,
            history=history,
            answer=answer,
            context_chunks=context_chunks,
            metrics=metrics,
            status=status,
            error_message=error_message,
            elapsed_ms=elapsed_ms,
        )

        return ChatResponse(
            answer=answer,
            context_chunks=context_chunks,
            encrypted_payload=encrypted_payload,
            metrics=metrics,
            request_id=request_id,
        )
