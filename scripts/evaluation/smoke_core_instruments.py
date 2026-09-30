#!/usr/bin/env python3
"""Live regression checks for supported core instruments and a genuine corpus gap."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen


CASES = (
    ("what is NOTCAM?", (r"notcam", r"infrared|swir")),
    ("What is NOTCAM?", (r"notcam", r"infrared|swir")),
    ("What is NOTCAM used for?", (r"notcam", r"imaging", r"spectro")),
    ("Which wavelength range does NOTCAM cover?", (r"0\.8", r"2\.5")),
    ("What is ALFOSC used for?", (r"alfosc", r"imaging", r"spectro")),
    ("What is FIES?", (r"fies", r"spectro")),
    ("NOT quantum teleporter recalibration", ()),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = []
    for question, expected in CASES:
        request = Request(
            args.api_base_url.rstrip("/") + "/api/chat",
            data=json.dumps({"message": question, "language": "en"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=180) as response:
            data = json.load(response)
        answer = data.get("answer", "")
        trace = data.get("trace", {})
        ids = re.findall(r"\[(D-[a-fA-F0-9]+-C\d+)\]", answer)
        supplied = {chunk.get("citationId") for chunk in data.get("contextChunks", [])}
        errors = []
        if expected:
            if data.get("metrics", {}).get("abstained") is not False:
                errors.append("supported question abstained")
            if not ids or not set(ids).issubset(supplied):
                errors.append("missing or unsupplied citation")
            for pattern in expected:
                if not re.search(pattern, answer, re.I):
                    errors.append(f"missing expected content: {pattern}")
        elif data.get("metrics", {}).get("abstained") is not True or ids:
            errors.append("corpus gap did not abstain")
        row = {
            "question": question, "answer": answer, "passed": not errors,
            "errors": errors, "promptVersion": trace.get("promptVersion"),
            "promptSha256": trace.get("promptSha256"), "indexId": trace.get("indexId"),
            "model": trace.get("model"), "corpusVersion": trace.get("corpusVersion"),
            "elapsedMs": trace.get("elapsedMs"), "acceptedClaims": trace.get("acceptedClaims", 0),
            "rejectedClaims": trace.get("rejectedClaims", 0),
            "generationAttempts": trace.get("generationAttempts", 0),
        }
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(row["passed"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
