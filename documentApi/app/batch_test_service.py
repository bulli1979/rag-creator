"""In-process Bulk-/Batch-Test gegen ChatService (Fragen-Datei → Ergebnisse + Stats)."""

from __future__ import annotations

import asyncio
import ast
import csv
import io
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml

from .chat_service import ChatService
from .claim_judge import build_claim_eval_prompt, score_claims_from_payload
from .database import IndexDatabase
from .models import ChatRequest, ChatSettings

_logger = logging.getLogger(__name__)

BatchStatus = Literal["queued", "running", "done", "error", "cancelled"]

DEFAULT_CHAT_OVERRIDE: dict[str, Any] = {
    "temperature": 0.3,
    "maxTokens": 2048,
    "topK": 5,
    "rerankSimilarityWeight": 0.90,
    "rerankLexicalWeight": 0.05,
    "rerankNumericWeight": 0.05,
    "retrievalCandidateK": None,
    "systemPrompt": (
        "You are a helpful assistant that answers questions based on provided documents. "
        "Always cite the source file name when possible. Be precise and thorough."
    ),
}

DEFAULT_EVAL_JUDGE: dict[str, Any] = {
    "llmBaseUrl": "http://localhost:11434/v1",
    "llmApiKey": "ollama",
    "llmModel": "qwen2.5:latest",
    "temperature": 0,
    "maxTokens": 1024,
    "maxContextChars": 12000,
    "maxRetries": 2,
    "retrySleepSec": 1.5,
    "claimLevel": True,
}


@dataclass
class BatchQuestion:
    id: str
    type: str
    question: str
    answer_field: str | None = None


@dataclass
class BatchItemResult:
    row_no: int
    question_id: str
    question_type: str
    question: str
    ground_truth: str
    answer: str
    error: str
    latency_ms: float | None
    prompt_tokens: float | None
    completion_tokens: float | None
    total_tokens: float | None
    tokens_per_second: float | None
    chunk_count: int
    chunks_summary: str
    context_chunks: list[dict[str, Any]] = field(default_factory=list)
    judge_answer_relevance: float | None = None
    judge_context_relevance: float | None = None
    judge_groundedness: float | None = None
    judge_answer_correctness: float | None = None
    judge_notes: str = ""
    judge_error: str = ""


