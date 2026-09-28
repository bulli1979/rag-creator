"""Claim-Level-Bewertung (RAGChecker-Idee) für Groundedness und Answer Correctness.

Ablauf:
1) Antwort (und ggf. Ground Truth) in atomare Claims zerlegen + Entailment prüfen
2) Groundedness = Anteil Antwort-Claims, die vom Context gestützt werden
3) AC = F1 aus Precision (Antwort-Claims ⊆ GT) und Recall (GT-Claims ⊆ Antwort)
"""

from __future__ import annotations

from typing import Any


def _clamp01(value: Any) -> float | None:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n < 0.0:
        return 0.0
    if n > 1.0:
        return 1.0
    return n


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in ("true", "yes", "y", "1", "entailed", "supported"):
        return True
    if s in ("false", "no", "n", "0", "not_entailed", "unsupported", "contradicted"):
        return False
    return None


def _claim_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ("claim", "text", "statement", "fact"):
            raw = item.get(key)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
    return ""


def build_claim_eval_prompt(
    *,
    question: str,
    answer: str,
    context: str | None,
    ground_truth: str | None,
) -> str:
    has_gt = bool((ground_truth or "").strip()) and (ground_truth or "").strip() != "[NONE]"
    has_ctx = bool((context or "").strip()) and (context or "").strip() != "[NONE]"
    gt_block = (
        "Also extract gt_claims from Ground truth. "
        "For each gt claim set supported_by_answer true/false "
        "(true only if the Answer entails that claim).\n"
        if has_gt
        else "Set gt_claims to [].\n"
    )
    ctx_rule = (
        "For each answer claim set supported_by_context true/false "
        "(true only if Context alone entails the claim; no outside knowledge).\n"
        if has_ctx
        else "Context is [NONE]: set supported_by_context false for every answer claim that asserts a fact.\n"
    )
    gt_rule = (
        "For each answer claim set supported_by_gt true/false "
        "(true only if Ground truth entails the claim).\n"
        if has_gt
        else "Set supported_by_gt to null for all answer claims.\n"
    )
    return (
        "You are a claim-level fact checker for a RAG system (RAGChecker-style).\n"
        "Decompose texts into atomic factual claims (short, verifiable statements).\n"
        "Do NOT invent claims that are not stated. Prefer 2–8 claims per side.\n\n"
        f"{ctx_rule}"
        f"{gt_rule}"
        f"{gt_block}"
        "Return ONLY a JSON object (double quotes, no markdown fences):\n"
        "{\n"
        '  "answer_claims": [\n'
        '    {"claim":"...","supported_by_context":true,"supported_by_gt":true}\n'
        "  ],\n"
        '  "gt_claims": [\n'
        '    {"claim":"...","supported_by_answer":true}\n'
        "  ],\n"
        '  "notes":"short summary"\n'
        "}\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:\n{answer}\n\n"
        f"Context:\n{context if context else '[NONE]'}\n\n"
        f"Ground truth:\n{ground_truth if ground_truth else '[NONE]'}\n"
    )


def score_claims_from_payload(
    data: dict[str, Any],
    *,
    has_ground_truth: bool,
    has_context: bool,
) -> dict[str, Any]:
    """Berechnet groundedness + answer_correctness (F1) aus Claim-JSON."""
    answer_raw = data.get("answer_claims") or data.get("answerClaims") or []
    gt_raw = data.get("gt_claims") or data.get("gtClaims") or data.get("ground_truth_claims") or []
    if not isinstance(answer_raw, list):
        answer_raw = []
    if not isinstance(gt_raw, list):
        gt_raw = []

    answer_claims: list[dict[str, Any]] = []
    for item in answer_raw:
        text = _claim_text(item)
        if not text:
            continue
        row = item if isinstance(item, dict) else {}
        answer_claims.append(
            {
                "claim": text,
                "supported_by_context": _as_bool(
                    row.get("supported_by_context", row.get("supportedByContext"))
                ),
                "supported_by_gt": _as_bool(
                    row.get("supported_by_gt", row.get("supportedByGt", row.get("supported_by_ground_truth")))
                ),
            }
        )

    gt_claims: list[dict[str, Any]] = []
    for item in gt_raw:
        text = _claim_text(item)
        if not text:
            continue
        row = item if isinstance(item, dict) else {}
        gt_claims.append(
            {
                "claim": text,
                "supported_by_answer": _as_bool(
                    row.get("supported_by_answer", row.get("supportedByAnswer"))
                ),
            }
        )

    groundedness: float | None
    if not has_context:
        # Kein Context: faktische Antwort-Claims gelten als ungestützt
        if answer_claims:
            groundedness = 0.0
        else:
            groundedness = 0.0
    elif not answer_claims:
        groundedness = 1.0  # keine Behauptungen → nichts halluziniert
    else:
        flags = [c["supported_by_context"] for c in answer_claims if c["supported_by_context"] is not None]
        groundedness = (sum(1 for f in flags if f) / len(flags)) if flags else None

    answer_correctness: float | None = None
    precision: float | None = None
    recall: float | None = None
    if has_ground_truth:
        if answer_claims:
            p_flags = [c["supported_by_gt"] for c in answer_claims if c["supported_by_gt"] is not None]
            precision = (sum(1 for f in p_flags if f) / len(p_flags)) if p_flags else 0.0
        else:
            precision = 1.0 if not gt_claims else 0.0

        if gt_claims:
            r_flags = [c["supported_by_answer"] for c in gt_claims if c["supported_by_answer"] is not None]
            recall = (sum(1 for f in r_flags if f) / len(r_flags)) if r_flags else 0.0
        else:
            recall = 1.0 if not answer_claims else 0.0

        if precision is not None and recall is not None:
            if precision + recall <= 0:
                answer_correctness = 0.0
            else:
                answer_correctness = 2.0 * precision * recall / (precision + recall)

    notes = str(data.get("notes") or "").strip()
    detail_parts = [
        f"claimsA={len(answer_claims)}",
        f"claimsGT={len(gt_claims)}",
    ]
    if groundedness is not None:
        detail_parts.append(f"GR={groundedness:.3f}")
    if precision is not None:
        detail_parts.append(f"P={precision:.3f}")
    if recall is not None:
        detail_parts.append(f"R={recall:.3f}")
    if answer_correctness is not None:
        detail_parts.append(f"F1={answer_correctness:.3f}")
    detail = "Claim-Level " + " ".join(detail_parts)
    if notes:
        detail = f"{notes} | {detail}"

    unsupported = [
        c["claim"]
        for c in answer_claims
        if c.get("supported_by_context") is False
    ][:3]
    missing = [
        c["claim"]
        for c in gt_claims
        if c.get("supported_by_answer") is False
    ][:3]
    extras: list[str] = []
    if unsupported:
        extras.append("ungestützt: " + "; ".join(unsupported))
    if missing:
        extras.append("fehlend: " + "; ".join(missing))
    if extras:
        detail = detail + " | " + " · ".join(extras)

    return {
        "groundedness": _clamp01(groundedness),
        "answer_correctness": _clamp01(answer_correctness),
        "claimPrecision": _clamp01(precision),
        "claimRecall": _clamp01(recall),
        "answerClaimCount": len(answer_claims),
        "gtClaimCount": len(gt_claims),
        "notes": detail[:800],
        "answerClaims": answer_claims,
        "gtClaims": gt_claims,
    }


def looks_like_claim_payload(data: dict[str, Any]) -> bool:
    return any(
        key in data
        for key in ("answer_claims", "answerClaims", "gt_claims", "gtClaims", "ground_truth_claims")
    )
