#!/usr/bin/env python3
"""Summarize only immutable matching pilot receipts; never open raw prompts."""
import argparse
import json
from pathlib import Path
import re

from compare_models import MODELS, atomic_json, quantiles, sha

ROOT = Path(__file__).resolve().parents[2]


def summarize(folder):
    capture = json.loads((folder / "frozen-capture.json").read_text())
    expected_ids = {c["id"] for c in json.loads(Path(__file__).with_name("model_cases.json").read_text())
                    if c.get("pilot")}
    rows = []
    harnesses = set()
    resource_file = folder / "resource-samples-pilot.json"
    samples = json.loads(resource_file.read_text())["samples"] if resource_file.exists() else []
    # This summarizer is for the original six-model frozen bank only.
    for key in ("control", "command-r7b", "qwen35-9b", "qwen38-27b", "qwen3-4b", "gemma4-12b"):
        base = MODELS[key]
        path = folder / f"pilot-{key}.json"
        if not path.exists():
            rows.append({"model": key, "baseModel": base, "state": "not yet attempted"})
            continue
        report = json.loads(path.read_text())
        if report["frozenSha256"] != capture["frozenSha256"] or report["casesSha256"] != capture["casesSha256"]:
            raise ValueError("Pilot evidence/case identity mismatch")
        if report["appPythonSha256"] != capture["appPythonSha256"]:
            raise ValueError("Pilot application identity mismatch")
        harnesses.add(report["harnessSha256"])
        results = report["results"]
        actual_pairs = {(r["pass"], r["id"]) for r in results}
        expected_pairs = {(repeat, case_id) for repeat in (1, 2) for case_id in expected_ids}
        if len(actual_pairs) != len(results) or not actual_pairs.issubset(expected_pairs):
            raise ValueError("Duplicate or unexpected pilot result")
        complete = report["complete"] and actual_pairs == expected_pairs
        if report["complete"] and not complete:
            raise ValueError("Incomplete pilot marked complete")
        supported = [r for r in results if r["category"] == "supported"]
        failures = [{"id": r["id"], "pass": r["pass"], "errors": r["errors"]}
                    for r in results if not r["passed"]]
        contexts = set()
        for sample in samples:
            if sample.get("modelUnderTest") != key:
                continue
            text = sample.get("residency", {}).get("notbot-model-eval-20261001", {}).get("stdout", "")
            match = re.search(r"^notbot-eval-" + re.escape(key) +
                r":ctx32k\s+\S+\s+\S+\s+\S+\s+\d+%\s+\S+\s+(\d+)", text, re.M)
            if match:
                contexts.add(int(match[1]))
        rows.append({
            "model": key, "baseModel": base, "state": "complete" if complete else "partial/error",
            "receiptSha256": sha(path.read_bytes()), "baseManifestDigest": report["baseManifestDigest"],
            "responses": len(results), "passed": report["passed"],
            "supportedResponses": len(supported), "supportedPassed": sum(r["passed"] for r in supported),
            "allPilotChecksPassed": complete and not failures,
            "falseRefusals": sum(r["abstained"] and r["category"] != "gap" for r in results),
            "repairResponses": sum(r["generationAttempts"] > 1 for r in results),
            "requestErrors": report["requestErrors"],
            "requestedContext": report["context"],
            "sampledRuntimeContexts": sorted(contexts),
            "contextMatchesRequestInSamples": bool(contexts) and contexts == {report["context"]},
            "actualContextMustBeQualified": contexts != {report["context"]},
            "pilotLatencyAll": quantiles(results),
            "pilotLatencyExcludingFirstRequest": quantiles(results[1:]),
            "passingResponseLatencyOnly": quantiles([r for r in results if r["passed"]]),
            "passingLatencyIsNotAllRequestsSLO": True,
            "thinkingControlVerified": report["thinkingControlVerified"],
            "noReasoningOutputObserved": report["noReasoningOutputObserved"],
            "failures": failures,
        })
    if len(harnesses) > 1:
        raise ValueError("Pilots used different harness versions")
    return {
        "scope": "Six-model generator pilot on shared GPU; not PHP latency, domain-owner review, or release approval",
        "allPilotsComplete": all(r["state"] == "complete" for r in rows),
        "casesSha256": capture["casesSha256"], "frozenSha256": capture["frozenSha256"],
        "appPythonSha256": capture["appPythonSha256"], "harnessSha256": next(iter(harnesses), None),
        "approvedWinner": None, "automaticPromotion": False,
        "formalWarmColdConcurrencyTestingComplete": False,
        "fullEndToEndTestingComplete": False, "independentDomainReviewComplete": False,
        "models": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=ROOT / "reports/model-evaluation")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = summarize(args.reports)
    atomic_json(args.output or args.reports / "pilot-summary.json", result)
    print(json.dumps({"allPilotsComplete": result["allPilotsComplete"],
                      "models": [{k: row.get(k) for k in ("model", "state", "responses", "passed",
                                                         "falseRefusals", "pilotLatencyExcludingFirstRequest")}
                                 for row in result["models"]]}, indent=2))


if __name__ == "__main__":
    main()
