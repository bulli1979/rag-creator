#!/usr/bin/env python3
"""Run all isolated model pilots sequentially and record shared GPU conditions.

No live service is stopped or modified. A failed/time-limited model cancels only
the owned test engine before proceeding, so abandoned requests cannot stack.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading

from compare_models import atomic_json, private_dir, sha

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/model-evaluation"
ENGINE = "notbot-model-eval-20261001"
IMAGE = "observatory-document-api:phase6-final-20261001"
PINS = {
    "control": "529eae81d571715fd08bcd654c3a3db008fb93ab15a7369a24be7856d7f48477",
    "command-r7b": "ff4e9696ef9f19b62e3f7d7261c95dcc9bb15a7c0398493366d851119fe2e1ef",
    "qwen35-9b": "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7",
    "qwen38-27b": "22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643",
    "qwen3-4b": "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0",
    "gemma4-12b": "6114515d63c17436a7c0417d82820ac65ad643e2806c5a3c89cb62846436ed0b",
}


def sample(model):
    def read(cmd):
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=15)
        return {"exitCode": result.returncode, "stdout": result.stdout.strip()}
    return {"recordedAt": datetime.now(timezone.utc).isoformat(), "modelUnderTest": model,
            "gpu": read(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader"]),
            "residency": {name: read(["docker", "exec", name, "ollama", "ps"])
                          for name in ("ollama-prod", "ollama-qwen-secondary", ENGINE)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--only", choices=PINS)
    args = parser.parse_args()
    work = private_dir(args.private)
    models = [args.only] if args.only else list(PINS)
    resources = []
    statuses = []
    current = {"model": None}
    stop = threading.Event()
    resource_path = REPORTS / ("resource-samples-" + (args.only or "pilot") + ".json")

    def sampler():
        while not stop.is_set():
            try:
                resources.append(sample(current["model"]))
            except Exception as exc:
                resources.append({"error": type(exc).__name__})
            atomic_json(resource_path, {"condition": "Shared GPU; live and agent services retained",
                                        "samples": resources})
            stop.wait(15)
    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    try:
        for key in models:
            current["model"] = key
            print(json.dumps({"startingModel": key}), flush=True)
            cmd = ["docker", "run", "--rm", "--name", f"notbot-model-pilot-{key}",
                   "--network", "observatory_default",
                   "-e", "RAG_DATA_ROOT=/data", "-e", "PYTHONPATH=/app",
                   "-e", "HF_HUB_OFFLINE=1", "-e", "TRANSFORMERS_OFFLINE=1",
                   "-e", "CUDA_VISIBLE_DEVICES=-1", "-e", "OMP_NUM_THREADS=2",
                   "-v", "observatory_rag_api_data:/data:ro",
                   "-v", f"{ROOT}/scripts/evaluation:/workspace/scripts/evaluation:ro",
                   "-v", f"{work}:/private", "-v", f"{REPORTS}:/reports", IMAGE,
                   "python", "-u", "/workspace/scripts/evaluation/compare_models.py",
                   "pilot", "--private", "/private", "--output", f"/reports/pilot-{key}.json",
                   "--model", key, "--digest", PINS[key]]
            status = subprocess.run(cmd).returncode
            report_path = REPORTS / f"pilot-{key}.json"
            report = json.loads(report_path.read_text()) if report_path.exists() else {}
            row = {"model": key, "processExitCode": status, "complete": report.get("complete", False),
                   "responses": len(report.get("results", [])), "passed": report.get("passed"),
                   "requestErrors": report.get("requestErrors")}
            statuses.append(row)
            atomic_json(REPORTS / "pilot-run-status.json",
                        {"requestedModels": models, "modelsCompletedOrAttempted": statuses,
                         "driverSha256": sha(Path(__file__).read_bytes()),
                         "complete": len(statuses) == len(models),
                         "allPilotsComplete": all(r["complete"] for r in statuses)})
            print(json.dumps({"modelStatus": row}), flush=True)
            if status or report.get("requestErrors") or not report.get("complete"):
                # Cancellation is limited to this explicitly task-owned test engine.
                subprocess.run(["docker", "restart", ENGINE], check=True, capture_output=True)
                print(json.dumps({"testEngineRestartedAfterFailedModel": key}), flush=True)
    finally:
        stop.set()
        thread.join(timeout=60)


if __name__ == "__main__":
    main()
