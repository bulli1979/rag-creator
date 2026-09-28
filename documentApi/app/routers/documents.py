from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import PlainTextResponse

from ..dependencies import get_ingest_service
from ..ingest_service import IngestService
from ..models import UploadFolderRequest, UploadOptions

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
    embeddingModel: str = Form(""),
    svc: IngestService = Depends(get_ingest_service),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    options = UploadOptions(
        tags=tag_list,
        source=source or "lokal",
        embeddingModel=(embeddingModel or "").strip() or None,
    )

    file_tuples: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        file_tuples.append((f.filename or "unknown", content))

    try:
        result = await svc.add_documents(file_tuples, options)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _logger.exception("upload_documents")
        raise HTTPException(
            status_code=500,
            detail=f"Upload fehlgeschlagen: {exc}",
        ) from exc
    return result.model_dump(by_alias=True)


@router.post("/upload-folder-path")
async def upload_folder_path(
    body: UploadFolderRequest,
    svc: IngestService = Depends(get_ingest_service),
):
    options = UploadOptions(
        tags=body.tags,
        source=body.source or "lokal",
        embeddingModel=body.embedding_model,
    )
    try:
        result, file_count, next_offset, done = await svc.add_documents_from_folder_path(
            body.folder_path,
            options,
            offset=body.offset,
            batch_size=body.batch_size,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _logger.exception("upload_folder_path")
        raise HTTPException(
            status_code=500,
            detail=f"Ordner-Upload fehlgeschlagen: {exc}",
        ) from exc
    payload = result.model_dump(by_alias=True)
    payload["fileCount"] = file_count
    payload["nextOffset"] = next_offset
    payload["done"] = done
    return payload


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


@router.post("/remove-not-ingested")
async def remove_not_ingested_documents(
    svc: IngestService = Depends(get_ingest_service),
):
    removed = await svc.remove_not_ingested_documents()
    return {"ok": True, "removedCount": removed}


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


@router.post("/family-reindex")
async def start_family_reindex(
    body: dict | None = None,
    svc: IngestService = Depends(get_ingest_service),
):
    payload = body or {}
    try:
        return await svc.start_family_reindex(
            family_id=(payload.get("familyId") or "").strip() or None,
            source_environment_id=(payload.get("sourceEnvironmentId") or "").strip() or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/family-reindex/status")
async def family_reindex_status(svc: IngestService = Depends(get_ingest_service)):
    status = svc.get_family_reindex_status()
    return status or {"status": "idle"}


@router.post("/family-reindex/cancel")
async def cancel_family_reindex(svc: IngestService = Depends(get_ingest_service)):
    ok = svc.cancel_family_reindex()
    if not ok:
        raise HTTPException(status_code=404, detail="Kein laufender Familien-Reindex.")
    return svc.get_family_reindex_status() or {"ok": True}


@router.get("/export/csv")
async def export_csv(svc: IngestService = Depends(get_ingest_service)):
    csv_content = svc.export_documents_as_csv()
    return PlainTextResponse(content=csv_content, media_type="text/csv")
