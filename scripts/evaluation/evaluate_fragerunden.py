#!/usr/bin/env python3
"""Evaluate extracted Fragerunden Q/A pairs per RAG system version.

This script consumes outputs/fragerunden_qa_long.csv (or similar) and produces:
- Row-level metric scores per question/answer/system
- Aggregated summary per system version

Metrics:
- answer_relevance: How well answer addresses the question
- context_relevance: How relevant retrieved context is (requires context column)
- groundedness: How well answer is supported by context (requires context column)
- answer_correctness: How close answer is to ground truth (requires ground-truth file)

The evaluator uses an OpenAI-compatible chat-completions endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from openai import OpenAI

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


DEFAULT_DOTENV_PATH = Path(os.environ.get("EVAL_DOTENV_PATH", ".env")).expanduser()


QUESTION_COLUMNS = ["question", "objective fragen", "frage", "prompt"]
ANSWER_COLUMNS = ["answer", "antwort", "response", "model_answer"]
CONTEXT_COLUMNS = ["context", "contexts", "retrieved_context", "retrieved_contexts", "source_text"]
GROUND_TRUTH_COLUMNS = ["ground_truth", "reference_answer", "gold_answer", "answer"]


def normalize_col(name: str) -> str:
    return " ".join(str(name).replace("\xa0", " ").strip().lower().split())


def find_column(columns: list[str], aliases: list[str]) -> str | None:
    lookup = {normalize_col(c): c for c in columns}
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]
    return None


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file format: {path}")


@dataclass
class EvalConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float
    max_retries: int
    retry_sleep_sec: float


def build_judge_prompt(
    question: str,
    answer: str,
    context: str | None,
    ground_truth: str | None,
) -> str:
    return (
        "You are a strict evaluator for a scientific observatory RAG assistant.\n"
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
        "- context_relevance: Are provided context snippets relevant to the question? Use null if no context is provided.\n"
        "- groundedness: Is the answer supported by provided context? Use null if no context is provided.\n"
        "- answer_correctness: Semantic correctness vs ground truth. Use null if no ground truth is provided.\n\n"
        "Constraints:\n"
        "- Be strict and conservative.\n"
        "- Prefer lower scores when uncertain.\n"
        "- Notes max 240 chars.\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:\n{answer}\n\n"
        f"Context:\n{context if context else '[NONE]'}\n\n"
        f"Ground Truth:\n{ground_truth if ground_truth else '[NONE]'}\n"
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


def judge_one(
    client: OpenAI,
    cfg: EvalConfig,
    question: str,
    answer: str,
    context: str | None,
    ground_truth: str | None,
) -> dict[str, Any]:
    prompt = build_judge_prompt(
        question=question,
        answer=answer,
        context=context,
        ground_truth=ground_truth,
    )

    last_err: Exception | None = None
    for attempt in range(1, cfg.max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=cfg.model,
                temperature=cfg.temperature,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content or "{}"
            payload = extract_json_from_text(content)
            return {
                "answer_relevance": clamp_score(payload.get("answer_relevance")),
                "context_relevance": clamp_score(payload.get("context_relevance")),
                "groundedness": clamp_score(payload.get("groundedness")),
                "answer_correctness": clamp_score(payload.get("answer_correctness")),
                "notes": str(payload.get("notes", "")).strip()[:240],
            }
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < cfg.max_retries:
                time.sleep(cfg.retry_sleep_sec)

    raise RuntimeError(f"Judge call failed after {cfg.max_retries} attempts: {last_err}")


def prepare_ground_truth_map(ground_truth_path: Path | None) -> dict[str, str]:
    if ground_truth_path is None:
        return {}

    df = read_table(ground_truth_path)
    columns = [str(c) for c in df.columns]

    q_col = find_column(columns, QUESTION_COLUMNS)
    gt_col = find_column(columns, GROUND_TRUTH_COLUMNS)

    if not q_col or not gt_col:
        raise ValueError(
            "Ground truth file must contain question and ground-truth columns. "
            f"Detected columns: {columns}"
        )

    out: dict[str, str] = {}
    for _, row in df[[q_col, gt_col]].iterrows():
        q = str(row[q_col]).replace("\xa0", " ").strip()
        gt = str(row[gt_col]).replace("\xa0", " ").strip()
        if not q or q.lower() == "nan":
            continue
        if not gt or gt.lower() == "nan":
            continue
        out[q] = gt
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Fragerunden Q/A outputs per RAG system version.")
    parser.add_argument("--input", type=Path, required=True, help="Input long-format Q/A file (csv/jsonl/xlsx).")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Optional file with reference answers for answer_correctness metric.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("outputs"),
        help="Output folder for evaluation files.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("EVAL_JUDGE_MODEL", "gpt-4o-mini"),
        help="Judge model name.",
    )
    parser.add_argument("--temperature", type=float, default=0.0, help="Judge temperature.")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retries per row.")
    parser.add_argument("--retry-sleep", type=float, default=1.5, help="Sleep between retries in seconds.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for number of rows to score.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if load_dotenv:
        load_dotenv(DEFAULT_DOTENV_PATH)

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for evaluation.")

    df = read_table(args.input)
    columns = [str(c) for c in df.columns]

    question_col = find_column(columns, QUESTION_COLUMNS)
    answer_col = find_column(columns, ANSWER_COLUMNS)
    context_col = find_column(columns, CONTEXT_COLUMNS)

    if not question_col or not answer_col:
        raise ValueError(
            "Input file must contain question and answer columns. "
            f"Detected columns: {columns}"
        )

    if "system_version" not in df.columns:
        df["system_version"] = "unknown"

    gt_map = prepare_ground_truth_map(args.ground_truth)

    cfg = EvalConfig(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        max_retries=max(1, args.max_retries),
        retry_sleep_sec=max(0.0, args.retry_sleep),
    )

    client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    args.outdir.mkdir(parents=True, exist_ok=True)

    work_df = df.copy()
    if args.limit and args.limit > 0:
        work_df = work_df.head(args.limit)

    records: list[dict[str, Any]] = []

    for idx, row in work_df.iterrows():
        question = str(row.get(question_col, "")).replace("\xa0", " ").strip()
        answer = str(row.get(answer_col, "")).replace("\xa0", " ").strip()

        if not question or question.lower() == "nan":
            continue

        if not answer or answer.lower() == "nan":
            answer = ""

        context_val: str | None = None
        if context_col:
            raw_context = str(row.get(context_col, "")).replace("\xa0", " ").strip()
            if raw_context and raw_context.lower() != "nan":
                context_val = raw_context

        ground_truth = gt_map.get(question)

        judged = judge_one(
            client=client,
            cfg=cfg,
            question=question,
            answer=answer,
            context=context_val,
            ground_truth=ground_truth,
        )

        records.append(
            {
                "row_index": int(idx),
                "system_version": row.get("system_version", "unknown"),
                "sheet_name": row.get("sheet_name", ""),
                "round": row.get("round", ""),
                "question": question,
                "answer": answer,
                "ground_truth": ground_truth,
                **judged,
            }
        )

        if len(records) % 10 == 0:
            print(f"Scored rows: {len(records)}")

    scored_df = pd.DataFrame.from_records(records)

    score_cols = [
        "answer_relevance",
        "context_relevance",
        "groundedness",
        "answer_correctness",
    ]

    if scored_df.empty:
        raise RuntimeError("No rows were scored. Check your input columns and data.")

    summary = (
        scored_df.groupby("system_version", dropna=False)[score_cols]
        .agg(["count", "mean", "std", "min", "max"])
        .round(4)
    )
    summary.columns = ["_".join(c).strip("_") for c in summary.columns.values]
    summary = summary.reset_index()

    rows_path = args.outdir / "fragerunden_eval_rows.csv"
    systems_path = args.outdir / "fragerunden_eval_by_system.csv"

    scored_df.to_csv(rows_path, index=False)
    summary.to_csv(systems_path, index=False)

    print(f"Scored rows: {len(scored_df)}")
    print(f"Systems: {scored_df['system_version'].nunique()}")
    print(f"Row-level output: {rows_path}")
    print(f"System summary output: {systems_path}")


if __name__ == "__main__":
    main()
