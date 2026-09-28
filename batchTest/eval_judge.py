"""
LLM-as-a-Judge für Batch-Antworten (OpenAI-kompatibles Chat-Completions-API).

Orientierung an der Idee von evaluate_fragerunden.py (RAG-Creator): Metriken
answer_relevance, context_relevance, groundedness, answer_correctness auf Skala 0.0–1.0.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx


def build_judge_prompt(
    question: str,
    answer: str,
    context: str | None,
    ground_truth: str | None,
    question_type: str | None,
) -> str:
    qt = (question_type or "").strip()
    type_hint = ""
    if qt == "Objective":
        type_hint = "Question type: objective — use answer_correctness vs. ground truth when provided."
    elif qt == "Subjective":
        type_hint = (
            "Question type: subjective — if no ground truth, set answer_correctness to null "
            "(do not invent a reference)."
        )
    return (
        "You are a strict evaluator for a RAG assistant at a scientific observatory.\n"
        "Score each metric from 0.0 to 1.0. Return ONLY JSON with this schema:\n"
        "{\n"
        '  "answer_relevance": number,\n'
        '  "context_relevance": number|null,\n'
        '  "groundedness": number|null,\n'
        '  "answer_correctness": number|null,\n'
        '  "notes": string\n'
        "}\n\n"
        "Scoring guidance:\n"
        "- answer_relevance: Does the answer directly and usefully address the question?\n"
        "- context_relevance: Are provided context snippets relevant to the question? null if no context.\n"
        "- groundedness: Is the answer supported by the provided context? null if no context.\n"
        "- answer_correctness: Semantic factual alignment with ground truth; null if no ground truth.\n\n"
        f"{type_hint}\n\n"
        "Constraints: be conservative; prefer lower scores when uncertain; notes max 240 chars.\n\n"
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
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response did not contain JSON object")
    return json.loads(text[start : end + 1])


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
) -> dict[str, Any]:
    """POST …/chat/completions (OpenAI-kompatibel, Client.base_url = …/v1)."""
    url = "/chat/completions"
    prompt = build_judge_prompt(question, answer, context, ground_truth, question_type)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": "Return valid JSON only, no markdown."},
            {"role": "user", "content": prompt},
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
            return {
                "answer_relevance": clamp_score(parsed.get("answer_relevance")),
                "context_relevance": clamp_score(parsed.get("context_relevance")),
                "groundedness": clamp_score(parsed.get("groundedness")),
                "answer_correctness": clamp_score(parsed.get("answer_correctness")),
                "notes": str(parsed.get("notes", "")).strip()[:240],
                "error": "",
            }
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < max_retries:
                time.sleep(max(0.0, retry_sleep_sec))
    return {
        "answer_relevance": None,
        "context_relevance": None,
        "groundedness": None,
        "answer_correctness": None,
        "notes": "",
        "error": str(last_err) if last_err else "unknown",
    }


def resolve_eval_judge_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """evalJudge aus Config, sonst Fallback chatSettings."""
    ej = cfg.get("evalJudge") if isinstance(cfg.get("evalJudge"), dict) else {}
    chat = cfg.get("chatSettings") if isinstance(cfg.get("chatSettings"), dict) else {}
    return {
        "llmBaseUrl": str(ej.get("llmBaseUrl") or chat.get("llmBaseUrl") or "http://localhost:11434/v1").rstrip(
            "/"
        ),
        "llmApiKey": str(ej.get("llmApiKey") if ej.get("llmApiKey") is not None else chat.get("llmApiKey") or ""),
        "llmModel": str(ej.get("llmModel") or chat.get("llmModel") or "llama3.2"),
        "temperature": float(ej.get("temperature") if ej.get("temperature") is not None else 0.0),
        "maxTokens": int(ej.get("maxTokens") or 512),
        "maxContextChars": int(ej.get("maxContextChars") or 12000),
        "maxRetries": int(ej.get("maxRetries") or 2),
        "retrySleepSec": float(ej.get("retrySleepSec") or 1.5),
        "requestTimeoutSeconds": float(ej.get("requestTimeoutSeconds") or cfg.get("requestTimeoutSeconds") or 120),
    }
