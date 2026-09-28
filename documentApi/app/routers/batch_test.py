from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from ..auth import require_admin_key
from ..batch_test_service import get_batch_test_service, resolve_batch_upload
from ..models import ApiKeyRecord

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch-test", tags=["batch-test"])


class BatchSettingsBody(BaseModel):
    settings_id: str | None = Field(None, alias="settingsId")
    name: str = "Test-Settings"
    chat_settings: dict = Field(default_factory=dict, alias="chatSettings")
    eval_judge: dict = Field(default_factory=dict, alias="evalJudge")

    model_config = {"populate_by_name": True}


class CopySettingsBody(BaseModel):
    name: str | None = None


@router.get("/defaults")
async def get_batch_defaults(_admin: ApiKeyRecord = Depends(require_admin_key)):
    return get_batch_test_service().default_run_settings()


@router.get("/settings")
async def list_batch_settings(_admin: ApiKeyRecord = Depends(require_admin_key)):
    return {"settings": get_batch_test_service().list_settings()}


@router.get("/settings/{settings_id}")
async def get_batch_settings(settings_id: str, _admin: ApiKeyRecord = Depends(require_admin_key)):
    row = get_batch_test_service().get_settings(settings_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Test-Settings nicht gefunden.")
    return row


@router.post("/settings")
async def save_batch_settings(
    body: BatchSettingsBody,
    _admin: ApiKeyRecord = Depends(require_admin_key),
):
    return get_batch_test_service().save_settings(
        settings_id=body.settings_id,
        name=body.name,
        chat_settings=body.chat_settings,
        eval_judge=body.eval_judge,
    )


@router.delete("/settings/{settings_id}")
async def delete_batch_settings(settings_id: str, _admin: ApiKeyRecord = Depends(require_admin_key)):
    ok = get_batch_test_service().delete_settings(settings_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Test-Settings nicht gefunden.")
    return {"ok": True}


@router.post("/settings/from-run/{run_id}")
async def copy_settings_from_run(
    run_id: str,
    body: CopySettingsBody | None = None,
    _admin: ApiKeyRecord = Depends(require_admin_key),
):
    try:
        return get_batch_test_service().copy_settings_from_run(
            run_id,
            name=(body.name if body else None),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs")
async def list_batch_runs(
    limit: int = Query(50, ge=1, le=200),
    sortBy: str = Query("createdAt"),
    sortDir: str = Query("desc"),
    _admin: ApiKeyRecord = Depends(require_admin_key),
):
    svc = get_batch_test_service()
    return {"runs": svc.list_runs(limit=limit, sort_by=sortBy, sort_dir=sortDir)}


@router.get("/runs/{run_id}")
async def get_batch_run(
    run_id: str,
    _admin: ApiKeyRecord = Depends(require_admin_key),
):
    run = get_batch_test_service().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Bulk-Test-Lauf nicht gefunden.")
    return run


@router.delete("/runs/{run_id}")
async def delete_batch_run(
    run_id: str,
    _admin: ApiKeyRecord = Depends(require_admin_key),
):
    ok = get_batch_test_service().delete_run(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bulk-Test-Lauf nicht gefunden.")
    return {"ok": True}


@router.post("/runs")
async def start_batch_run(
    file: UploadFile = File(...),
    questionsFile: UploadFile | None = File(None),
    evaluateAnswers: str = Form("false"),
    language: str = Form(""),
    settingsId: str = Form(""),
    settingsName: str = Form(""),
    environmentId: str = Form(""),
    familyId: str = Form(""),
    runAllInstances: str = Form("false"),
    chatSettingsJson: str = Form(""),
    evalJudgeJson: str = Form(""),
    _admin: ApiKeyRecord = Depends(require_admin_key),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Leere Datei.")
    filename = file.filename or "questions.yaml"

    companion_bytes: bytes | None = None
    companion_name: str | None = None
    if questionsFile is not None:
        companion_bytes = await questionsFile.read()
        companion_name = questionsFile.filename or "question.yaml"
        if not companion_bytes:
            companion_bytes = None

    try:
        questions, cfg_opts, display_name = resolve_batch_upload(
            raw,
            filename,
            companion=companion_bytes,
            companion_name=companion_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Fragen-Datei ungültig: {exc}") from exc

    form_eval = str(evaluateAnswers or "").strip().lower() in ("1", "true", "yes", "on")
    evaluate = form_eval or bool(cfg_opts.get("evaluateAnswers", False))

    lang = (language or "").strip().lower() or None
    if not lang:
        cfg_lang = cfg_opts.get("language")
        lang = cfg_lang if cfg_lang in ("de", "en") else None
    if lang not in (None, "de", "en"):
        raise HTTPException(status_code=400, detail="language muss de, en oder leer sein.")

    chat_override = cfg_opts.get("chatSettings") if isinstance(cfg_opts.get("chatSettings"), dict) else None
    eval_judge = cfg_opts.get("evalJudge") if isinstance(cfg_opts.get("evalJudge"), dict) else None
    if chatSettingsJson.strip():
        try:
            parsed = json.loads(chatSettingsJson)
            if isinstance(parsed, dict):
                chat_override = {**(chat_override or {}), **parsed}
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"chatSettingsJson ungültig: {exc}") from exc
    if evalJudgeJson.strip():
        try:
            parsed = json.loads(evalJudgeJson)
            if isinstance(parsed, dict):
                eval_judge = {**(eval_judge or {}), **parsed}
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"evalJudgeJson ungültig: {exc}") from exc

    env_id = (environmentId or "").strip() or None
    if not env_id and isinstance(cfg_opts.get("activePostgresEnvironmentId"), str):
        env_id = str(cfg_opts.get("activePostgresEnvironmentId") or "").strip() or None

    family_id = (familyId or "").strip() or None
    run_all = str(runAllInstances or "").strip().lower() in ("1", "true", "yes", "on")

    svc = get_batch_test_service()
    try:
        if run_all and family_id:
            run = await svc.start_family_run(
                questions=questions,
                file_name=display_name,
                evaluate_answers=evaluate,
                language=lang,
                family_id=family_id,
                chat_override=chat_override,
                eval_judge=eval_judge,
                settings_id=(settingsId or "").strip() or None,
                settings_name=(settingsName or "").strip(),
            )
        else:
            run = await svc.start_run(
                questions=questions,
                file_name=display_name,
                evaluate_answers=evaluate,
                language=lang,
                chat_override=chat_override,
                eval_judge=eval_judge,
                settings_id=(settingsId or "").strip() or None,
                settings_name=(settingsName or "").strip(),
                environment_id=env_id,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    _logger.info(
        "batch-test started runId=%s questions=%s evaluate=%s file=%s env=%s model=%s family=%s",
        run.get("runId"),
        run.get("total"),
        evaluate,
        display_name,
        run.get("environmentName"),
        run.get("llmModel"),
        run.get("familyRunId"),
    )
    return run


@router.post("/runs/{run_id}/cancel")
async def cancel_batch_run(
    run_id: str,
    _admin: ApiKeyRecord = Depends(require_admin_key),
):
    svc = get_batch_test_service()
    ok = await svc.cancel_run(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Bulk-Test-Lauf nicht gefunden.")
    run = svc.get_run(run_id)
    return run if run else {"ok": True}
