#!/usr/bin/env python3
"""Visualize Fragerunden evaluation results per system and per question.

Inputs:
- outputs/fragerunden_eval_rows.csv
- outputs/fragerunden_eval_by_system.csv (optional)

Outputs (PNG + CSV) in outdir:
- fragerunden_heatmap_answer_relevance.png
- fragerunden_heatmap_answer_correctness.png
- fragerunden_system_means.png
- fragerunden_per_question_best_system.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize Fragerunden eval outputs.")
    parser.add_argument(
        "--rows",
        type=Path,
        default=Path("outputs/fragerunden_eval_rows.csv"),
        help="Row-level evaluation CSV.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("outputs/fragerunden_eval_by_system.csv"),
        help="System-level summary CSV (optional, recomputed if missing).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("outputs"),
        help="Directory to write plots and helper CSV outputs.",
    )
    return parser.parse_args()


def _short_question_label(question: str, max_chars: int = 85) -> str:
    q = " ".join(str(question).split())
    if len(q) <= max_chars:
        return q
    return q[: max_chars - 3] + "..."


def _plot_heatmap(pivot: pd.DataFrame, title: str, outpath: Path, cmap: str = "YlGnBu") -> None:
    if pivot.empty:
        return

    fig_h = max(6, 0.45 * len(pivot.index))
    fig_w = max(8, 1.8 * len(pivot.columns))

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(pivot.values, aspect="auto", cmap=cmap, vmin=0.0, vmax=1.0)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([_short_question_label(q) for q in pivot.index])
    ax.set_title(title)
    ax.set_xlabel("RAG system version")
    ax.set_ylabel("Question")

    # annotate values for readability
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.iat[i, j]
            txt = "" if pd.isna(val) else f"{val:.2f}"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8, color="black")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Score")

    fig.tight_layout()
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def _plot_system_means(rows_df: pd.DataFrame, outpath: Path) -> None:
    metrics = ["answer_relevance", "answer_correctness", "context_relevance", "groundedness"]
    present_metrics = [m for m in metrics if m in rows_df.columns]
    if not present_metrics:
        return

    means = rows_df.groupby("system_version", dropna=False)[present_metrics].mean(numeric_only=True)
    means = means.fillna(0.0)

    fig_w = max(8, 1.6 * len(means.index))
    fig, ax = plt.subplots(figsize=(fig_w, 6))

    x = range(len(means.index))
    width = 0.8 / max(1, len(present_metrics))

    for idx, metric in enumerate(present_metrics):
        offset = (idx - (len(present_metrics) - 1) / 2) * width
        values = means[metric].values
        ax.bar([i + offset for i in x], values, width=width, label=metric)

    ax.set_xticks(list(x))
    ax.set_xticklabels(means.index, rotation=25, ha="right")
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Mean score")
    ax.set_title("Mean metric scores by RAG system")
    ax.legend()

    fig.tight_layout()
    fig.savefig(outpath, dpi=160)
    plt.close(fig)


def _build_best_system_table(rows_df: pd.DataFrame) -> pd.DataFrame:
    # Primary ranking by correctness when available, then by answer relevance.
    ranking_cols = [c for c in ["answer_correctness", "answer_relevance"] if c in rows_df.columns]
    if not ranking_cols:
        return pd.DataFrame(columns=["question", "best_system", "best_score"])

    work = rows_df[["question", "system_version", *ranking_cols]].copy()
    work[ranking_cols] = work[ranking_cols].fillna(-1.0)

    work["rank_score"] = work[ranking_cols[0]]
    if len(ranking_cols) > 1:
        work["rank_score"] = work["rank_score"] + 0.01 * work[ranking_cols[1]]

    idx = work.groupby("question", dropna=False)["rank_score"].idxmax()
    best = work.loc[idx, ["question", "system_version", "rank_score"]].copy()
    best = best.rename(
        columns={
            "system_version": "best_system",
            "rank_score": "best_score",
        }
    ).sort_values("question")
    return best.reset_index(drop=True)


def main() -> None:
    args = parse_args()

    if not args.rows.exists():
        raise FileNotFoundError(f"Row-level file not found: {args.rows}")

    rows_df = pd.read_csv(args.rows)
    args.outdir.mkdir(parents=True, exist_ok=True)

    # Keep order stable by the first appearance in file.
    question_order = rows_df["question"].dropna().drop_duplicates().tolist()
    system_order = rows_df["system_version"].dropna().drop_duplicates().tolist()

    for metric, plot_name, title in [
        ("answer_relevance", "fragerunden_heatmap_answer_relevance.png", "Answer relevance by question and system"),
        ("answer_correctness", "fragerunden_heatmap_answer_correctness.png", "Answer correctness by question and system"),
    ]:
        if metric not in rows_df.columns:
            continue
        pivot = rows_df.pivot_table(index="question", columns="system_version", values=metric, aggfunc="mean")
        pivot = pivot.reindex(index=question_order, columns=system_order)
        _plot_heatmap(pivot, title=title, outpath=args.outdir / plot_name)

    _plot_system_means(rows_df, args.outdir / "fragerunden_system_means.png")

    best = _build_best_system_table(rows_df)
    best.to_csv(args.outdir / "fragerunden_per_question_best_system.csv", index=False)

    print(f"Saved: {args.outdir / 'fragerunden_heatmap_answer_relevance.png'}")
    print(f"Saved: {args.outdir / 'fragerunden_heatmap_answer_correctness.png'}")
    print(f"Saved: {args.outdir / 'fragerunden_system_means.png'}")
    print(f"Saved: {args.outdir / 'fragerunden_per_question_best_system.csv'}")


if __name__ == "__main__":
    main()
