#!/usr/bin/env python3
"""Sequential isolated final-service checks with sampled shared GPU state."""
import argparse
import json
from pathlib import Path
import subprocess
import threading

from compare_models import MODELS, atomic_json, private_dir, quantiles, sha
from run_model_pilot import ENGINE, IMAGE, sample

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/model-evaluation/english-v2"


def summarize(models):
    capture = json.loads((REPORTS / "frozen-capture.json").read_text())
    case_digest = sha((ROOT / "scripts/evaluation/operational_cases.json").read_bytes())
    english_cases = [c for c in json.loads((ROOT / "scripts/evaluation/operational_cases.json").read_text())
                     if c.get("language", "en") == "en"]
    ids = {c["id"] for c in english_cases}
    rows, versions = [], set()
    for key in models:
        path = REPORTS / "service" / f"service-{key}.json"
        if not path.exists():
            rows.append({"model": key, "complete": False})
            continue
        report = json.loads(path.read_text())
        if report["appPythonSha256"] != capture["appPythonSha256"] or report["casesSha256"] != case_digest:
            raise ValueError("Service application/case identity differs")
        versions.add(report["driverSha256"])
        results = report["results"]
        actual = {r["id"] for r in results}
        if len(actual) != len(results) or not actual.issubset(ids):
            raise ValueError("Unexpected or duplicate service result")
        complete = report["complete"] and actual == ids
        generated = [r for r in results if r["trace"].get("generationAttempts", 0)]
        sourced = [r for r in results if not r["trace"].get("generationAttempts", 0)]
        rows.append({"model": key, "complete": complete, "responses": len(results), "passed": report["passed"],
            "generatedResponses": len(generated), "generatedPassed": sum(r["passed"] for r in generated),
            "sourceDerivedResponses": len(sourced), "sourceDerivedPassed": sum(r["passed"] for r in sourced),
            "allLatency": quantiles(results), "generatedLatency": quantiles(generated),
            "sourceDerivedLatency": quantiles(sourced), "receiptSha256": sha(path.read_bytes()),
            "failures": [{"id": r["id"], "errors": r["errors"], "abstained": r["abstained"]} for r in results if not r["passed"]]})
    if len(versions) > 1:
        raise ValueError("Mixed service harness versions")
    report = {"allComplete": all(r["complete"] for r in rows), "models": rows,
        "scope": "Final in-process ChatService, English-only, real retrieval/routing, dynamic validated history; not HTTP/PHP certification",
        "casesSha256": case_digest, "appPythonSha256": capture["appPythonSha256"],
        "uniformTransportAdapter": "Explicit reasoning_effort none, SDK retries disabled, timeout180",
        "approvedWinner": None, "automaticPromotion": False}
    atomic_json(REPORTS / "service/summary.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--models", nargs="+", choices=MODELS,
                        default=["control", "ministral3-8b", "qwen38-27b", "qwen3-4b"])
    args = parser.parse_args()
    work = private_dir(args.private)
    folder = REPORTS / "service"
    folder.mkdir(parents=True, exist_ok=True)
    resources, statuses = [], []
    current = {"model": None}
    stopped = threading.Event()
    def sampler():
        while not stopped.is_set():
            try:
                resources.append(sample(current["model"]))
            except Exception as exc:
                resources.append({"error": type(exc).__name__})
            atomic_json(folder / "resources.json", {"condition": "Live/agent services retained", "samples": resources})
            stopped.wait(15)
    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    try:
        for key in args.models:
            current["model"] = key
            target = folder / f"service-{key}.json"
            if target.exists():
                report = json.loads(target.read_text())
                if report.get("complete"):
                    continue
                raise ValueError("Partial service receipt requires a separately labeled run")
            print(json.dumps({"startingServiceModel": key}), flush=True)
            cmd = ["docker", "run", "--rm", "--name", f"notbot-english-service-{key}", "--network", "observatory_default",
                "-e", "RAG_DATA_ROOT=/data", "-e", "PYTHONPATH=/app", "-e", "HF_HUB_OFFLINE=1", "-e", "TRANSFORMERS_OFFLINE=1",
                "-e", "CUDA_VISIBLE_DEVICES=-1", "-e", "OMP_NUM_THREADS=2", "-v", "observatory_rag_api_data:/data:ro",
                "-v", f"{ROOT}/documentApi/source_boosts.json:/data/source_boosts.json:ro",
                "-v", f"{ROOT}/scripts/evaluation:/workspace/scripts/evaluation:ro", "-v", f"{work}:/private",
                "-v", f"{folder}:/reports", "-v", f"{REPORTS}/models.json:/pins.json:ro", IMAGE,
                "python", "-u", "/workspace/scripts/evaluation/evaluate_model_service.py", "--model", key,
                "--private", "/private", "--pins", "/pins.json", "--output", f"/reports/service-{key}.json"]
            code = subprocess.run(cmd).returncode
            report = json.loads(target.read_text()) if target.exists() else {}
            statuses.append({"model": key, "exitCode": code, "complete": report.get("complete", False),
                             "responses": len(report.get("results", [])), "passed": report.get("passed")})
            atomic_json(folder / "run-status.json", {"models": statuses, "requestedModels": args.models,
                "driverSha256": sha(Path(__file__).read_bytes()), "complete": len(statuses) == len(args.models)})
            print(json.dumps(statuses[-1]), flush=True)
            summarize(args.models)
            if code or not report.get("complete"):
                subprocess.run(["docker", "restart", ENGINE], check=True, stdout=subprocess.DEVNULL)
    finally:
        stopped.set()
        thread.join(timeout=30)


if __name__ == "__main__":
    main()
