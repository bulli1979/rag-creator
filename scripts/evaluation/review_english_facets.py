#!/usr/bin/env python3
"""Additional text-only facet audit; preserve original screening receipts.

Citation identifiers must not accidentally satisfy numeric answer expectations.
Reads only fresh task-owned validated test outputs, never prompts or old audits.
Does not alter the application, verifier, frozen cases or original scoring.
"""
import argparse
import json
from pathlib import Path
import re

from compare_models import atomic_json, private_dir, sha


def text_errors(case, answer):
    text = re.sub(r"\[D-[a-fA-F0-9]+-C\d+\]", "", answer)
    errors = []
    for pattern in case.get("expect", []):
        if pattern == "four|4":
            pattern = r"\b(?:four|4)\b"
        if pattern == "N.*3|3.*N":
            pattern = r"\bN\b.*\b3\b|\b3\b.*\bN\b|at least\s+(?:3|three)"
        if pattern == "no|cannot|can't|below|outside":
            pattern = r"\b(?:no|cannot|can't|below|outside)\b"
        if not re.search(pattern, text, re.I | re.S):
            errors.append("missing text-only required facet: " + pattern)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("model_cases_en_v2.json"))
    parser.add_argument("--stage", choices=("pilot", "full"), default="pilot")
    parser.add_argument("--receipt-glob", default="pilot-*.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = private_dir(args.private)
    cases = {c["id"]: c for c in json.loads(args.cases.read_text())}
    cases_digest = sha(args.cases.read_bytes())
    models = []
    if "/" in args.receipt_glob or ".." in args.receipt_glob:
        raise ValueError("Receipt glob must stay within the named report directory")
    for path in sorted(args.reports.glob(args.receipt_glob)):
        report = json.loads(path.read_text())
        if report["casesSha256"] != cases_digest:
            raise ValueError("Case identity changed")
        relative = Path(report.get("rawOutputsRelativeDirectory", args.stage + "-outputs/" + report["model"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Raw output location must stay private")
        raw_directory = (work / relative).resolve()
        if not raw_directory.is_relative_to(work):
            raise ValueError("Raw outputs resolve outside private directory")
        reviewed = []
        for row in report["results"]:
            matches = []
            for attempt in row["attempts"]:
                raw_path = raw_directory / f"{row['pass']}-{row['id']}-{attempt['attempt']}.json"
                raw = json.loads(raw_path.read_text())
                answer = raw["validatedAnswer"]
                if sha(answer.encode()) == row["answerSha256"]:
                    matches.append(answer)
            if not matches:
                raise ValueError("Validated output hash does not match receipt")
            errors = text_errors(cases[row["id"]], matches[-1])
            reviewed.append({"id": row["id"], "pass": row["pass"], "originalPassed": row["passed"],
                             "additionalErrors": errors, "passed": row["passed"] and not errors})
        models.append({"model": report["model"], "profile": report.get("profile"), "complete": report["complete"], "responses": len(reviewed),
            "originalPassed": report["passed"], "textOnlyPassed": sum(r["passed"] for r in reviewed),
            "receiptSha256": sha(path.read_bytes()), "results": reviewed})
    atomic_json(args.output, {"scope": "Additional citation-ID-free text facet audit, NOT independent semantic/domain certification",
        "casesSha256": cases_digest, "reviewerSha256": sha(Path(__file__).read_bytes()),
        "originalReceiptsModified": False, "promptsRead": False, "historicalAuditsRead": False, "models": models})
    print(json.dumps([{k:v for k,v in m.items() if k != "results"} for m in models], indent=2))


if __name__ == "__main__":
    main()
