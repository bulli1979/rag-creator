from __future__ import annotations


class UnavailableVectorStore:
    """Platzhalter, wenn optionale Abhaengigkeiten fehlen (z. B. qdrant-client). API bleibt erreichbar."""

    def __init__(self, message: str) -> None:
        self._message = message

    def health_check(self) -> dict:
        return {"status": "error", "message": self._message}

    def ensure_schema(self, table_name: str) -> None:
        raise RuntimeError(self._message)

    def remove_document(self, table_name: str, doc_id: str) -> None:
        raise RuntimeError(self._message)

    def upsert_document_chunks(
        self,
        table_name: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        raise RuntimeError(self._message)

    def similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        raise RuntimeError(self._message)

    def search_by_filename(
        self,
        table_name: str,
        pattern: str,
        query_vector: list[float],
        top_k: int = 2,
    ) -> list[dict]:
        raise RuntimeError(self._message)
