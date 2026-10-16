#!/usr/bin/env python3
"""Reproducible API acceptance tests: facts, completeness, citations and conversation.

The legacy suite is preserved as diagnostic output, not silently promoted to truth:
its historical references and safety answers need source-aware manual review.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


def assess(case, result):
    answer = result.get("answer", "")
    errors = []
    abstained = result.get("metrics", {}).get("abstained", False)
    if bool(case.get("abstain", False)) != abstained:
        errors.append("wrong abstention status")
    for pattern in case.get("expect", []):
        if not re.search(pattern, answer, re.I | re.S):
            errors.append(f"missing required facet: {pattern}")
    for pattern in case.get("forbid", []):
        if re.search(pattern, answer, re.I):
            errors.append(f"forbidden content: {pattern}")
    cited = set(re.findall(r"\[(D-[a-fA-F0-9]+-C\d+)\]", answer))
    chunks = {c.get("citationId"): c for c in result.get("contextChunks", [])}
    if not abstained and (not cited or not cited.issubset(chunks)):
        errors.append("missing or unsupplied citation")
    if case.get("currentSources") and not abstained:
        if any(re.search(r"/devel/|/bundleD/|fies-comm\.html", str(chunks.get(cid, {}).get("canonicalLocation", "")), re.I) for cid in cited):
            errors.append("obsolete/design evidence used as current operational fact")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("operational_cases.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--only", help="Comma-separated core case IDs")
    args = parser.parse_args()
    cases_bytes=args.cases.read_bytes()
    cases = json.loads(cases_bytes)
    cases_hash=hashlib.sha256(cases_bytes).hexdigest()
    legacy_hash=None
    if args.legacy:
        legacy_path=ROOT / "reports/phase0/evaluation-production-2026-09-28/questions_ground_truth.csv"
        legacy_hash=hashlib.sha256(legacy_path.read_bytes()).hexdigest()
        with legacy_path.open(newline="") as handle:
            cases += [{"id": f"legacy_{i+1:02}", "question": row["question"], "reference": row["ground_truth"], "diagnosticOnly": True}
                      for i, row in enumerate(csv.DictReader(handle, skipinitialspace=True))]
    selected = set(args.only.split(",")) if args.only else None
    cases = [case for case in cases if not selected or case['id'] in selected]
    if selected and selected != {case['id'] for case in cases}:
        raise ValueError('Unknown selected case IDs')
    results = []
    by_id = {}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    implementation_hash=hashlib.sha256()
    for path in sorted([*(ROOT/"documentApi/app").rglob("*.py"),
                        *(ROOT/"chatBotPHP").glob("*.js"),*(ROOT/"chatBotPHP").glob("*.php")]):
        implementation_hash.update(str(path.relative_to(ROOT)).encode())
        implementation_hash.update(path.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if selected and case["id"] not in selected:
            continue
        history = list(case.get("history", []))
        if case.get("after"):
            prior = by_id.get(case["after"])
            if prior is None:
                raise ValueError(f"Preceding case {case['after']} must be run first")
            history = prior["history"] + [{"role": "user", "content": prior["question"]},
                                         {"role": "assistant", "content": prior["answer"]}]
        payload = {"message": case["question"], "history": history, "language": case.get("language", "en")}
        started = time.monotonic()
        request = Request(args.api_base_url.rstrip("/") + "/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=240) as response:
                result = json.load(response)
            errors = assess(case, result) if not case.get("diagnosticOnly") else []
        except Exception as exc:
            result = {}; errors = [f"request error: {type(exc).__name__}: {exc}"]
        trace = result.get("trace", {})
        context_texts=[' '.join(str(c.get('text','')).split()) for c in result.get('contextChunks', [])]
        row = {"id": case["id"], "question": case["question"], "answer": result.get("answer", ""),
               "passed": not errors, "errors": errors, "diagnosticOnly": case.get("diagnosticOnly", False),
               "reference": case.get("reference"), "abstained": result.get("metrics", {}).get("abstained"),
               "elapsedMs": int((time.monotonic()-started)*1000),
               "exactDuplicateContextRows":len(context_texts)-len(set(context_texts)),
               "sources": [{"citationId": c.get("citationId"), "file": c.get("fileName"), "url": c.get("canonicalLocation"),
                            "section": c.get("section"), "status": c.get("status"), "authority": c.get("authority")}
                           for c in result.get("contextChunks", [])],
               "trace": {k:trace.get(k) for k in ("promptVersion","promptSha256","model","embeddingModel","corpusVersion","indexId",
                                                   "contextResolution","answerMethod","abstentionReason","generationAttempts","rejectedClaims","acceptedClaims",
                                                   "rejectionReasons","initialRejectionReasons","semanticChecker")}}
        by_id[case["id"]] = {**row, "history": history}
        results.append(row)
        core = [r for r in results if not r["diagnosticOnly"]]
        report = {"applicationCommit": commit, "casesSha256": cases_hash, "legacyCasesSha256":legacy_hash,
                  "implementationSha256":implementation_hash.hexdigest(),
                  "expectedCoreTotal":sum(not c.get('diagnosticOnly',False) for c in cases),
                  "expectedLegacyTotal":sum(bool(c.get('diagnosticOnly')) for c in cases),
                  "complete":len(results)==len(cases), "selectedCaseIds":sorted(selected) if selected else None,
                  "corePassed": sum(r["passed"] for r in core), "coreTotal": len(core), "results": results}
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
        print(json.dumps({k:row[k] for k in ("id","passed","abstained","elapsedMs","errors")}), flush=True)
    core = [r for r in results if not r["diagnosticOnly"]]
    return 0 if all(r["passed"] for r in core) else 1


if __name__ == "__main__":
    raise SystemExit(main())
