from __future__ import annotations

import re
import time

from openai import OpenAI

from .config import (
    _DEFAULT_SETTINGS,
    load_chat_settings,
    save_chat_settings as persist_chat_settings,
)
from .crypto_service import CryptoService
from .models import AppSettings, ChatRequest, ChatResponse, ChatSettings
from .services.thread_pool import run_in_worker_pool
from .vector_store.protocol import VectorStore
from .worker import embed_texts


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_\-/\.]+")
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 1}


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text or ""))


def _rerank_chunks(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Blend vector similarity with lexical and numeric matching for higher QA precision."""
    if not chunks:
        return []

    q_tokens = _tokenize(query)
    q_numbers = _extract_numbers(query)

    scored: list[tuple[float, dict]] = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        c_tokens = _tokenize(text)
        c_numbers = _extract_numbers(text)

        sim = float(chunk.get("similarity", 0.0) or 0.0)
        lexical = (len(q_tokens & c_tokens) / len(q_tokens)) if q_tokens else 0.0
        numeric = (len(q_numbers & c_numbers) / len(q_numbers)) if q_numbers else 0.0

        # Prioritize semantic match, but boost exact lexical and numeric overlap.
        score = (0.65 * sim) + (0.25 * lexical) + (0.10 * numeric)
        scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[: max(1, top_k)]]


def _trim_context_text(text: str, max_chars: int = 1200) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3] + "..."


class ChatService:
    def __init__(
        self,
        vector_service: VectorStore,
        crypto_service: CryptoService,
    ) -> None:
        self._vs = vector_service
        self._crypto = crypto_service
        self._settings: AppSettings = _DEFAULT_SETTINGS.model_copy(deep=True)
        self._chat_settings = load_chat_settings()

    def update_settings(self, app_settings: AppSettings) -> None:
        self._settings = app_settings

    def get_chat_settings(self) -> ChatSettings:
        return self._chat_settings

    def update_chat_settings(self, chat_settings: ChatSettings) -> None:
        self._chat_settings = persist_chat_settings(chat_settings)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started_at = time.perf_counter()
        query = request.message
        history = request.history or []
        preferred_language = request.language

        query_embedding = await run_in_worker_pool(
            embed_texts, self._settings.embedding_model, [query]
        )
        if not query_embedding.get("ok") or not query_embedding.get("vectors"):
            return ChatResponse(
                answer="Embedding der Anfrage fehlgeschlagen.",
                context_chunks=[],
                encrypted_payload="",
            )

        query_vector = query_embedding["vectors"][0]

        active_pg = self._settings.get_active_postgres()
        # Retrieve a wider candidate pool, then rerank for QA precision.
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

        elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
        tokens_per_second = (
            round((completion_tokens / (elapsed_ms / 1000.0)), 2)
            if completion_tokens > 0
            else 0.0
        )

        return ChatResponse(
            answer=answer,
            context_chunks=context_chunks,
            encrypted_payload=encrypted_payload,
            metrics={
                "elapsedMs": elapsed_ms,
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "totalTokens": total_tokens,
                "tokensPerSecond": tokens_per_second,
            },
        )