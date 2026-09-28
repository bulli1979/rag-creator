"""
LLM-as-a-Judge für Batch-Antworten (OpenAI-kompatibles Chat-Completions-API).

Rubriken + Chain-of-Thought: erst kurze Begründung, dann Scores
answer_relevance, context_relevance, groundedness, answer_correctness (0.0–1.0).
"""

from __future__ import annotations

import ast
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

_ROOT = Path(__file__).resolve().parents[1]
_DOC_API = _ROOT / "documentApi"
if str(_DOC_API) not in sys.path:
    sys.path.insert(0, str(_DOC_API))

try:
    from app.claim_judge import build_claim_eval_prompt, score_claims_from_payload
except Exception:  # noqa: BLE001
    build_claim_eval_prompt = None  # type: ignore[assignment]
    score_claims_from_payload = None  # type: ignore[assignment]


def build_judge_prompt(
    question: str,
    answer: str,
    context: str | None,
    ground_truth: str | None,
    question_type: str | None,
) -> str:
    qt = (question_type or "").strip()
    has_gt = bool((ground_truth or "").strip()) and (ground_truth or "").strip() != "[NONE]"
    type_hint = ""
    if qt == "Objective":
        type_hint = (
            "Question type: objective. "
            "ALWAYS set answer_correctness (0.0–1.0) when ground truth is present."
        )
    elif qt == "Subjective":
        type_hint = (
            "Question type: subjective. ALWAYS set answer_relevance. "
            "Set answer_correctness only if ground truth is present; otherwise null."
        )
    ac_rule = (
        "- answer_correctness: REQUIRED number 0.0–1.0 (ground truth is present).\n"
        if has_gt
        else "- answer_correctness: MUST be null (no ground truth).\n"
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
        "- groundedness: Is the answer supported only by the provided Context (no invented facts)? "
        "Ignore whether it matches ground truth or fully answers the question. "
        "1.0 = fully supported by context; 0.5 = partly supported; 0.0 = mostly hallucinated "
        "or Context is [NONE] while the answer asserts facts.\n"
        "- answer_correctness: Semantic agreement with Ground truth (not exact wording). "
        "Ignore style and citations. "
        "1.0 = key facts match; 0.5 = partial; 0.0 = contradicts or misses key facts. "
        "null if Ground truth is [NONE].\n\n"
        "## Process (required)\n"
        "1) Write brief reasoning (3–8 sentences): cover answer_relevance, context_relevance, "
        "groundedness, and answer_correctness (if applicable). Mention decisive evidence.\n"
        "2) Then output a single JSON object (no markdown fences) with exactly these keys:\n"
        '{"answer_relevance":0.0,"context_relevance":0.0,'
        '"groundedness":0.0,"answer_correctness":0.0,"notes":""}\n'
        "Rules:\n"
        "- JSON MUST use double quotes for all keys and string values (not single quotes).\n"
        "- answer_relevance is REQUIRED (never null).\n"
        f"{ac_rule}"
        "- notes: one short sentence summarizing the main issue or strength (max ~200 chars).\n"
        "- Be conservative: when uncertain, prefer the lower score.\n"
        f"{type_hint}\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:\n{answer}\n\n"
        f"Context:\n{context if context else '[NONE]'}\n\n"
        f"Ground truth:\n{ground_truth if ground_truth else '[NONE]'}\n"
    )


def clamp_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0.0:
        return 0.0
    if numeric > 1.0:
        return 1.0
    return numeric


