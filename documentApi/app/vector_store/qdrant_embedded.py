from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

from ..file_store import create_sha256

_logger = logging.getLogger(__name__)


def _sanitize_collection(name: str) -> str:
    # Qdrant: Buchstaben, Zahlen, Unterstrich
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{0,254}$", name):
        raise ValueError(f"Ungueltiger Collection-Name: {name}")
    return name


class QdrantEmbeddedVectorStore:
    """Qdrant im eingebetteten Modus (lokales Verzeichnis, kein separater Qdrant-Server)."""

    def __init__(self, storage_path: Path) -> None:
        self._storage_path = Path(storage_path)
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError as exc:
            raise ImportError(
                "qdrant-client nicht installiert. Bitte pip install qdrant-client ausfuehren."
            ) from exc

        self._storage_path.mkdir(parents=True, exist_ok=True)
        # Gleicher Prozess / Threads; bei uvicorn --reload koennen zwei Worker kurz ueberlappen (siehe run-document-api.mjs).
        self._client = QdrantClient(
            path=str(self._storage_path),
            force_disable_check_same_thread=True,
        )
        self._Distance = Distance
        self._VectorParams = VectorParams

    def health_check(self) -> dict:
        try:
            _ = self._client.get_collections()
            return {"status": "ok", "message": f"Qdrant embedded OK ({self._storage_path})."}
        except Exception as exc:
            return {"status": "error", "message": f"Qdrant embedded Fehler: {exc}"}

    def ensure_schema(self, table_name: str) -> None:
        name = _sanitize_collection(table_name)
        cols = self._client.get_collections().collections
        if any(c.name == name for c in cols):
            return
        # Default-Dimension wie all-MiniLM-L6-v2; bei anderem Modell Collection/Tabelle wechseln.
        self._client.create_collection(
            collection_name=name,
            vectors_config=self._VectorParams(size=384, distance=self._Distance.COSINE),
        )

    def remove_document(self, table_name: str, doc_id: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        name = _sanitize_collection(table_name)
        ids_to_delete: list = []
        offset = None
        while True:
            points, offset = self._client.scroll(
                collection_name=name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]
                ),
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            if not points:
                break
            ids_to_delete.extend([p.id for p in points])
            if offset is None:
                break
        if not ids_to_delete:
            return
        self._client.delete(collection_name=name, points_selector=ids_to_delete)

    def upsert_document_chunks(
        self,
        table_name: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        from qdrant_client.models import PointStruct

        if len(vectors) != len(payloads):
            raise ValueError("Anzahl von Vektoren und Payloads muss identisch sein.")
        name = _sanitize_collection(table_name)
        dim = len(vectors[0])
        cols = self._client.get_collections().collections
        if not any(c.name == name for c in cols):
            self._client.create_collection(
                collection_name=name,
                vectors_config=self._VectorParams(size=dim, distance=self._Distance.COSINE),
            )

        points = []
        for vector, payload in zip(vectors, payloads):
            chunk_ix = int(payload["chunkIndex"])
            point_key = create_sha256(f"{doc_id}:{chunk_ix}")
            pid = str(uuid.uuid5(uuid.NAMESPACE_URL, point_key))
            points.append(
                PointStruct(
                    id=pid,
                    vector=vector,
                    payload={
                        "text_content": payload["text"],
                        "document_id": payload["documentId"],
                        "file_name": payload["fileName"],
                        "chunk_index": chunk_ix,
                        "source_path": payload["sourcePath"],
                        "source": payload["source"],
                        "tags": json.dumps(payload["tags"]),
                        "source_modified_unix_seconds": int(payload["sourceModifiedUnixSeconds"]),
                    },
                )
            )
        self._client.upsert(collection_name=name, points=points)
        _logger.info("qdrant upsert fertig: doc_id=%s… points=%s", doc_id[:16], len(points))

    def similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        name = _sanitize_collection(table_name)
        # qdrant-client >= 1.7: kein .search() mehr auf QdrantClient; Vektorsuche ueber query_points()
        resp = self._client.query_points(
            collection_name=name,
            query=query_vector,
            limit=max(1, top_k),
            with_payload=True,
        )
        hits = getattr(resp, "points", None) or []
        out: list[dict] = []
        for h in hits:
            raw = getattr(h, "payload", None) or {}
            p = dict(raw) if not isinstance(raw, dict) else raw
            score = getattr(h, "score", None)
            out.append(
                {
                    "text": p.get("text_content", ""),
                    "documentId": p.get("document_id", ""),
                    "fileName": p.get("file_name", ""),
                    "chunkIndex": int(p.get("chunk_index", 0)),
                    "sourcePath": p.get("source_path", ""),
                    "source": p.get("source", ""),
                    "similarity": float(score) if score is not None else 0.0,
                }
            )
        return out

    def search_by_filename(
        self,
        table_name: str,
        pattern: str,
        query_vector: list[float],
        top_k: int = 2,
    ) -> list[dict]:
        """Return top_k chunks whose file_name contains pattern (case-insensitive), ordered by similarity."""
        from qdrant_client.models import Filter, FieldCondition, MatchText
        name = _sanitize_collection(table_name)
        try:
            resp = self._client.query_points(
                collection_name=name,
                query=query_vector,
                query_filter=Filter(must=[FieldCondition(key="file_name", match=MatchText(text=pattern))]),
                limit=max(1, top_k),
                with_payload=True,
            )
            hits = getattr(resp, "points", None) or []
        except Exception:
            return []
        out: list[dict] = []
        for h in hits:
            raw = getattr(h, "payload", None) or {}
            p = dict(raw) if not isinstance(raw, dict) else raw
            score = getattr(h, "score", None)
            if pattern.lower() not in str(p.get("file_name", "")).lower():
                continue
            out.append(
                {
                    "text": p.get("text_content", ""),
                    "documentId": p.get("document_id", ""),
                    "fileName": p.get("file_name", ""),
                    "chunkIndex": int(p.get("chunk_index", 0)),
                    "sourcePath": p.get("source_path", ""),
                    "source": p.get("source", ""),
                    "similarity": float(score) if score is not None else 0.0,
                }
            )
        return out
