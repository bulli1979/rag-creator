#!/usr/bin/env python3
"""Run RAG Q/A generation from a ground-truth file and trigger evaluation.

Designed for invocation like:
  python scripts/evaluation/run_rag_eval_from_ground_truth.py \
    --ground-truth-file outputs/not_questions_ground_truth_input.txt \
    --api-base-url http://127.0.0.1:8000 \
    --system-version legacy_ollama_en_qwen25_7b \
    --outdir outputs/eval_run_not
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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


def get_resilient_session(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


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
                "Expected blocks like 'Question: ... Answer: ...'."
            )
        return pairs

    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix == ".jsonl":
        df = pd.read_json(path, lines=True)
    elif suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file format: {path}")

    columns = [str(c) for c in df.columns]
    q_col = find_column(columns, QUESTION_COLUMNS)
    gt_col = find_column(columns, GROUND_TRUTH_COLUMNS)

    if not q_col or not gt_col:
        raise ValueError(f"Missing question/reference columns in {path}. Columns found: {columns}")

    pairs: list[tuple[str, str]] = []
    for _, row in df[[q_col, gt_col]].iterrows():
        q = str(row[q_col]).replace("\xa0", " ").strip()
        gt = str(row[gt_col]).replace("\xa0", " ").strip()
        if not q or q.lower() == "nan" or not gt or gt.lower() == "nan":
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


def write_ground_truth_csv(path: Path, pairs: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "ground_truth"])
        writer.writeheader()
        for question, ground_truth in pairs:
            writer.writerow({"question": question, "ground_truth": ground_truth})


def write_generated_qa_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = ["system_version", "question", "answer", "context", "latency_ms"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_evaluator(
    evaluator_script: Path,
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
        str(evaluator_script),
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

    print(f"\nTriggering evaluator: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RAG answers from question/ground-truth file and run evaluator."
    )
    parser.add_argument(
        "--ground-truth-file",
        type=Path,
        required=True,
        help="Path to txt/md (Question: ... Answer: ...) or csv/jsonl/xlsx file.",
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
        help="Language forwarded to /api/chat. Empty string to omit.",
    )
    parser.add_argument(
        "--system-version",
        default="legacy_ollama_en_qwen25_7b",
        help="Identifier for the configuration being evaluated.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("outputs/eval_run_not"),
        help="Output directory.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=90,
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of questions to process (0 = all).",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="Skip running evaluate_fragerunden_gemini.py after generation.",
    )
    parser.add_argument(
        "--eval-base-url",
        default="https://api.openai.com/v1",
        help="Judge LLM base URL.",
    )
    parser.add_argument(
        "--eval-model",
        default="gpt-4o-mini",
        help="Judge model name.",
    )
    parser.add_argument(
        "--eval-temperature",
        type=float,
        default=0.0,
        help="Judge temperature.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    evaluator_script = script_dir / "evaluate_fragerunden_gemini.py"

    if not evaluator_script.exists() and not args.skip_eval:
        raise FileNotFoundError(
            f"Evaluator script not found at expected location: {evaluator_script}"
        )

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)

    pairs = load_ground_truth_pairs(args.ground_truth_file)
    if args.limit > 0:
        pairs = pairs[: args.limit]

    gt_csv = outdir / "questions_ground_truth.csv"
    qa_csv = outdir / "questions_qa.csv"

    write_ground_truth_csv(gt_csv, pairs)

    session = get_resilient_session()
    rows: list[dict[str, Any]] = []
    total = len(pairs)

    print(f"Beginning inference for {total} questions against {args.api_base_url}...")

    for idx, (question, _) in enumerate(pairs, start=1):
        payload: dict[str, Any] = {"message": question, "history": []}
        if args.language:
            payload["language"] = args.language

        t0 = time.perf_counter()
        try:
            resp = session.post(
                f"{args.api_base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=args.timeout_sec,
            )
            resp.raise_for_status()
            data = resp.json()
            latency = round((time.perf_counter() - t0) * 1000, 2)
            answer = str(data.get("answer", "")).strip()
            context_chunks = data.get("contextChunks") or []
            context = serialize_context_chunks(context_chunks)
        except Exception as exc:
            latency = round((time.perf_counter() - t0) * 1000, 2)
            answer = f"RAG request failed: {exc}"
            context = ""

        rows.append(
            {
                "system_version": args.system_version,
                "question": question,
                "answer": answer,
                "context": context,
                "latency_ms": latency,
            }
        )
        print(f"[{idx}/{total}] Latency: {latency}ms")

    write_generated_qa_csv(qa_csv, rows)

    print(f"\nGround truth CSV written to: {gt_csv}")
    print(f"Generated QA CSV written to: {qa_csv}")

    if args.skip_eval:
        print("Skipping evaluation as requested (--skip-eval).")
        return

    run_evaluator(
        evaluator_script=evaluator_script,
        generated_qa_csv=qa_csv,
        ground_truth_csv=gt_csv,
        outdir=outdir,
        base_url=args.eval_base_url,
        model=args.eval_model,
        temperature=args.eval_temperature,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()