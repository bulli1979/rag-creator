from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import PlainTextResponse

from ..dependencies import get_ingest_service
from ..ingest_service import IngestService
from ..models import UploadOptions

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.get("")
async def list_documents(svc: IngestService = Depends(get_ingest_service)):
    docs = svc.list_documents()
    return [doc.model_dump(by_alias=True) for doc in docs]


@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...),
    tags: str = Form(""),
    source: str = Form("lokal"),
    svc: IngestService = Depends(get_ingest_service),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    options = UploadOptions(tags=tag_list, source=source or "lokal")

    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        file_tuples.append((f.filename or "unknown", content))

    try:
        result = await svc.add_documents(file_tuples, options)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _logger.exception("upload_documents")
        raise HTTPException(
            status_code=500,
            detail=f"Upload fehlgeschlagen: {exc}",
        ) from exc
    return result.model_dump(by_alias=True)


@router.delete("/{doc_id}")
async def remove_document(
    doc_id: str,
    svc: IngestService = Depends(get_ingest_service),
):
    await svc.remove_document(doc_id)
    return {"ok": True}


@router.post("/remove-bulk")
async def remove_documents_bulk(
    body: dict,
    svc: IngestService = Depends(get_ingest_service),
):
    doc_ids = body.get("docIds", [])
    await svc.remove_documents(doc_ids)
    return {"ok": True}


@router.post("/{doc_id}/reindex")
async def reindex_document(
    doc_id: str,
    svc: IngestService = Depends(get_ingest_service),
):
    await svc.reindex_document(doc_id)
    return {"ok": True}


@router.post("/reindex-bulk")
async def reindex_documents_bulk(
    body: dict,
    svc: IngestService = Depends(get_ingest_service),
):
    doc_ids = body.get("docIds", [])
    await svc.reindex_documents(doc_ids)
    return {"ok": True}


@router.get("/export/csv")
async def export_csv(svc: IngestService = Depends(get_ingest_service)):
    csv_content = svc.export_documents_as_csv()
    return PlainTextResponse(content=csv_content, media_type="text/csv")
