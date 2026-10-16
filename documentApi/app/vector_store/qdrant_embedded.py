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
            self._migrate_legacy_payloads(name)
            return
        # Default-Dimension wie all-MiniLM-L6-v2; bei anderem Modell Collection/Tabelle wechseln.
        self._client.create_collection(
            collection_name=name,
            vectors_config=self._VectorParams(size=384, distance=self._Distance.COSINE),
        )

    def _migrate_legacy_payloads(self, name: str) -> None:
        offset = None
        while True:
            points, offset = self._client.scroll(
                collection_name=name, limit=256, offset=offset,
                with_payload=True, with_vectors=False,
            )
            for point in points:
                payload = dict(point.payload or {})
                document_id = str(payload.get("document_id", ""))
                additions = {}
                if "source_id" not in payload:
                    additions["source_id"] = document_id
                if "content_hash" not in payload:
                    additions["content_hash"] = document_id
                if "version" not in payload:
                    additions["version"] = 1
                if "is_active" not in payload:
                    additions["is_active"] = True
                if "canonical_location" not in payload:
                    additions["canonical_location"] = ""
                if "corpus_version" not in payload:
                    additions["corpus_version"] = ""
                if "category" not in payload:
                    additions["category"] = ""
                if "instrument" not in payload:
                    additions["instrument"] = ""
                if "authority" not in payload:
                    additions["authority"] = "unclassified"
                if "document_status" not in payload:
                    additions["document_status"] = "active"
                if "section" not in payload:
                    additions["section"] = ""
                if "heading_path" not in payload:
                    additions["heading_path"] = []
                if "parent_section" not in payload:
                    additions["parent_section"] = ""
                if "previous_section" not in payload:
                    additions["previous_section"] = ""
                if "next_section" not in payload:
                    additions["next_section"] = ""
                if "content_types" not in payload:
                    additions["content_types"] = []
                if additions:
                    self._client.set_payload(
                        collection_name=name, payload=additions, points=[point.id]
                    )
            if offset is None:
                return

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

    def _matching_ids(self, table_name: str, conditions: list) -> list:
        from qdrant_client.models import Filter

        ids: list = []
        offset = None
        while True:
            points, offset = self._client.scroll(
                collection_name=_sanitize_collection(table_name),
                scroll_filter=Filter(must=conditions),
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            ids.extend(p.id for p in points)
            if offset is None:
                return ids

    def remove_source(self, table_name: str, source_id: str) -> None:
        from qdrant_client.models import FieldCondition, MatchValue

        ids = self._matching_ids(
            table_name, [FieldCondition(key="source_id", match=MatchValue(value=source_id))]
        )
        if ids:
            self._client.delete(collection_name=_sanitize_collection(table_name), points_selector=ids)

    def upsert_document_chunks(
        self,
        table_name: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        source_id = str(payloads[0].get("sourceId", doc_id)) if payloads else doc_id
        self.replace_source_chunks(table_name, source_id, doc_id, vectors, payloads)

    def replace_source_chunks(
        self,
        table_name: str,
        source_id: str,
        doc_id: str,
        vectors: list[list[float]],
        payloads: list[dict],
    ) -> None:
        from qdrant_client.models import PointStruct

        if len(vectors) != len(payloads):
            raise ValueError("Anzahl von Vektoren und Payloads muss identisch sein.")
        if not vectors:
            raise ValueError("Mindestens ein Vektor ist fuer den Source-Austausch erforderlich.")
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
                        "source_id": source_id,
                        "content_hash": payload.get("contentHash", doc_id),
                        "version": int(payload.get("version", 1)),
                        "is_active": True,
                        "canonical_location": payload.get("canonicalLocation", ""),
                        "corpus_version": payload.get("corpusVersion", ""),
                        "category": payload.get("category", ""),
                        "instrument": payload.get("instrument", ""),
                        "authority": payload.get("authority", "unclassified"),
                        "document_status": payload.get("documentStatus", "active"),
                        "section": payload.get("section", ""),
                        "heading_path": payload.get("headingPath", []),
                        "parent_section": payload.get("parentSection", ""),
                        "previous_section": payload.get("previousSection", ""),
                        "next_section": payload.get("nextSection", ""),
                        "content_types": payload.get("contentTypes", []),
                        "complete_tables": payload.get("completeTables", []),
                    },
                )
            )
        from qdrant_client.models import FieldCondition, MatchValue

        old_ids = self._matching_ids(
            table_name,
            [
                FieldCondition(key="source_id", match=MatchValue(value=source_id)),
                FieldCondition(key="is_active", match=MatchValue(value=True)),
            ],
        )
        self._client.upsert(collection_name=name, points=points)
        new_ids = {point.id for point in points}
        stale_ids = [point_id for point_id in old_ids if point_id not in new_ids]
        try:
            if stale_ids:
                self._client.set_payload(
                    collection_name=name, payload={"is_active": False}, points=stale_ids
                )
        except Exception:
            new_only_ids = [point_id for point_id in new_ids if point_id not in set(old_ids)]
            if new_only_ids:
                self._client.set_payload(
                    collection_name=name, payload={"is_active": False}, points=new_only_ids
                )
            if old_ids:
                self._client.set_payload(
                    collection_name=name, payload={"is_active": True}, points=old_ids
                )
            raise
        _logger.info("qdrant source replacement fertig: source=%s… doc=%s… points=%s", source_id[:12], doc_id[:12], len(points))

    def activate_source_version(self, table_name: str, source_id: str, doc_id: str) -> None:
        from qdrant_client.models import FieldCondition, MatchValue

        source_ids = self._matching_ids(
            table_name, [FieldCondition(key="source_id", match=MatchValue(value=source_id))]
        )
        target_ids = self._matching_ids(
            table_name,
            [
                FieldCondition(key="source_id", match=MatchValue(value=source_id)),
                FieldCondition(key="document_id", match=MatchValue(value=doc_id)),
            ],
        )
        if not target_ids:
            raise ValueError(f"Keine Vektoren fuer Source-Version {source_id}/{doc_id}")
        name = _sanitize_collection(table_name)
        self._client.set_payload(collection_name=name, payload={"is_active": True}, points=target_ids)
        stale_ids = [point_id for point_id in source_ids if point_id not in set(target_ids)]
        if stale_ids:
            self._client.set_payload(collection_name=name, payload={"is_active": False}, points=stale_ids)

    def cleanup_inactive_versions(self, table_name: str, source_id: str | None = None) -> int:
        from qdrant_client.models import FieldCondition, MatchValue

        conditions = [FieldCondition(key="is_active", match=MatchValue(value=False))]
        if source_id is not None:
            conditions.append(FieldCondition(key="source_id", match=MatchValue(value=source_id)))
        ids = self._matching_ids(table_name, conditions)
        if ids:
            self._client.delete(collection_name=_sanitize_collection(table_name), points_selector=ids)
        return len(ids)

    def similarity_search(
        self,
        table_name: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        name = _sanitize_collection(table_name)
        # qdrant-client >= 1.7: kein .search() mehr auf QdrantClient; Vektorsuche ueber query_points()
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        resp = self._client.query_points(
            collection_name=name,
            query=query_vector,
            query_filter=Filter(must=[FieldCondition(key="is_active", match=MatchValue(value=True))]),
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
                    "category": p.get("category", ""),
                    "instrument": p.get("instrument", ""),
                    "authority": p.get("authority", "unclassified"),
                    "status": p.get("document_status", "active"),
                    "section": p.get("section", ""),
                    "headingPath": p.get("heading_path", []),
                    "parentSection": p.get("parent_section", ""),
                    "previousSection": p.get("previous_section", ""),
                    "nextSection": p.get("next_section", ""),
                    "contentTypes": p.get("content_types", []),
                    "sourceId": p.get("source_id", ""),
                    "canonicalLocation": p.get("canonical_location", ""),
                    "corpusVersion": p.get("corpus_version", ""),
                    "completeTables": p.get("complete_tables", []),
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
        from qdrant_client.models import Filter, FieldCondition, MatchText, MatchValue
        name = _sanitize_collection(table_name)
        try:
            resp = self._client.query_points(
                collection_name=name,
                query=query_vector,
                query_filter=Filter(must=[
                    FieldCondition(key="is_active", match=MatchValue(value=True)),
                    FieldCondition(key="file_name", match=MatchText(text=pattern)),
                ]),
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
                    "category": p.get("category", ""),
                    "instrument": p.get("instrument", ""),
                    "authority": p.get("authority", "unclassified"),
                    "status": p.get("document_status", "active"),
                    "section": p.get("section", ""),
                    "headingPath": p.get("heading_path", []),
                    "parentSection": p.get("parent_section", ""),
                    "previousSection": p.get("previous_section", ""),
                    "nextSection": p.get("next_section", ""),
                    "contentTypes": p.get("content_types", []),
                    "sourceId": p.get("source_id", ""),
                    "canonicalLocation": p.get("canonical_location", ""),
                    "corpusVersion": p.get("corpus_version", ""),
                    "completeTables": p.get("complete_tables", []),
                    "similarity": float(score) if score is not None else 0.0,
                }
            )
        return out
