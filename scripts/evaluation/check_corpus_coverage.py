#!/usr/bin/env python3
"""Map baseline retrieved source URLs to corpus-manifest dispositions."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import corpus_audit


LABEL_RE = re.compile(r"^\[([^\]]+)\]$", re.MULTILINE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--csv-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    by_url: dict[str, list[dict]] = defaultdict(list)
    for item in manifest["documents"]:
        if item.get("sourceUrl"):
            by_url[corpus_audit.canonicalize_url(item["sourceUrl"]).lower()].append(item)

    with args.qa.open("r", encoding="utf-8", newline="") as handle:
        qa_rows = list(csv.DictReader(handle))
    output: list[dict[str, str]] = []
    summary: Counter[str] = Counter()
    for index, row in enumerate(qa_rows):
        urls = {
            corpus_audit.canonicalize_url(unquote(label)).lower()
            for label in LABEL_RE.findall(row.get("context", ""))
            if label.startswith(("http://", "https://"))
        }
        matched = [item for url in sorted(urls) for item in by_url.get(url, [])]
        dispositions = sorted({item["disposition"] for item in matched})
        active_available = any(item["disposition"] == "active" for item in matched)
        status = (
            "active_source_available"
            if active_available
            else "mapped_without_active_source"
            if matched
            else "unmapped_context"
        )
        summary[status] += 1
        output.append(
            {
                "rowIndex": str(index),
                "question": row.get("question", ""),
                "status": status,
                "dispositions": ";".join(dispositions),
                "matchedSources": str(len(matched)),
                "activeSources": str(sum(item["disposition"] == "active" for item in matched)),
                "historicalSources": str(sum(item["disposition"] == "historical" for item in matched)),
                "quarantineSources": str(sum(item["disposition"] == "quarantine" for item in matched)),
                "excludedSources": str(sum(item["disposition"] == "excluded" for item in matched)),
            }
        )

    args.csv_out.parent.mkdir(parents=True, exist_ok=True)
    with args.csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    lines = [
        "# Phase 1 evaluation-source coverage",
        "",
        "This is a conservative mapping of sources retrieved by the Phase 0 live evaluation to their Phase 1 manifest dispositions. It does not replace running the evaluation against a rebuilt shadow index.",
        "",
        "| Status | Questions |",
        "|---|---:|",
    ]
    for status, count in sorted(summary.items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(
        [
            "",
            "## Questions without an active mapped source",
            "",
            "| Row | Status | Question | Dispositions |",
            "|---:|---|---|---|",
        ]
    )
    for row in output:
        if row["status"] == "active_source_available":
            continue
        question = row["question"].replace("|", "\\|")
        lines.append(
            f"| {row['rowIndex']} | {row['status']} | {question} | {row['dispositions']} |"
        )
    lines.extend(
        [
            "",
            "A candidate with any `mapped_without_active_source` row has a material regression risk and must not replace the live corpus before domain review, regeneration of corrupted sources, and comparative evaluation.",
            "",
        ]
    )
    args.markdown_out.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(dict(sorted(summary.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