@dataclass
class BatchTestRun:
    run_id: str
    status: BatchStatus
    created_at: str
    file_name: str
    evaluate_answers: bool
    language: str | None
    total: int
    current: int = 0
    progress: int = 0
    message: str = ""
    error: str = ""
    finished_at: str | None = None
    results: list[BatchItemResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    llm_model: str = ""
    environment_id: str = ""
    environment_name: str = ""
    cancel_requested: bool = False
    settings_id: str | None = None
    settings_name: str = ""
    settings_snapshot: dict[str, Any] = field(default_factory=dict)
    family_run_id: str | None = None
    family_instance_index: int | None = None
    family_instance_total: int | None = None

    def to_public_dict(self, *, include_results: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "runId": self.run_id,
            "status": self.status,
            "createdAt": self.created_at,
            "finishedAt": self.finished_at,
            "fileName": self.file_name,
            "evaluateAnswers": self.evaluate_answers,
            "language": self.language,
            "total": self.total,
            "current": self.current,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "llmModel": self.llm_model,
            "environmentId": self.environment_id,
            "environmentName": self.environment_name,
            "settingsId": self.settings_id,
            "settingsName": self.settings_name,
            "settingsSnapshot": self.settings_snapshot,
            "summary": self.summary,
            "familyRunId": self.family_run_id,
            "familyInstanceIndex": self.family_instance_index,
            "familyInstanceTotal": self.family_instance_total,
        }
        if include_results:
            payload["results"] = [asdict(r) for r in self.results]
        return payload

    def to_db_payload(self) -> dict[str, Any]:
        data = self.to_public_dict(include_results=True)
        return data


_RUNS: dict[str, BatchTestRun] = {}
_LOCK = asyncio.Lock()
_MAX_RUNS = 30
# familyRunId → Abbruchflag für Sequenz über alle Instanzen einer Familie
_FAMILY_CANCEL: dict[str, bool] = {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_type(raw: Any, *, require: bool = False) -> str:
    t = str(raw or "").strip()
    if not t:
        if require:
            raise ValueError("Jede Frage braucht ein type (Subjective | Objective).")
        return ""
    low = t.lower()
    if low in ("subjective", "subj"):
        return "Subjective"
    if low in ("objective", "obj"):
        return "Objective"
    if t in ("Subjective", "Objective"):
        return t
    raise ValueError(f"Ungültiger type '{raw}'. Erlaubt: Subjective, Objective.")


def parse_questions_bytes(content: bytes, filename: str) -> list[BatchQuestion]:
    name = (filename or "questions.yaml").lower()
    text = content.decode("utf-8-sig")
    if name.endswith((".yaml", ".yml")):
        return _parse_yaml_questions(text)
    if name.endswith(".json"):
        return _parse_json_questions(text)
    if name.endswith(".csv"):
        return _parse_csv_questions(text)
    # Heuristik
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return _parse_json_questions(text)
    if "," in text.splitlines()[0] and "question" in text.splitlines()[0].lower():
        return _parse_csv_questions(text)
    return _parse_yaml_questions(text)


def _looks_like_batch_config(data: dict[str, Any]) -> bool:
    keys = set(data.keys())
    return bool(
        keys
        & {
            "questionsFile",
            "apiBaseUrl",
            "chatSettings",
            "evaluateAnswers",
            "evalJudge",
            "outputExcel",
        }
    )


def _repo_batch_test_dir() -> Path | None:
    # documentApi/app/batch_test_service.py → repo root / batchTest
    try:
        root = Path(__file__).resolve().parents[2]
        candidate = root / "batchTest"
        return candidate if candidate.is_dir() else None
    except Exception:
        return None


def resolve_batch_upload(
    primary: bytes,
    primary_name: str,
    *,
    companion: bytes | None = None,
    companion_name: str | None = None,
) -> tuple[list[BatchQuestion], dict[str, Any], str]:
    """
    Akzeptiert Fragen-Datei (yaml/json/csv) oder batch_config.json.
    Bei Config mit leerem questions[] + questionsFile: Companion-Upload oder
    lokale batchTest/<questionsFile> nutzen.
    Returns: (questions, options, display_name)
    options kann evaluateAnswers / language aus der Config enthalten.
    """
    name = primary_name or "upload"
    options: dict[str, Any] = {}
    lower = name.lower()

    if lower.endswith(".json") or primary.lstrip().startswith(b"{"):
        try:
            data = json.loads(primary.decode("utf-8-sig"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and _looks_like_batch_config(data):
            if "evaluateAnswers" in data:
                options["evaluateAnswers"] = bool(data.get("evaluateAnswers"))
            lang = data.get("language")
            if lang in ("de", "en"):
                options["language"] = lang
            if isinstance(data.get("chatSettings"), dict):
                options["chatSettings"] = data["chatSettings"]
            if isinstance(data.get("evalJudge"), dict):
                options["evalJudge"] = data["evalJudge"]

            inline = data.get("questions")
            questions: list[BatchQuestion] = []
            if isinstance(inline, list) and inline:
                # Inline-Fragen aus Config (Strings oder Objekte)
                questions = _parse_json_questions(json.dumps({"questions": inline}))

            qfile = str(data.get("questionsFile") or "").strip()
            if not questions and qfile:
                q_bytes: bytes | None = None
                q_name = Path(qfile).name
                if companion:
                    q_bytes = companion
                    q_name = companion_name or q_name
                else:
                    base = _repo_batch_test_dir()
                    if base is not None:
                        # relativ wie im CLI: neben der Config unter batchTest/
                        candidates = [
                            base / qfile,
                            base / Path(qfile).name,
                        ]
                        for cand in candidates:
                            if cand.is_file():
                                q_bytes = cand.read_bytes()
                                q_name = cand.name
                                break
                if q_bytes is None:
                    raise ValueError(
                        f"batch_config.json verweist auf questionsFile={qfile!r}, "
                        "enthält aber keine Fragen. Bitte zusätzlich die Fragen-Datei "
                        f"hochladen (z. B. batchTest/{Path(qfile).name}) "
                        "oder direkt die YAML/CSV hochladen."
                    )
                questions = parse_questions_bytes(q_bytes, q_name)
                return questions, options, f"{name} + {q_name}"

            if not questions:
                raise ValueError(
                    "batch_config.json enthält keine Fragen (questions: []). "
                    "questionsFile setzen und Fragen-Datei mit hochladen, "
                    "oder question.yaml direkt hochladen."
                )
            return questions, options, name

    # Reine Fragen-Datei; Companion ignorieren außer als Fallback unnötig
    questions = parse_questions_bytes(primary, name)
    return questions, options, name


def _parse_yaml_questions(text: str) -> list[BatchQuestion]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or "questions" not in data:
        raise ValueError("YAML muss ein Mapping mit Schlüssel 'questions' sein.")
    raw_list = data["questions"]
    if not isinstance(raw_list, list):
        raise ValueError("'questions' muss eine Liste sein.")
    out: list[BatchQuestion] = []
    for i, item in enumerate(raw_list, start=1):
        if not isinstance(item, dict):
            raise ValueError("Jedes Element unter 'questions' muss ein Objekt sein.")
        qid = str(item.get("id") or f"q{i}").strip()
        qtext = str(item.get("question") or "").strip()
        if not qtext:
            raise ValueError(f"Frage {qid!r} braucht 'question'.")
        af = item.get("answerField", item.get("answer_field"))
        af_s = None if af is None else str(af).strip()
        qtype = _normalize_type(item.get("type"), require=True)
        out.append(BatchQuestion(id=qid, type=qtype, question=qtext, answer_field=af_s or None))
    if not out:
        raise ValueError("Keine Fragen in der Datei gefunden.")
    return out


def _parse_json_questions(text: str) -> list[BatchQuestion]:
    data = json.loads(text)
    if isinstance(data, dict):
        if "questions" not in data:
            raise ValueError("JSON muss 'questions' enthalten (Liste oder Objekte).")
        raw = data["questions"]
        if not isinstance(raw, list):
            raise ValueError("'questions' muss eine Liste sein.")
        if raw and isinstance(raw[0], str):
            return [
                BatchQuestion(id=f"inline-{i}", type="", question=str(q).strip(), answer_field=None)
                for i, q in enumerate(raw, start=1)
                if str(q).strip()
            ]
        data = raw
    if isinstance(data, list):
        out: list[BatchQuestion] = []
        for i, item in enumerate(data, start=1):
            if isinstance(item, str):
                if item.strip():
                    out.append(BatchQuestion(id=f"inline-{i}", type="", question=item.strip()))
                continue
            if not isinstance(item, dict):
                continue
            qtext = str(item.get("question") or item.get("q") or "").strip()
            if not qtext:
                continue
            af = item.get("answerField") or item.get("answer_field") or item.get("ground_truth")
            qtype_raw = item.get("type")
            qtype = _normalize_type(qtype_raw) if qtype_raw else ("Objective" if af else "Subjective")
            out.append(
                BatchQuestion(
                    id=str(item.get("id") or f"q{i}"),
                    type=qtype,
                    question=qtext,
                    answer_field=str(af).strip() if af else None,
                )
            )
        if not out:
            raise ValueError("Keine Fragen in der JSON-Datei gefunden.")
        return out
    raise ValueError("Ungültiges JSON-Format für Fragen.")


def _parse_csv_questions(text: str) -> list[BatchQuestion]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV ohne Header.")
    fields = {f.lower().strip(): f for f in reader.fieldnames if f}
    q_key = fields.get("question") or fields.get("frage")
    gt_key = (
        fields.get("ground_truth")
        or fields.get("groundtruth")
        or fields.get("answerfield")
        or fields.get("answer_field")
        or fields.get("answer")
    )
    type_key = fields.get("type") or fields.get("question_type")
    id_key = fields.get("id") or fields.get("question_id")
    if not q_key:
        raise ValueError("CSV braucht eine Spalte 'question'.")
    out: list[BatchQuestion] = []
    for i, row in enumerate(reader, start=1):
        qtext = str(row.get(q_key) or "").strip()
        if not qtext:
            continue
        gt = str(row.get(gt_key) or "").strip() if gt_key else ""
        qtype_raw = row.get(type_key) if type_key else None
        if qtype_raw:
            qtype = _normalize_type(qtype_raw)
        else:
            qtype = "Objective" if gt else "Subjective"
        qid = str(row.get(id_key) or f"csv-{i}").strip() if id_key else f"csv-{i}"
        out.append(BatchQuestion(id=qid, type=qtype, question=qtext, answer_field=gt or None))
    if not out:
        raise ValueError("Keine Fragen in der CSV gefunden.")
    return out


def _format_chunks_summary(chunks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, ch in enumerate(chunks, start=1):
        fn = ch.get("fileName") or ch.get("file_name") or "?"
        idx = ch.get("chunkIndex", ch.get("chunk_index", "?"))
        sim = ch.get("similarity", "")
        parts.append(f"{i}. {fn}#c{idx} (sim={sim})")
    return " | ".join(parts)


def _serialize_context_chunks(chunks: list[dict[str, Any]], *, max_text_chars: int = 4000) -> list[dict[str, Any]]:
    """Persistierbare Chunk-Metadaten inkl. Text für Highlight im Corpus-Viewer."""
    out: list[dict[str, Any]] = []
    for ch in chunks:
        text = str(ch.get("text") or "").strip()
        if len(text) > max_text_chars:
            text = text[: max_text_chars - 3] + "..."
        out.append(
            {
                "documentId": ch.get("documentId") or ch.get("document_id") or "",
                "fileName": ch.get("fileName") or ch.get("file_name") or "",
                "chunkIndex": ch.get("chunkIndex", ch.get("chunk_index")),
                "similarity": ch.get("similarity"),
                "text": text,
            }
        )
    return out


def _format_chunks_full(chunks: list[dict[str, Any]], max_chars: int = 12000) -> str:
    blocks: list[str] = []
    for i, ch in enumerate(chunks, start=1):
        fn = ch.get("fileName") or ch.get("file_name") or "?"
        text = str(ch.get("text") or "").strip()
        blocks.append(f"[{i}] {fn}\n{text}")
    joined = "\n\n".join(blocks)
    if len(joined) > max_chars:
        return joined[: max_chars - 3] + "..."
    return joined


def _mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return sum(vals) / len(vals)


def build_summary(results: list[BatchItemResult], *, had_judge: bool) -> dict[str, Any]:
    latencies = [r.latency_ms for r in results if r.latency_ms is not None]
    errors = sum(1 for r in results if r.error)
    ok = len(results) - errors
    by_type: dict[str, int] = {}
    for r in results:
        key = r.question_type or "—"
        by_type[key] = by_type.get(key, 0) + 1

    judge: dict[str, Any] = {}
    if had_judge:
        metrics = {
            "answerRelevance": [r.judge_answer_relevance for r in results],
            "contextRelevance": [r.judge_context_relevance for r in results],
            "groundedness": [r.judge_groundedness for r in results],
            "answerCorrectness": [r.judge_answer_correctness for r in results],
        }
        for name, series in metrics.items():
            nums = [float(v) for v in series if v is not None]
            judge[name] = {
                "mean": _mean(nums),
                "count": len(nums),
            }
        obj_corr = [
            float(r.judge_answer_correctness)
            for r in results
            if r.question_type == "Objective" and r.judge_answer_correctness is not None
        ]
        judge["objectiveCorrectness"] = {"mean": _mean(obj_corr), "count": len(obj_corr)}

    return {
        "questionCount": len(results),
        "successCount": ok,
        "errorCount": errors,
        "successRate": (ok / len(results)) if results else 0.0,
        "latencyMs": {
            "mean": _mean([float(x) for x in latencies]),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "count": len(latencies),
        },
        "byType": by_type,
        "judge": judge if had_judge else None,
        "avgChunkCount": _mean([float(r.chunk_count) for r in results]),
        "avgTokensPerSecond": _mean(
            [float(r.tokens_per_second) for r in results if r.tokens_per_second is not None]
        ),
    }


def _clamp_score(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return max(0.0, min(1.0, n))


def _score_from(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in data:
            scored = _clamp_score(data.get(key))
            if scored is not None:
                return scored
    # case-insensitive fallback
    lower_map = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        scored = _clamp_score(lower_map.get(key.lower()))
        if scored is not None:
            return scored
    return None


def _strip_json_fences(text: str) -> str:
    text = (text or "").strip()
    if "```" not in text:
        return text
    parts = text.split("```")
    for part in parts:
        chunk = part.strip()
        if chunk.lower().startswith("json"):
            chunk = chunk[4:].strip()
        if "{" in chunk:
            return chunk
    return text


def _extract_brace_object(text: str) -> str:
    text = _strip_json_fences(text).strip()
    if not text:
        raise ValueError("leere Judge-Antwort")
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("keine JSON-Antwort")
    return text[start : end + 1]


def _repair_jsonish(blob: str) -> str:
    """Häufige LLM-JSON-Fehler: Trailing-Comma, True/False/None, unquoted keys."""
    s = blob.strip()
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    s = re.sub(r"\bNone\b", "null", s)
    s = re.sub(r"\bTrue\b", "true", s)
    s = re.sub(r"\bFalse\b", "false", s)
    # Unquoted keys: {answer_relevance: 0.5} → {"answer_relevance": 0.5}
    s = re.sub(r'([{,]\s*)([A-Za-z_][\w]*)\s*:', r'\1"\2":', s)
    return s


def _single_quoted_to_json(blob: str) -> str:
    """Python-ähnliche Single-Quotes → JSON Double-Quotes (ohne Strings zu zerstören)."""
    out: list[str] = []
    i = 0
    n = len(blob)
    in_single = False
    in_double = False
    while i < n:
        ch = blob[i]
        if in_double:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(blob[i + 1])
                i += 2
                continue
            if ch == '"':
                in_double = False
            i += 1
            continue
        if in_single:
            if ch == "\\" and i + 1 < n:
                nxt = blob[i + 1]
                if nxt == "'":
                    out.append("'")
                elif nxt == '"':
                    out.append('\\"')
                else:
                    out.append(ch)
                    out.append(nxt)
                i += 2
                continue
            if ch == "'":
                out.append('"')
                in_single = False
                i += 1
                continue
            if ch == '"':
                out.append('\\"')
                i += 1
                continue
            out.append(ch)
            i += 1
            continue
        # außerhalb von Strings
        if ch == '"':
            in_double = True
            out.append(ch)
            i += 1
            continue
        if ch == "'":
            in_single = True
            out.append('"')
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _extract_json(text: str) -> dict[str, Any]:
    """JSON aus Judge-Antwort; tolerant gegenüber Single-Quotes / Trailing-Commas."""
    blob = _extract_brace_object(text)
    candidates = [
        blob,
        _repair_jsonish(blob),
        _repair_jsonish(_single_quoted_to_json(blob)),
        _single_quoted_to_json(_repair_jsonish(blob)),
    ]
    seen: set[str] = set()
    last_err: Exception | None = None
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        try:
            parsed = json.loads(cand)
            if isinstance(parsed, dict):
                return parsed
            last_err = ValueError("JSON ist kein Objekt")
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    # Python-Dict-Literal (einfache Quotes) als Fallback
    try:
        py = blob
        py = re.sub(r"\bnull\b", "None", py)
        py = re.sub(r"\btrue\b", "True", py, flags=re.IGNORECASE)
        py = re.sub(r"\bfalse\b", "False", py, flags=re.IGNORECASE)
        py = re.sub(r",\s*}", "}", py)
        py = re.sub(r",\s*]", "]", py)
        obj = ast.literal_eval(py)
        if isinstance(obj, dict):
            return {str(k): v for k, v in obj.items()}
    except Exception as exc:  # noqa: BLE001
        last_err = exc

    raise ValueError(f"ungültiges Judge-JSON: {last_err}")


def _build_judge_prompt(
    *,
    question: str,
    answer: str,
    context: str | None,
    ground_truth: str | None,
    question_type: str | None,
    claim_level: bool = False,
) -> str:
    """Rubriken + Chain-of-Thought. Bei claim_level nur AR/CR (GR/AC kommen aus Claims)."""
    qt = (question_type or "").strip()
    has_gt = bool((ground_truth or "").strip()) and (ground_truth or "").strip() != "[NONE]"
    type_hint = ""
    if qt == "Objective":
        type_hint = (
            "Question type: objective. "
            + (
                "Focus on answer_relevance and context_relevance; leave groundedness/answer_correctness null."
                if claim_level
                else "ALWAYS set answer_correctness (0.0–1.0) when ground truth is present."
            )
        )
    elif qt == "Subjective":
        type_hint = (
            "Question type: subjective. ALWAYS set answer_relevance. "
            + (
                "Leave answer_correctness null here."
                if claim_level
                else "Set answer_correctness only if ground truth is present; otherwise null."
            )
        )

    if claim_level:
        metric_rules = (
            "- answer_relevance is REQUIRED (never null).\n"
            "- context_relevance is REQUIRED.\n"
            "- groundedness: set null (computed later via claim-level check).\n"
            "- answer_correctness: set null (computed later via claim-level check).\n"
        )
        rubric_extra = (
            "- groundedness / answer_correctness: leave null — they are scored in a separate claim pass.\n"
        )
        process = (
            "1) Write brief reasoning (2–5 sentences) for answer_relevance and context_relevance only.\n"
            "2) Then output a single JSON object (no markdown fences):\n"
            '{"answer_relevance":0.0,"context_relevance":0.0,'
            '"groundedness":null,"answer_correctness":null,"notes":""}\n'
        )
    else:
        metric_rules = (
            "- answer_relevance is REQUIRED (never null).\n"
            + (
                "- answer_correctness: REQUIRED number 0.0–1.0 (ground truth is present).\n"
                if has_gt
                else "- answer_correctness: MUST be null (no ground truth).\n"
            )
        )
        rubric_extra = (
            "- groundedness: Is the answer supported only by the provided Context (no invented facts)? "
            "Ignore whether it matches ground truth or fully answers the question. "
            "1.0 = fully supported by context; 0.5 = partly supported; 0.0 = mostly hallucinated "
            "or Context is [NONE] while the answer asserts facts.\n"
            "- answer_correctness: Semantic agreement with Ground truth (not exact wording). "
            "Ignore style and citations. "
            "1.0 = key facts match; 0.5 = partial; 0.0 = contradicts or misses key facts. "
            "null if Ground truth is [NONE].\n"
        )
        process = (
            "1) Write brief reasoning (3–8 sentences): cover answer_relevance, context_relevance, "
            "groundedness, and answer_correctness (if applicable). Mention decisive evidence.\n"
            "2) Then output a single JSON object (no markdown fences) with exactly these keys:\n"
            '{"answer_relevance":0.0,"context_relevance":0.0,'
            '"groundedness":0.0,"answer_correctness":0.0,"notes":""}\n'
        )

    return (
        "You are a strict evaluator for a RAG assistant.\n"
        "Score each metric from 0.0 to 1.0 using the rubrics below.\n\n"
        "## Rubrics (keep metrics independent — do not mix criteria)\n"
        "- answer_relevance: Does the answer address the user's question (topic/intent)? "
        "Ignore factual accuracy, context support, and ground truth. "
        "1.0 = fully on-topic; 0.5 = partial; 0.0 = off-topic / empty / refuses without addressing the question. "
        "A fluent but invented answer can still score high on relevance.\n"
        "- context_relevance: Are the retrieved context passages useful for answering the question? "
        "Ignore whether the answer used them. "
        "1.0 = clearly useful; 0.5 = partly useful; 0.0 = irrelevant or empty. "
        "If Context is [NONE], score 0.0.\n"
        f"{rubric_extra}\n"
        "## Process (required)\n"
        f"{process}"
        "Rules:\n"
        "- JSON MUST use double quotes for all keys and string values (not single quotes).\n"
        f"{metric_rules}"
        "- notes: one short sentence summarizing the main issue or strength (max ~200 chars).\n"
        "- Be conservative: when uncertain, prefer the lower score.\n"
        f"{type_hint}\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:\n{answer}\n\n"
        f"Context:\n{context if context else '[NONE]'}\n\n"
        f"Ground truth:\n{ground_truth if ground_truth else '[NONE]'}\n"
    )


def _judge_notes_from(data: dict[str, Any], raw_content: str) -> str:
    notes = str(data.get("notes") or data.get("Notes") or "").strip()
    # CoT-Text vor dem JSON mit speichern (kurz), falls notes leer/kurz sind
    reasoning = raw_content
    json_start = reasoning.find("{")
    if json_start > 0:
        reasoning = reasoning[:json_start].strip()
    reasoning = reasoning[:600].strip()
    if notes and reasoning:
        combined = f"{notes} | {reasoning}"
    else:
        combined = notes or reasoning
    return combined[:800]


async def _judge_chat_json(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
    prompt: str,
    max_retries: int,
    retry_sleep_sec: float,
) -> tuple[dict[str, Any] | None, str, str]:
    """Returns (parsed_dict|None, raw_content, error)."""
    attempts = max(1, int(max_retries) + 1)
    last_error = ""
    last_content = ""
    for attempt in range(attempts):
        try:
            resp = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {api_key or 'ollama'}"},
                json={
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code >= 400:
                last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                if attempt + 1 < attempts:
                    await asyncio.sleep(retry_sleep_sec)
                    continue
                return None, last_content, last_error
            content = ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            last_content = str(content)
            data = _extract_json(last_content)
            return data, last_content, ""
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            if attempt + 1 < attempts:
                await asyncio.sleep(retry_sleep_sec)
                continue
            return None, last_content, last_error
    return None, last_content, last_error or "Judge fehlgeschlagen"


async def _judge_one(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int,
    question: str,
    answer: str,
    context: str | None,
    ground_truth: str | None,
    question_type: str | None,
    max_retries: int = 2,
    retry_sleep_sec: float = 1.5,
    claim_level: bool = True,
) -> dict[str, Any]:
    empty = {
        "answer_relevance": None,
        "context_relevance": None,
        "groundedness": None,
        "answer_correctness": None,
        "notes": "",
        "error": "",
        "claimPrecision": None,
        "claimRecall": None,
    }
    has_gt = bool((ground_truth or "").strip()) and (ground_truth or "").strip() != "[NONE]"
    has_ctx = bool((context or "").strip()) and (context or "").strip() != "[NONE]"

    rubric_prompt = _build_judge_prompt(
        question=question,
        answer=answer,
        context=context,
        ground_truth=ground_truth,
        question_type=question_type,
        claim_level=claim_level,
    )
    data, raw, err = await _judge_chat_json(
        client,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        prompt=rubric_prompt,
        max_retries=max_retries,
        retry_sleep_sec=retry_sleep_sec,
    )
    if data is None:
        empty["error"] = err or "Judge fehlgeschlagen"
        return empty

    ar = _score_from(data, "answer_relevance", "answerRelevance", "relevance")
    if ar is None:
        empty["error"] = err or "Kein answer_relevance im Judge-JSON"
        empty["notes"] = _judge_notes_from(data, raw)
        return empty

    result = {
        "answer_relevance": ar,
        "context_relevance": _score_from(data, "context_relevance", "contextRelevance"),
        "groundedness": _score_from(data, "groundedness"),
        "answer_correctness": _score_from(data, "answer_correctness", "answerCorrectness", "correctness"),
        "notes": _judge_notes_from(data, raw),
        "error": "",
        "claimPrecision": None,
        "claimRecall": None,
    }

    if not claim_level:
        return result

    claim_prompt = build_claim_eval_prompt(
        question=question,
        answer=answer,
        context=context,
        ground_truth=ground_truth if has_gt else None,
    )
    claim_data, claim_raw, claim_err = await _judge_chat_json(
        client,
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max(max_tokens, 1024),
        prompt=claim_prompt,
        max_retries=max_retries,
        retry_sleep_sec=retry_sleep_sec,
    )
    if claim_data is None:
        # Rubrik-Scores behalten; Claim-Fehler nur vermerken
        result["notes"] = (
            (result["notes"] + " | " if result["notes"] else "")
            + f"Claim-Pass fehlgeschlagen: {claim_err or 'unbekannt'}"
        )[:800]
        return result

    scored = score_claims_from_payload(
        claim_data,
        has_ground_truth=has_gt,
        has_context=has_ctx,
    )
    if scored.get("groundedness") is not None:
        result["groundedness"] = scored["groundedness"]
    if has_gt and scored.get("answer_correctness") is not None:
        result["answer_correctness"] = scored["answer_correctness"]
    elif not has_gt:
        result["answer_correctness"] = None
    result["claimPrecision"] = scored.get("claimPrecision")
    result["claimRecall"] = scored.get("claimRecall")
    claim_notes = scored.get("notes") or ""
    if claim_notes:
        base_notes = result["notes"]
        result["notes"] = (
            f"{base_notes} | {claim_notes}" if base_notes else claim_notes
        )[:800]
    if claim_raw and not claim_notes:
        result["notes"] = _judge_notes_from(claim_data, claim_raw)[:800]
    return result


def normalize_chat_override(raw: dict[str, Any] | None, base: ChatSettings | None = None) -> dict[str, Any]:
    src = dict(DEFAULT_CHAT_OVERRIDE)
    if base is not None:
        src.update(
            {
                "temperature": base.temperature,
                "maxTokens": base.max_tokens,
                "topK": base.top_k,
                "rerankSimilarityWeight": base.rerank_similarity_weight,
                "rerankLexicalWeight": base.rerank_lexical_weight,
                "rerankNumericWeight": base.rerank_numeric_weight,
                "retrievalCandidateK": base.retrieval_candidate_k,
                "systemPrompt": base.system_prompt,
                "llmApiKey": base.llm_api_key,
                "llmBaseUrl": base.llm_base_url,
                "llmModel": base.llm_model,
            }
        )
    if isinstance(raw, dict):
        for key in (
            "temperature",
            "maxTokens",
            "topK",
            "rerankSimilarityWeight",
            "rerankLexicalWeight",
            "rerankNumericWeight",
            "retrievalCandidateK",
            "systemPrompt",
            "llmApiKey",
            "llmBaseUrl",
            "llmModel",
            "encryptionKey",
        ):
            if key in raw and raw[key] is not None:
                src[key] = raw[key]
            elif key == "retrievalCandidateK" and key in raw:
                # explizit null erlaubt (= Auto)
                src[key] = None
    return src


def build_run_settings_snapshot(
    *,
    chat_settings: dict[str, Any],
    eval_judge: dict[str, Any],
    app_settings: Any,
    evaluate_answers: bool,
    language: str | None,
    family_run_id: str | None = None,
    family_instance_index: int | None = None,
    family_instance_total: int | None = None,
) -> dict[str, Any]:
    """Vollständiger Settings-Snapshot für spätere Vergleiche (Top-K ↔ AC usw.)."""
    env = app_settings.get_active_postgres()
    snap: dict[str, Any] = {
        "chatSettings": chat_settings,
        "evalJudge": eval_judge,
        "appSettings": {
            "chunkSize": int(app_settings.chunk_size),
            "chunkOverlap": int(app_settings.chunk_overlap),
            "embeddingModel": str(app_settings.embedding_model),
            "storeMarkdown": bool(app_settings.store_markdown),
            "activePostgresEnvironmentId": str(app_settings.active_postgres_environment_id),
        },
        "environment": {
            "id": env.environment_id,
            "name": env.name or env.environment_id,
            "familyId": str(env.family_id or env.environment_id),
            "familyName": str(env.family_name or env.name or env.environment_id),
            "vectorBackend": str(env.vector_backend),
            "dbHost": str(env.db_host),
            "dbPort": int(env.db_port),
            "dbName": str(env.db_name),
            "dbUser": str(env.db_user),
            "dbPasswordSet": bool(str(env.db_password or "").strip()),
            "dbSchema": str(env.db_schema),
            "dbTableName": str(env.db_table_name),
            "sqliteFilePath": str(env.sqlite_file_path or ""),
            "qdrantLocalPath": str(env.qdrant_local_path or ""),
            "embeddingModel": str(env.embedding_model or app_settings.embedding_model),
            "chunkSize": int(env.chunk_size or app_settings.chunk_size),
            "chunkOverlap": int(
                env.chunk_overlap if env.chunk_overlap is not None else app_settings.chunk_overlap
            ),
            "isMatrixVariant": bool(getattr(env, "is_matrix_variant", False)),
        },
        "runOptions": {
            "evaluateAnswers": bool(evaluate_answers),
            "language": language,
        },
    }
    if family_run_id:
        snap["familyRunId"] = family_run_id
        snap["familyInstanceIndex"] = family_instance_index
        snap["familyInstanceTotal"] = family_instance_total
    return snap


def normalize_eval_judge(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_EVAL_JUDGE)
    if isinstance(raw, dict):
        for key in DEFAULT_EVAL_JUDGE:
            if key not in raw:
                continue
            if key == "claimLevel":
                out[key] = bool(raw[key])
                continue
            if raw[key] is not None:
                out[key] = raw[key]
    # Judge-Modell nie leer / nie stillschweigend = Chat-Modell
    if not str(out.get("llmModel") or "").strip():
        out["llmModel"] = "qwen2.5:latest"
    out["claimLevel"] = bool(out.get("claimLevel", True))
    return out


class BatchTestService:
    def __init__(self, chat_service: ChatService, database: IndexDatabase) -> None:
        self._chat = chat_service
        self._db = database

    def _persist(self, run: BatchTestRun) -> None:
        try:
            self._db.upsert_batch_test_run(run.to_db_payload())
        except Exception:
            _logger.exception("batch test persist failed runId=%s", run.run_id)

    def list_runs(
        self,
        *,
        limit: int = 50,
        sort_by: str = "createdAt",
        sort_dir: str = "desc",
    ) -> list[dict[str, Any]]:
        # aktive In-Memory-Runs zuerst mergen
        db_runs = self._db.list_batch_test_runs(limit=limit, sort_by=sort_by, sort_dir=sort_dir)
        by_id = {r["runId"]: r for r in db_runs}
        for run in _RUNS.values():
            by_id[run.run_id] = run.to_public_dict(include_results=False)
        items = list(by_id.values())
        reverse = str(sort_dir).lower() != "asc"
        key = sort_by if sort_by in {
            "createdAt", "finishedAt", "status", "fileName", "progress", "total", "llmModel", "environmentName"
        } else "createdAt"

        def sort_key(item: dict[str, Any]) -> Any:
            if key in ("progress", "total"):
                return item.get(key) or 0
            if key == "summary.successRate":
                return float((item.get("summary") or {}).get("successRate") or 0)
            return item.get(key) or ""

        # optional summary sorts
        if sort_by == "successRate":
            items.sort(
                key=lambda i: float((i.get("summary") or {}).get("successRate") or 0),
                reverse=reverse,
            )
        elif sort_by == "latencyMean":
            items.sort(
                key=lambda i: float(((i.get("summary") or {}).get("latencyMs") or {}).get("mean") or 0),
                reverse=reverse,
            )
        elif sort_by == "arMean":
            items.sort(
                key=lambda i: float(
                    (((i.get("summary") or {}).get("judge") or {}).get("answerRelevance") or {}).get(
                        "mean"
                    )
                    or 0
                ),
                reverse=reverse,
            )
        elif sort_by == "acMean":
            items.sort(
                key=lambda i: float(
                    (((i.get("summary") or {}).get("judge") or {}).get("answerCorrectness") or {}).get(
                        "mean"
                    )
                    or 0
                ),
                reverse=reverse,
            )
        else:
            items.sort(key=sort_key, reverse=reverse)
        return items[:limit]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        mem = _RUNS.get(run_id)
        if mem is not None:
            return mem.to_public_dict(include_results=True)
        return self._db.get_batch_test_run(run_id, include_results=True)

    def delete_run(self, run_id: str) -> bool:
        _RUNS.pop(run_id, None)
        return self._db.delete_batch_test_run(run_id)

    # —— Settings CRUD ——

    def list_settings(self) -> list[dict[str, Any]]:
        return self._db.list_batch_test_settings()

    def get_settings(self, settings_id: str) -> dict[str, Any] | None:
        return self._db.get_batch_test_settings(settings_id)

    def save_settings(
        self,
        *,
        settings_id: str | None,
        name: str,
        chat_settings: dict[str, Any] | None,
        eval_judge: dict[str, Any] | None,
    ) -> dict[str, Any]:
        sid = (settings_id or "").strip() or str(uuid.uuid4())
        return self._db.upsert_batch_test_settings(
            settings_id=sid,
            name=name,
            chat_settings=normalize_chat_override(chat_settings, self._chat.get_chat_settings()),
            eval_judge=normalize_eval_judge(eval_judge),
        )

    def delete_settings(self, settings_id: str) -> bool:
        return self._db.delete_batch_test_settings(settings_id)

    def copy_settings_from_run(self, run_id: str, *, name: str | None = None) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            raise LookupError(f"Bulk-Test-Lauf {run_id} nicht gefunden.")
        snap = run.get("settingsSnapshot") or {}
        label = (name or "").strip() or f"Kopie von {run.get('fileName') or run_id[:8]}"
        return self.save_settings(
            settings_id=None,
            name=label,
            chat_settings=snap.get("chatSettings"),
            eval_judge=snap.get("evalJudge"),
        )

    def default_run_settings(self) -> dict[str, Any]:
        settings = self._chat.get_settings()
        active = settings.get_active_postgres()
        environments = [
            {
                "id": env.environment_id,
                "name": env.name or env.environment_id,
                "vectorBackend": str(env.vector_backend),
                "familyId": str(env.family_id or env.environment_id),
                "familyName": str(env.family_name or env.name or env.environment_id),
                "embeddingModel": str(env.embedding_model or settings.embedding_model),
                "chunkSize": int(env.chunk_size or settings.chunk_size),
                "chunkOverlap": int(
                    env.chunk_overlap if env.chunk_overlap is not None else settings.chunk_overlap
                ),
                "isMatrixVariant": bool(getattr(env, "is_matrix_variant", False)),
            }
            for env in settings.postgres_environments
        ]
        families: dict[str, dict[str, Any]] = {}
        for env in settings.postgres_environments:
            fid = str(env.family_id or env.environment_id)
            if fid not in families:
                families[fid] = {
                    "familyId": fid,
                    "familyName": str(env.family_name or env.name or fid),
                    "instanceCount": 0,
                    "instanceIds": [],
                }
            families[fid]["instanceCount"] += 1
            families[fid]["instanceIds"].append(env.environment_id)
        return {
            "chatSettings": normalize_chat_override(None, self._chat.get_chat_settings()),
            "evalJudge": normalize_eval_judge(None),
            "activeEnvironmentId": active.environment_id,
            "activeEnvironmentName": active.name or active.environment_id,
            "activeFamilyId": str(active.family_id or active.environment_id),
            "environments": environments,
            "families": list(families.values()),
        }

    async def _activate_environment_if_needed(self, environment_id: str | None) -> Any:
        """Aktiviert die gewählte Umgebung und spiegelt Embedding/Chunk auf AppSettings."""
        settings = self._chat.get_settings()
        eid = (environment_id or "").strip() or settings.active_postgres_environment_id
        known = {e.environment_id for e in settings.postgres_environments}
        if eid not in known:
            raise ValueError(f"Unbekannte Umgebung: {eid}")
        active = next(e for e in settings.postgres_environments if e.environment_id == eid)
        needs_switch = eid != settings.active_postgres_environment_id
        needs_sync = (
            str(settings.embedding_model) != str(active.embedding_model or settings.embedding_model)
            or int(settings.chunk_size) != int(active.chunk_size or settings.chunk_size)
            or int(settings.chunk_overlap)
            != int(active.chunk_overlap if active.chunk_overlap is not None else settings.chunk_overlap)
        )
        if needs_switch or needs_sync:
            from .dependencies import get_ingest_service

            updated = settings.model_copy(update={"active_postgres_environment_id": eid})
            await get_ingest_service().save_settings(updated)
            return self._chat.get_settings()
        return settings

    async def start_run(
        self,
        *,
        questions: list[BatchQuestion],
        file_name: str,
        evaluate_answers: bool,
        language: str | None,
        chat_override: dict[str, Any] | None = None,
        eval_judge: dict[str, Any] | None = None,
        settings_id: str | None = None,
        settings_name: str = "",
        environment_id: str | None = None,
        family_run_id: str | None = None,
        family_instance_index: int | None = None,
        family_instance_total: int | None = None,
        start_execute: bool = True,
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        try:
            settings = await self._activate_environment_if_needed(environment_id)
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Umgebung konnte nicht aktiviert werden: {exc}") from exc
        env = settings.get_active_postgres()
        base_chat = self._chat.get_chat_settings()

        preset: dict[str, Any] | None = None
        if settings_id:
            preset = self._db.get_batch_test_settings(settings_id)
            if preset:
                settings_name = settings_name or preset.get("name") or ""
                if chat_override is None:
                    chat_override = preset.get("chatSettings")
                if eval_judge is None:
                    eval_judge = preset.get("evalJudge")

        chat_norm = normalize_chat_override(chat_override, base_chat)
        judge_norm = normalize_eval_judge(eval_judge)
        snapshot = build_run_settings_snapshot(
            chat_settings=chat_norm,
            eval_judge=judge_norm,
            app_settings=settings,
            evaluate_answers=evaluate_answers,
            language=language if language in ("de", "en") else None,
            family_run_id=family_run_id,
            family_instance_index=family_instance_index,
            family_instance_total=family_instance_total,
        )

        run = BatchTestRun(
            run_id=run_id,
            status="queued",
            created_at=_utcnow_iso(),
            file_name=file_name,
            evaluate_answers=evaluate_answers,
            language=language if language in ("de", "en") else None,
            total=len(questions),
            message="Warteschlange …",
            llm_model=str(chat_norm.get("llmModel") or base_chat.llm_model),
            environment_id=env.environment_id,
            environment_name=env.name or env.environment_id,
            settings_id=settings_id,
            settings_name=settings_name,
            settings_snapshot=snapshot,
            family_run_id=family_run_id,
            family_instance_index=family_instance_index,
            family_instance_total=family_instance_total,
        )
        async with _LOCK:
            _RUNS[run_id] = run
            if len(_RUNS) > _MAX_RUNS:
                oldest = sorted(_RUNS.values(), key=lambda r: r.created_at)[: len(_RUNS) - _MAX_RUNS]
                for old in oldest:
                    if old.status in ("done", "error", "cancelled"):
                        _RUNS.pop(old.run_id, None)

        self._persist(run)
        if start_execute:
            asyncio.create_task(self._execute(run_id, questions))
        return run.to_public_dict(include_results=False)

    async def start_family_run(
        self,
        *,
        questions: list[BatchQuestion],
        file_name: str,
        evaluate_answers: bool,
        language: str | None,
        family_id: str,
        chat_override: dict[str, Any] | None = None,
        eval_judge: dict[str, Any] | None = None,
        settings_id: str | None = None,
        settings_name: str = "",
    ) -> dict[str, Any]:
        """Startet sequentiell einen Bulk-Test für jede Instanz der Familie."""
        settings = self._chat.get_settings()
        fid = (family_id or "").strip()
        instances = settings.list_family_instances(fid)
        if not instances:
            raise ValueError(f"Keine Instanzen für Familie: {fid}")
        family_run_id = str(uuid.uuid4())
        _FAMILY_CANCEL[family_run_id] = False
        # Erste Instanz sofort anlegen und zurückgeben; Rest in Hintergrund-Sequenz
        first = await self.start_run(
            questions=questions,
            file_name=file_name,
            evaluate_answers=evaluate_answers,
            language=language,
            chat_override=chat_override,
            eval_judge=eval_judge,
            settings_id=settings_id,
            settings_name=settings_name,
            environment_id=instances[0].environment_id,
            family_run_id=family_run_id,
            family_instance_index=1,
            family_instance_total=len(instances),
            start_execute=False,
        )
        asyncio.create_task(
            self._execute_family_sequence(
                family_run_id=family_run_id,
                instance_ids=[e.environment_id for e in instances],
                first_run_id=str(first["runId"]),
                questions=questions,
                file_name=file_name,
                evaluate_answers=evaluate_answers,
                language=language,
                chat_override=chat_override,
                eval_judge=eval_judge,
                settings_id=settings_id,
                settings_name=settings_name,
            )
        )
        return {
            **first,
            "familyRunId": family_run_id,
            "familyInstanceTotal": len(instances),
            "runAllInstances": True,
        }

    async def _execute_family_sequence(
        self,
        *,
        family_run_id: str,
        instance_ids: list[str],
        first_run_id: str,
        questions: list[BatchQuestion],
        file_name: str,
        evaluate_answers: bool,
        language: str | None,
        chat_override: dict[str, Any] | None,
        eval_judge: dict[str, Any] | None,
        settings_id: str | None,
        settings_name: str,
    ) -> None:
        total = len(instance_ids)
        current_run_id = first_run_id
        for idx, env_id in enumerate(instance_ids, start=1):
            if _FAMILY_CANCEL.get(family_run_id):
                run = _RUNS.get(current_run_id)
                if run and run.status in ("queued", "running"):
                    run.cancel_requested = True
                break
            if idx > 1:
                started = await self.start_run(
                    questions=questions,
                    file_name=file_name,
                    evaluate_answers=evaluate_answers,
                    language=language,
                    chat_override=chat_override,
                    eval_judge=eval_judge,
                    settings_id=settings_id,
                    settings_name=settings_name,
                    environment_id=env_id,
                    family_run_id=family_run_id,
                    family_instance_index=idx,
                    family_instance_total=total,
                    start_execute=False,
                )
                current_run_id = str(started["runId"])
            await self._execute(current_run_id, questions)
            run = _RUNS.get(current_run_id)
            if run is None or run.status in ("error", "cancelled") or run.cancel_requested:
                _FAMILY_CANCEL[family_run_id] = True
                break
            if _FAMILY_CANCEL.get(family_run_id):
                break
        _FAMILY_CANCEL.pop(family_run_id, None)

    async def cancel_run(self, run_id: str) -> bool:
        run = _RUNS.get(run_id)
        if run is None:
            # bereits persisted / fertig
            existing = self._db.get_batch_test_run(run_id, include_results=False)
            return existing is not None
        run.cancel_requested = True
        if run.family_run_id:
            _FAMILY_CANCEL[run.family_run_id] = True
        if run.status in ("queued", "running"):
            run.message = "Abbruch angefordert …"
            self._persist(run)
        return True

    def _apply_chat_override(self, override: dict[str, Any]) -> ChatSettings:
        current = self._chat.get_chat_settings()
        candidate_raw = override.get("retrievalCandidateK", current.retrieval_candidate_k)
        candidate_k: int | None
        if candidate_raw is None or candidate_raw == "":
            candidate_k = None
        else:
            try:
                candidate_k = max(1, int(candidate_raw))
            except (TypeError, ValueError):
                candidate_k = current.retrieval_candidate_k
        updated = current.model_copy(
            update={
                "temperature": float(override.get("temperature", current.temperature)),
                "max_tokens": int(override.get("maxTokens", current.max_tokens)),
                "top_k": int(override.get("topK", current.top_k)),
                "rerank_similarity_weight": float(
                    override.get("rerankSimilarityWeight", current.rerank_similarity_weight)
                ),
                "rerank_lexical_weight": float(
                    override.get("rerankLexicalWeight", current.rerank_lexical_weight)
                ),
                "rerank_numeric_weight": float(
                    override.get("rerankNumericWeight", current.rerank_numeric_weight)
                ),
                "retrieval_candidate_k": candidate_k,
                "system_prompt": str(override.get("systemPrompt", current.system_prompt)),
                "llm_api_key": str(override.get("llmApiKey", current.llm_api_key)),
                "llm_base_url": str(override.get("llmBaseUrl", current.llm_base_url)),
                "llm_model": str(override.get("llmModel", current.llm_model)),
            }
        )
        # Nur in-memory für den Lauf (kein persist), Restore danach
        self._chat._chat_settings = updated
        return updated

    async def _execute(self, run_id: str, questions: list[BatchQuestion]) -> None:
        run = _RUNS.get(run_id)
        if run is None:
            return
        run.status = "running"
        run.message = "Fragen werden beantwortet …"
        self._persist(run)
        results: list[BatchItemResult] = []
        snapshot_chat = self._chat.get_chat_settings().model_copy(deep=True)
        chat_override = (run.settings_snapshot or {}).get("chatSettings") or {}
        judge_cfg = normalize_eval_judge((run.settings_snapshot or {}).get("evalJudge"))
        try:
            applied = self._apply_chat_override(chat_override)
            run.llm_model = applied.llm_model
            # Effektive Settings nach Override nochmals festhalten
            run.settings_snapshot = build_run_settings_snapshot(
                chat_settings=normalize_chat_override(
                    (run.settings_snapshot or {}).get("chatSettings"),
                    applied,
                ),
                eval_judge=judge_cfg,
                app_settings=self._chat.get_settings(),
                evaluate_answers=run.evaluate_answers,
                language=run.language,
                family_run_id=run.family_run_id,
                family_instance_index=run.family_instance_index,
                family_instance_total=run.family_instance_total,
            )
            self._persist(run)

            for i, q in enumerate(questions, start=1):
                if run.cancel_requested:
                    run.status = "cancelled"
                    run.message = "Abgebrochen."
                    run.finished_at = _utcnow_iso()
                    run.results = results
                    run.summary = build_summary(results, had_judge=False)
                    self._persist(run)
                    return

                run.current = i
                run.progress = int(((i - 1) / max(1, len(questions))) * (80 if run.evaluate_answers else 100))
                prefix = ""
                if run.family_instance_index and run.family_instance_total:
                    prefix = f"Instanz {run.family_instance_index}/{run.family_instance_total} · "
                run.message = f"{prefix}Frage {i}/{len(questions)}: {q.id}"
                if i == 1 or i % 3 == 0:
                    self._persist(run)

                err = ""
                answer = ""
                metrics: dict[str, Any] = {}
                chunks: list[dict[str, Any]] = []
                try:
                    req = ChatRequest(
                        message=q.question,
                        history=[],
                        language=run.language,  # type: ignore[arg-type]
                        clientSource="admin-bulk-test",
                    )
                    resp = await self._chat.chat(req)
                    answer = resp.answer or ""
                    metrics = dict(resp.metrics or {})
                    chunks = [c for c in (resp.context_chunks or []) if isinstance(c, dict)]
                except Exception as exc:
                    err = str(exc)
                    _logger.exception("batch test question %s", q.id)

                results.append(
                    BatchItemResult(
                        row_no=i,
                        question_id=q.id,
                        question_type=q.type,
                        question=q.question,
                        ground_truth=q.answer_field or "",
                        answer=answer,
                        error=err,
                        latency_ms=_as_float(metrics.get("elapsedMs")),
                        prompt_tokens=_as_float(metrics.get("promptTokens")),
                        completion_tokens=_as_float(metrics.get("completionTokens")),
                        total_tokens=_as_float(metrics.get("totalTokens")),
                        tokens_per_second=_as_float(metrics.get("tokensPerSecond")),
                        chunk_count=len(chunks),
                        chunks_summary=_format_chunks_summary(chunks),
                        context_chunks=_serialize_context_chunks(chunks),
                    )
                )
                setattr(results[-1], "_chunks_full", _format_chunks_full(chunks))

            if run.evaluate_answers and results and not run.cancel_requested:
                prefix = ""
                if run.family_instance_index and run.family_instance_total:
                    prefix = f"Instanz {run.family_instance_index}/{run.family_instance_total} · "
                run.message = f"{prefix}LLM-Judge bewertet Antworten …"
                run.progress = 82
                self._persist(run)
                base = str(judge_cfg.get("llmBaseUrl") or "").rstrip("/")
                max_cc = int(judge_cfg.get("maxContextChars") or 12000)
                async with httpx.AsyncClient(base_url=base, timeout=180.0) as jclient:
                    for idx, item in enumerate(results):
                        if run.cancel_requested:
                            break
                        run.current = idx + 1
                        run.progress = 82 + int((idx / max(1, len(results))) * 18)
                        run.message = f"{prefix}Judge {idx + 1}/{len(results)}: {item.question_id}"
                        if idx % 3 == 0:
                            self._persist(run)
                        full_ctx = getattr(item, "_chunks_full", "") or None
                        if full_ctx and len(full_ctx) > max_cc:
                            full_ctx = full_ctx[:max_cc]
                        judged = await _judge_one(
                            jclient,
                            api_key=str(judge_cfg.get("llmApiKey") or "ollama"),
                            model=str(judge_cfg.get("llmModel") or "qwen2.5:latest"),
                            temperature=float(judge_cfg.get("temperature") or 0),
                            max_tokens=int(judge_cfg.get("maxTokens") or 1024),
                            question=item.question,
                            answer=item.answer,
                            context=full_ctx,
                            ground_truth=item.ground_truth or None,
                            question_type=item.question_type,
                            max_retries=int(judge_cfg.get("maxRetries") or 2),
                            retry_sleep_sec=float(judge_cfg.get("retrySleepSec") or 1.5),
                            claim_level=bool(judge_cfg.get("claimLevel", True)),
                        )
                        item.judge_answer_relevance = judged["answer_relevance"]
                        item.judge_context_relevance = judged["context_relevance"]
                        item.judge_groundedness = judged["groundedness"]
                        # AC immer übernehmen, wenn der Judge einen Wert liefert
                        # (auch Subjective, sofern Ground Truth / Score vorhanden).
                        item.judge_answer_correctness = judged["answer_correctness"]
                        item.judge_notes = judged.get("notes") or ""
                        item.judge_error = judged.get("error") or ""

            for item in results:
                if hasattr(item, "_chunks_full"):
                    delattr(item, "_chunks_full")

            run.results = results
            run.summary = build_summary(results, had_judge=run.evaluate_answers)
            if run.family_run_id:
                run.summary = {
                    **(run.summary or {}),
                    "familyRunId": run.family_run_id,
                    "familyInstanceIndex": run.family_instance_index,
                    "familyInstanceTotal": run.family_instance_total,
                }
            if run.cancel_requested:
                run.status = "cancelled"
                run.message = "Abgebrochen."
            else:
                run.status = "done"
                run.progress = 100
                run.message = "Fertig."
            run.finished_at = _utcnow_iso()
            self._persist(run)
        except Exception as exc:
            _logger.exception("batch test run %s failed", run_id)
            run.status = "error"
            run.error = str(exc)
            run.message = f"Fehler: {exc}"
            run.results = results
            run.summary = build_summary(results, had_judge=False)
            run.finished_at = _utcnow_iso()
            self._persist(run)
        finally:
            self._chat._chat_settings = snapshot_chat


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_batch_service: BatchTestService | None = None


def set_batch_test_service(svc: BatchTestService) -> None:
    global _batch_service
    _batch_service = svc


def get_batch_test_service() -> BatchTestService:
    if _batch_service is None:
        raise RuntimeError("BatchTestService not initialized")
    return _batch_service
