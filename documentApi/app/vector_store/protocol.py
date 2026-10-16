from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    """Gemeinsames Interface für pgvector, SQLite embedded und Qdrant embedded."""

    def health_check(self) -> dict: ...

    def ensure_schema(self, table_name: str) -> None: ...

    def remove_document(self, table_name: str, doc_id: str) -> None: ...

    def remove_source(self, table_name: str, source_id: str) -> None: ...

    def replace_source_chunks(
        self,
        table_name: str,
        source_id: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None: ...

    def activate_source_version(
        self, table_name: str, source_id: str, doc_id: str
    ) -> None: ...

    def cleanup_inactive_versions(
        self, table_name: str, source_id: str | None = None
    ) -> int: ...

    def upsert_document_chunks(
        self,
        table_name: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None: ...

    def similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]: ...

    def search_by_filename(
        self,
        table_name: str,
        pattern: str,
        query_vector: list[float],
        top_k: int = 2,
    ) -> list[dict]:
        """Return up to top_k chunks whose fileName contains pattern (case-insensitive),
        ordered by vector similarity. Used to guarantee boosted sources appear in the
        reranking candidate pool even when their raw similarity rank is too low."""
        ...
