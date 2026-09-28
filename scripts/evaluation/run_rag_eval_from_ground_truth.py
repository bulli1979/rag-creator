#!/usr/bin/env python3
"""Run RAG Q/A generation from a ground-truth file and evaluate results.

This script:
1) Reads questions + reference answers from either:
   - plain text lines containing "Question: ... Answer: ..."
   - CSV/JSONL/XLSX files with question + ground-truth columns
2) Sends each question to the local RAG API (/api/chat)
3) Writes:
   - generated Q/A file (for evaluator input)
   - normalized ground-truth file
4) Runs scripts/evaluate_fragerunden.py automatically (optional)

Example:
  python scripts/run_rag_eval_from_ground_truth.py \
    --ground-truth-file outputs/my_questions.txt \
    --api-base-url http://127.0.0.1:8000 \
    --system-version legacy_ollama_en_qwen25_7b
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import requests


QUESTION_COLUMNS = ["question", "frage", "prompt", "objective fragen"]
GROUND_TRUTH_COLUMNS = ["ground_truth", "reference_answer", "gold_answer", "answer", "antwort"]


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
    raise ValueError(f"Unsupported structured file format: {path}")


def parse_question_answer_text(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"(?:^\s*\d+\s+)?Question:\s*(.*?)\s*Answer:\s*(.*?)(?=(?:^\s*\d+\s+)?Question:|\Z)",
        flags=re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )

    records: list[tuple[str, str]] = []
    for match in pattern.finditer(text):
        question = re.sub(r"\s+", " ", match.group(1)).strip()
        answer = re.sub(r"\s+", " ", match.group(2)).strip()
        if question and answer:
            records.append((question, answer))

    if records:
        return records

    # Fallback: line-by-line parser
    records = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = re.search(r"Question:\s*(.*?)\s*Answer:\s*(.*)$", line, flags=re.IGNORECASE)
        if not m:
            continue
        question = re.sub(r"\s+", " ", m.group(1)).strip()
        answer = re.sub(r"\s+", " ", m.group(2)).strip()
        if question and answer:
            records.append((question, answer))
    return records


def load_ground_truth_pairs(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8")
        pairs = parse_question_answer_text(text)
        if not pairs:
            raise ValueError(
                "Could not parse any Question/Answer pairs from text file. "
                "Expected lines with 'Question: ... Answer: ...'."
            )
        return pairs

    df = read_table(path)
    columns = [str(c) for c in df.columns]
    q_col = find_column(columns, QUESTION_COLUMNS)
    gt_col = find_column(columns, GROUND_TRUTH_COLUMNS)

    if not q_col or not gt_col:
        raise ValueError(
            "Structured ground-truth file must contain question and reference-answer columns. "
            f"Detected columns: {columns}"
        )

    pairs: list[tuple[str, str]] = []
    for _, row in df[[q_col, gt_col]].iterrows():
        q = str(row[q_col]).replace("\xa0", " ").strip()
        gt = str(row[gt_col]).replace("\xa0", " ").strip()
        if not q or q.lower() == "nan":
            continue
        if not gt or gt.lower() == "nan":
            continue
        pairs.append((q, gt))

    if not pairs:
        raise ValueError("No valid question/ground-truth rows found.")
    return pairs


def serialize_context_chunks(chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for chunk in chunks:
        source = (
            chunk.get("source")
            or chunk.get("file")
            or chunk.get("filename")
            or chunk.get("file_name")
            or "unknown"
        )
        text = str(chunk.get("text") or chunk.get("content") or "").strip()
        if text:
            blocks.append(f"[{source}]\n{text}")
        else:
            blocks.append(f"[{source}]")
    return "\n---\n".join(blocks)


def query_rag(
    api_base_url: str,
    question: str,
    language: str | None,
    timeout_sec: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"message": question, "history": []}
    if language:
        payload["language"] = language

    response = requests.post(
        f"{api_base_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=timeout_sec,
    )
    response.raise_for_status()
    return response.json()


def write_ground_truth_csv(path: Path, pairs: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "ground_truth"])
        writer.writeheader()
        for question, ground_truth in pairs:
            writer.writerow({"question": question, "ground_truth": ground_truth})


def write_generated_qa_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["system_version", "question", "answer", "context"])
        writer.writeheader()
        writer.writerows(rows)


def run_evaluator(
    repo_root: Path,
    generated_qa_csv: Path,
    ground_truth_csv: Path,
    outdir: Path,
    base_url: str,
    model: str,
    temperature: float,
    limit: int,
) -> None:
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "evaluation" / "evaluate_fragerunden.py"),
        "--input",
        str(generated_qa_csv),
        "--ground-truth",
        str(ground_truth_csv),
        "--outdir",
        str(outdir),
        "--base-url",
        base_url,
        "--model",
        model,
        "--temperature",
        str(temperature),
    ]
    if limit > 0:
        cmd.extend(["--limit", str(limit)])

    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RAG answers from question/ground-truth file and run evaluator."
    )
    parser.add_argument(
        "--ground-truth-file",
        type=Path,
        required=True,
        help="Path to .txt/.md (Question: ... Answer: ...) or csv/jsonl/xlsx with question+ground truth.",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://127.0.0.1:8000",
        help="RAG API base URL.",
    )
    parser.add_argument(
        "--language",
        default="en",
        choices=["en", "de", ""],
        help="Language forwarded to /api/chat. Use empty string to omit.",
    )
    parser.add_argument(
        "--system-version",
        default="legacy_ollama_en_qwen25_7b",
        help="Label written into generated QA rows.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("outputs/eval_run"),
        help="Output directory for generated files and evaluation outputs.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=90,
        help="Timeout per /api/chat request.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit of questions to run (0 = all).",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Only generate QA + ground truth CSVs, do not run evaluate_fragerunden.py.",
    )
    parser.add_argument(
        "--eval-base-url",
        default="https://api.openai.com/v1",
        help="Judge base URL passed to evaluate_fragerunden.py.",
    )
    parser.add_argument(
        "--eval-model",
        default="gpt-4o-mini",
        help="Judge model passed to evaluate_fragerunden.py.",
    )
    parser.add_argument(
        "--eval-temperature",
        type=float,
        default=0.0,
        help="Judge temperature passed to evaluate_fragerunden.py.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    pairs = load_ground_truth_pairs(args.ground_truth_file)
    if args.limit > 0:
        pairs = pairs[: args.limit]

    gt_csv = outdir / "questions_ground_truth.csv"
    qa_csv = outdir / "questions_qa.csv"

    write_ground_truth_csv(gt_csv, pairs)

    rows: list[dict[str, str]] = []
    total = len(pairs)

    for idx, (question, _) in enumerate(pairs, start=1):
        try:
            payload = query_rag(
                api_base_url=args.api_base_url,
                question=question,
                language=args.language if args.language else None,
                timeout_sec=args.timeout_sec,
            )
            answer = str(payload.get("answer", "")).strip()
            context_chunks = payload.get("contextChunks") or []
            context = serialize_context_chunks(context_chunks)
        except Exception as exc:  # noqa: BLE001
            answer = f"RAG request failed: {exc}"
            context = ""

        rows.append(
            {
                "system_version": args.system_version,
                "question": question,
                "answer": answer,
                "context": context,
            }
        )
        print(f"[{idx}/{total}] completed")

    write_generated_qa_csv(qa_csv, rows)

    print(f"Ground truth CSV: {gt_csv}")
    print(f"Generated QA CSV: {qa_csv}")

    if args.skip_eval:
        print("Skipped evaluator (--skip-eval).")
        return

    run_evaluator(
        repo_root=repo_root,
        generated_qa_csv=qa_csv,
        ground_truth_csv=gt_csv,
        outdir=outdir,
        base_url=args.eval_base_url,
        model=args.eval_model,
        temperature=args.eval_temperature,
        limit=args.limit,
    )

    print("Evaluation finished.")
    print(f"Row-level output: {outdir / 'fragerunden_eval_rows.csv'}")
    print(f"System summary output: {outdir / 'fragerunden_eval_by_system.csv'}")


if __name__ == "__main__":
    main()
