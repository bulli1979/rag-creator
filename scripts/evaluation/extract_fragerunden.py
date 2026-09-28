#!/usr/bin/env python3
"""Extract questions and answers from a multi-sheet Fragerunden workbook.

Each answer sheet is treated as one RAG system/version. The script produces:
- Long format: one row per (sheet_version, question, answer)
- Wide format: one row per question, one answer column per sheet_version

Usage:
    python scripts/extract_fragerunden.py \
        --input "Fragerunden .xlsx" \
        --outdir "outputs"
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


QUESTION_ALIASES = {
    "question",
    "questions",
    "frage",
    "fragen",
    "objective fragen",
    "objectivefrage",
    "objective_fragen",
}

ANSWER_ALIASES = {
    "answer",
    "answers",
    "antwort",
    "antworten",
    "response",
    "responses",
}


def normalize_column_name(name: object) -> str:
    if name is None:
        return ""
    text = str(name).replace("\xa0", " ").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def find_first_matching_column(columns: Iterable[object], aliases: set[str]) -> str | None:
    for col in columns:
        normalized = normalize_column_name(col)
        if normalized in aliases:
            return str(col)
    return None


def is_settings_sheet(df: pd.DataFrame) -> bool:
    normalized_cols = {normalize_column_name(c) for c in df.columns}
    return "setting" in normalized_cols and "value" in normalized_cols


def detect_header_row(raw_df: pd.DataFrame) -> int | None:
    for idx in range(len(raw_df)):
        row_values = [normalize_column_name(v) for v in raw_df.iloc[idx].tolist()]
        has_question = any(v in QUESTION_ALIASES for v in row_values)
        has_answer = any(v in ANSWER_ALIASES for v in row_values)
        if has_question and has_answer:
            return idx
    return None


def sheet_with_detected_headers(workbook_path: Path, sheet_name: str) -> pd.DataFrame:
    raw_df = pd.read_excel(workbook_path, sheet_name=sheet_name, header=None, dtype=str)
    if raw_df.empty:
        return pd.DataFrame()

    header_row = detect_header_row(raw_df)
    if header_row is None:
        # Fallback to pandas default parsing if no explicit header row could be found.
        return pd.read_excel(workbook_path, sheet_name=sheet_name)

    data = raw_df.iloc[header_row + 1 :].copy()
    data.columns = raw_df.iloc[header_row].tolist()
    data = data.reset_index(drop=True)
    return data


def normalize_sheet_label(label: str) -> str:
    normalized = label.strip()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^A-Za-z0-9_\-]", "", normalized)
    return normalized


def extract_round(label: str) -> str | None:
    match = re.search(r"r(ound)?\s*([0-9]+)", label, flags=re.IGNORECASE)
    if not match:
        return None
    return f"R{match.group(2)}"


def build_long_records(workbook_path: Path) -> pd.DataFrame:
    excel = pd.ExcelFile(workbook_path)
    records: list[dict[str, object]] = []

    for sheet_name in excel.sheet_names:
        df = sheet_with_detected_headers(workbook_path, sheet_name)
        if df.empty:
            continue
        if is_settings_sheet(df):
            continue

        question_col = find_first_matching_column(df.columns, QUESTION_ALIASES)
        answer_col = find_first_matching_column(df.columns, ANSWER_ALIASES)

        if not question_col or not answer_col:
            continue

        subset = df[[question_col, answer_col]].copy()
        subset = subset.rename(columns={question_col: "question", answer_col: "answer"})
        subset["question"] = subset["question"].fillna("").astype(str).str.replace("\xa0", " ", regex=False).str.strip()
        subset["answer"] = subset["answer"].fillna("").astype(str).str.replace("\xa0", " ", regex=False).str.strip()

        subset = subset[(subset["question"] != "") & (subset["question"].str.lower() != "nan")]

        system_version = normalize_sheet_label(sheet_name)
        round_name = extract_round(sheet_name)

        for _, row in subset.iterrows():
            records.append(
                {
                    "system_version": system_version,
                    "sheet_name": sheet_name,
                    "round": round_name,
                    "question": row["question"],
                    "answer": row["answer"],
                }
            )

    if not records:
        return pd.DataFrame(columns=["system_version", "sheet_name", "round", "question", "answer"])

    long_df = pd.DataFrame.from_records(records)
    long_df = long_df.drop_duplicates(subset=["sheet_name", "question", "answer"]).reset_index(drop=True)
    return long_df


def build_wide_records(long_df: pd.DataFrame) -> pd.DataFrame:
    if long_df.empty:
        return pd.DataFrame(columns=["question"])

    wide = (
        long_df.pivot_table(
            index="question",
            columns="system_version",
            values="answer",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    ordered_cols = ["question"] + sorted([c for c in wide.columns if c != "question"])
    return wide[ordered_cols]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Q/A pairs from Fragerunden workbook.")
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to .xlsx file (e.g. 'Fragerunden .xlsx').",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("outputs"),
        help="Directory for generated files.",
    )
    parser.add_argument(
        "--long-name",
        default="fragerunden_qa_long.csv",
        help="Filename for long-format CSV output.",
    )
    parser.add_argument(
        "--wide-name",
        default="fragerunden_qa_wide.csv",
        help="Filename for wide-format CSV output.",
    )
    parser.add_argument(
        "--json-name",
        default="fragerunden_qa_long.jsonl",
        help="Filename for JSONL output based on long format.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")

    args.outdir.mkdir(parents=True, exist_ok=True)

    long_df = build_long_records(args.input)
    wide_df = build_wide_records(long_df)

    long_path = args.outdir / args.long_name
    wide_path = args.outdir / args.wide_name
    jsonl_path = args.outdir / args.json_name

    long_df.to_csv(long_path, index=False)
    wide_df.to_csv(wide_path, index=False)
    long_df.to_json(jsonl_path, orient="records", lines=True, force_ascii=False)

    print(f"Input workbook: {args.input}")
    print(f"Extracted rows: {len(long_df)}")
    print(f"Detected systems: {long_df['system_version'].nunique() if not long_df.empty else 0}")
    print(f"Long CSV: {long_path}")
    print(f"Wide CSV: {wide_path}")
    print(f"Long JSONL: {jsonl_path}")


if __name__ == "__main__":
    main()
