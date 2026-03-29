from __future__ import annotations

import json

from openai import OpenAI

from .config import (
    _DEFAULT_SETTINGS,
    load_chat_settings,
    load_settings,
    save_chat_settings as persist_chat_settings,
)
from .crypto_service import CryptoService
from .models import AppSettings, ChatMessage, ChatRequest, ChatResponse, ChatSettings
from .services.thread_pool import run_in_worker_pool
from .vector_service import PostgresVectorService
from .worker import embed_texts


class ChatService:
    def __init__(
        self,
        vector_service: PostgresVectorService,
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
        context_chunks = self._vs.similarity_search(
            table_name=active_pg.db_table_name,
            query_vector=query_vector,
            top_k=self._chat_settings.top_k,
        )

        context_text = "\n\n---\n\n".join(
            f"[{chunk['fileName']} | Chunk {chunk['chunkIndex']}]\n{chunk['text']}"
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
                "IMPORTANT: Always respond in German (Deutsch), regardless of document language."
            )
        elif preferred_language == "en":
            language_instruction = (
                "IMPORTANT: Always respond in English, regardless of document language."
            )
        else:
            language_instruction = (
                "IMPORTANT: Always respond in the same language the user writes in."
            )

        system_prompt = (
            f"{self._chat_settings.system_prompt}\n\n"
            f"{language_instruction}\n"
            "Use ONLY the following context to answer. "
            "If the context does not contain relevant information, say so.\n\n"
            f"--- CONTEXT ---\n{context_text}\n--- END CONTEXT ---"
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": query})

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
        except Exception as exc:
            answer = f"LLM-Anfrage fehlgeschlagen: {exc}"

        return ChatResponse(
            answer=answer,
            context_chunks=context_chunks,
            encrypted_payload=encrypted_payload,
        )