def extract_json_from_text(text: str) -> dict[str, Any]:
    """JSON aus Judge-Antwort; tolerant gegenüber Single-Quotes / Trailing-Commas."""
    raw = (text or "").strip()
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            chunk = part.strip()
            if chunk.lower().startswith("json"):
                chunk = chunk[4:].strip()
            if "{" in chunk:
                raw = chunk
                break
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model response did not contain JSON object")
    blob = raw[start : end + 1]

    def repair(s: str) -> str:
        s = re.sub(r",\s*}", "}", s)
        s = re.sub(r",\s*]", "]", s)
        s = re.sub(r"\bNone\b", "null", s)
        s = re.sub(r"\bTrue\b", "true", s)
        s = re.sub(r"\bFalse\b", "false", s)
        s = re.sub(r'([{,]\s*)([A-Za-z_][\w]*)\s*:', r'\1"\2":', s)
        return s

    def single_to_double(blob_in: str) -> str:
        out: list[str] = []
        i = 0
        n = len(blob_in)
        in_single = False
        in_double = False
        while i < n:
            ch = blob_in[i]
            if in_double:
                out.append(ch)
                if ch == "\\" and i + 1 < n:
                    out.append(blob_in[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    in_double = False
                i += 1
                continue
            if in_single:
                if ch == "\\" and i + 1 < n:
                    nxt = blob_in[i + 1]
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

    candidates = [blob, repair(blob), repair(single_to_double(blob)), single_to_double(repair(blob))]
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
            last_err = ValueError("JSON is not an object")
        except Exception as exc:  # noqa: BLE001
            last_err = exc

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

    raise ValueError(f"invalid judge JSON: {last_err}")


def _notes_from(parsed: dict[str, Any], raw_content: str) -> str:
    notes = str(parsed.get("notes") or "").strip()
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


def judge_one_http(
    client: httpx.Client,
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
    max_retries: int,
    retry_sleep_sec: float,
    claim_level: bool = True,
) -> dict[str, Any]:
    """POST …/chat/completions (OpenAI-kompatibel, Client.base_url = …/v1)."""
    url = "/chat/completions"
    prompt = build_judge_prompt(question, answer, context, ground_truth, question_type)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def _post(user_prompt: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "First reason briefly if needed, then end with a single JSON object. "
                        "No markdown fences. Use double quotes only."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
        }
        last_err: Exception | None = None
        for attempt in range(1, max(1, max_retries) + 1):
            try:
                r = client.post(url, headers=headers, json=body)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:1500]}")
                payload = r.json()
                choices = payload.get("choices") or []
                if not choices:
                    raise RuntimeError("No choices in completion response")
                content = (choices[0].get("message") or {}).get("content") or "{}"
                content = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
                content = re.sub(r"\s*```\s*$", "", content)
                parsed = extract_json_from_text(content)
                return {"parsed": parsed, "content": content, "error": ""}
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                if attempt < max_retries:
                    time.sleep(max(0.0, retry_sleep_sec))
        return {"parsed": None, "content": "", "error": str(last_err) if last_err else "unknown"}

    first = _post(prompt)
    if not first["parsed"]:
        return {
            "answer_relevance": None,
            "context_relevance": None,
            "groundedness": None,
            "answer_correctness": None,
            "notes": "",
            "error": first["error"],
        }

    parsed = first["parsed"]
    result = {
        "answer_relevance": clamp_score(parsed.get("answer_relevance")),
        "context_relevance": clamp_score(parsed.get("context_relevance")),
        "groundedness": clamp_score(parsed.get("groundedness")),
        "answer_correctness": clamp_score(parsed.get("answer_correctness")),
        "notes": _notes_from(parsed, first["content"]),
        "error": "",
    }

    if not claim_level or build_claim_eval_prompt is None or score_claims_from_payload is None:
        return result

    has_gt = bool((ground_truth or "").strip()) and (ground_truth or "").strip() != "[NONE]"
    has_ctx = bool((context or "").strip()) and (context or "").strip() != "[NONE]"
    claim_prompt = build_claim_eval_prompt(
        question=question,
        answer=answer,
        context=context,
        ground_truth=ground_truth if has_gt else None,
    )
    second = _post(claim_prompt)
    if not second["parsed"]:
        result["notes"] = (
            (result["notes"] + " | " if result["notes"] else "")
            + f"Claim-Pass fehlgeschlagen: {second['error']}"
        )[:800]
        return result

    scored = score_claims_from_payload(
        second["parsed"],
        has_ground_truth=has_gt,
        has_context=has_ctx,
    )
    if scored.get("groundedness") is not None:
        result["groundedness"] = scored["groundedness"]
    if has_gt and scored.get("answer_correctness") is not None:
        result["answer_correctness"] = scored["answer_correctness"]
    elif not has_gt:
        result["answer_correctness"] = None
    claim_notes = scored.get("notes") or ""
    if claim_notes:
        result["notes"] = (
            f"{result['notes']} | {claim_notes}" if result["notes"] else claim_notes
        )[:800]
    return result


def resolve_eval_judge_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """evalJudge aus Config, sonst Fallback chatSettings."""
    ej = cfg.get("evalJudge") if isinstance(cfg.get("evalJudge"), dict) else {}
    chat = cfg.get("chatSettings") if isinstance(cfg.get("chatSettings"), dict) else {}
    return {
        "llmBaseUrl": str(ej.get("llmBaseUrl") or chat.get("llmBaseUrl") or "http://localhost:11434/v1").rstrip(
            "/"
        ),
        "llmApiKey": str(ej.get("llmApiKey") if ej.get("llmApiKey") is not None else chat.get("llmApiKey") or ""),
        "llmModel": str(ej.get("llmModel") or "qwen2.5:latest"),
        "temperature": float(ej.get("temperature") if ej.get("temperature") is not None else 0.0),
        "maxTokens": int(ej.get("maxTokens") or 1024),
        "maxContextChars": int(ej.get("maxContextChars") or 12000),
        "maxRetries": int(ej.get("maxRetries") or 2),
        "retrySleepSec": float(ej.get("retrySleepSec") or 1.5),
        "claimLevel": bool(ej["claimLevel"]) if "claimLevel" in ej else True,
        "requestTimeoutSeconds": float(ej.get("requestTimeoutSeconds") or cfg.get("requestTimeoutSeconds") or 120),
    }
