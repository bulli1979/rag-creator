#!/usr/bin/env python3
"""Download or screen English-only candidates in the task-owned isolated engine."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import threading

from compare_models import MODELS, atomic_json, private_dir, quantiles, sha
from run_model_pilot import ENGINE, IMAGE, PINS, sample

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/model-evaluation/english-v2"
DOWNLOAD = "notbot-model-download-20261001"
NEW = ("ministral3-8b", "ministral3-14b", "granite42-8b", "qwen3-30b-a3b", "nemotron35-30b-a3b")
SCREEN = ("control", "ministral3-8b", "ministral3-14b", "granite42-8b", "qwen3-30b-a3b",
          "nemotron35-30b-a3b", "qwen38-27b", "qwen3-4b", "command-r7b")


def inventory():
    # Same network namespace as the CPU-only downloader, no published endpoint.
    code = '''import hashlib,json,urllib.request
def call(path,body=None):
 req=urllib.request.Request("http://127.0.0.1:11434"+path,data=json.dumps(body).encode() if body else None,headers={"Content-Type":"application/json"})
 with urllib.request.urlopen(req,timeout=60) as r: return json.load(r)
rows=[]
for m in call("/api/tags")["models"]:
 if m["name"] not in NAMES: continue
 s=call("/api/show",{"model":m["name"]})
 rows.append({"name":m["name"],"digest":m["digest"],"size":m["size"],"details":m.get("details"),"capabilities":s.get("capabilities"),"contextMetadata":{k:v for k,v in s.get("model_info",{}).items() if k.endswith("context_length")},"templateSha256":hashlib.sha256(s.get("template","").encode()).hexdigest(),"licenseSha256":hashlib.sha256(s.get("license","").encode()).hexdigest(),"parameters":s.get("parameters","")})
print(json.dumps(rows))
'''
    code = "NAMES=" + repr(list(MODELS.values())) + "\n" + code
    result = subprocess.run(["docker", "run", "--rm", "--network", f"container:{DOWNLOAD}",
        "--entrypoint", "python", IMAGE, "-c", code], capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("Model metadata snapshot failed; error body withheld")
    return json.loads(result.stdout)


def download():
    statuses = []
    for key in NEW:
        print(json.dumps({"downloading": key, "tag": MODELS[key]}), flush=True)
        result = subprocess.run(["docker", "exec", DOWNLOAD, "ollama", "pull", MODELS[key]],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2400)
        statuses.append({"model": key, "tag": MODELS[key], "exitCode": result.returncode})
        atomic_json(REPORTS / "download-status.json", {"models": statuses, "complete": len(statuses) == len(NEW)})
        print(json.dumps(statuses[-1]), flush=True)
        if result.returncode:
            raise RuntimeError("Download failed; inspect bounded task-owned downloader diagnostics")
    models = inventory()
    for key in SCREEN:
        record = next(m for m in models if m["name"] == MODELS[key])
        if key in PINS and record["digest"] != PINS[key]:
            raise ValueError("Installed comparator changed")
    atomic_json(REPORTS / "models.json", {"recordedAt": datetime.now(timezone.utc).isoformat(),
        "models": models, "isolatedStore": "notbot_model_eval_20261001", "inferencePerformed": False})


def summarize(folder, models, stage):
    capture = json.loads((REPORTS / "frozen-capture.json").read_text())
    cases = json.loads((ROOT / "scripts/evaluation/model_cases_en_v2.json").read_text())
    case_digest = sha((ROOT / "scripts/evaluation/model_cases_en_v2.json").read_bytes())
    if case_digest != capture["casesSha256"]:
        raise ValueError("Frozen English bank changed")
    rows = []
    harnesses = set()
    resource_path = folder / "resources.json"
    samples = json.loads(resource_path.read_text())["samples"] if resource_path.exists() else []
    for key in models:
        path = folder / f"pilot-{key}.json"
        if not path.exists():
            rows.append({"model": key, "complete": False, "responses": 0})
            continue
        report = json.loads(path.read_text())
        for attr in ("frozenSha256", "casesSha256", "appPythonSha256"):
            if report[attr] != capture[attr]:
                raise ValueError("Pilot identity mismatch: " + attr)
        harnesses.add(report["harnessSha256"])
        expected_ids = {c["id"] for c in cases if stage == "full" or c.get("pilot")}
        if set(report["caseIds"]) != expected_ids:
            raise ValueError("Unexpected case subset")
        results = report["results"]
        expected = {(r, c) for r in range(1, report["repeats"] + 1) for c in expected_ids}
        seen = {(r["pass"], r["id"]) for r in results}
        if len(seen) != len(results) or not seen.issubset(expected):
            raise ValueError("Duplicate or unexpected response")
        complete = report["complete"] and seen == expected
        supported = [r for r in results if r["category"] == "supported"]
        contexts = set()
        for resource in samples:
            if resource.get("modelUnderTest") != key:
                continue
            text = resource.get("residency", {}).get(ENGINE, {}).get("stdout", "")
            match = re.search(r"^notbot-eval-" + re.escape(key) +
                r":english-v2-ctx32k\s+\S+\s+\S+\s+\S+\s+\d+%\s+\S+\s+(\d+)", text, re.M)
            if match:
                contexts.add(int(match[1]))
        rows.append({"model": key, "complete": complete, "responses": len(results),
            "passed": sum(r["passed"] for r in results), "supportedPassed": sum(r["passed"] for r in supported),
            "supportedResponses": len(supported), "falseRefusals": sum(r["abstained"] and r["category"] != "gap" for r in results),
            "repairResponses": sum(r["generationAttempts"] > 1 for r in results), "requestErrors": report["requestErrors"],
            "medianAndTailExcludingFirstRequest": quantiles(results[1:]),
            "passingOnlyLatency": quantiles([r for r in results if r["passed"]]),
            "receiptSha256": sha(path.read_bytes()), "baseManifestDigest": report["baseManifestDigest"],
            "noReasoningOutputObserved": report["noReasoningOutputObserved"],
            "requestedContext": report["context"], "sampledRuntimeContexts": sorted(contexts),
            "contextMatchesRequestInSamples": contexts == {report["context"]},
            "failures": [{"id": r["id"], "pass": r["pass"], "errors": r["errors"]} for r in results if not r["passed"]]})
    if len(harnesses) > 1:
        raise ValueError("Mixed harness versions")
    value = {"stage": stage, "scope": "English-only frozen-evidence generator screening; not PHP end-to-end or owner approval",
        "allComplete": all(r["complete"] for r in rows), "appPythonSha256": capture["appPythonSha256"],
        "frozenSha256": capture["frozenSha256"], "casesSha256": case_digest, "models": rows,
        "approvedWinner": None, "automaticPromotion": False}
    atomic_json(folder / "summary.json", value)
    return value


def run(args):
    work = private_dir(args.private)
    stage = "full" if args.all_cases else "pilot"
    folder = REPORTS / stage
    folder.mkdir(parents=True, exist_ok=True)
    models = args.models or list(SCREEN)
    inventory_rows = json.loads((REPORTS / "models.json").read_text())["models"]
    pins = {key: next(m["digest"] for m in inventory_rows if m["name"] == MODELS[key]) for key in models}
    resources, statuses = [], []
    current = {"model": None}
    stopped = threading.Event()
    def sampler():
        while not stopped.is_set():
            try:
                resources.append(sample(current["model"]))
            except Exception as exc:
                resources.append({"error": type(exc).__name__})
            atomic_json(folder / "resources.json", {"condition": "Live/agent services retained; residency sampled, no host-exclusive guarantee", "samples": resources})
            stopped.wait(15)
    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    try:
        for key in models:
            current["model"] = key
            print(json.dumps({"startingModel": key, "stage": stage}), flush=True)
            cmd = ["docker", "run", "--rm", "--name", f"notbot-english-{stage}-{key}", "--network", "observatory_default",
                "-e", "RAG_DATA_ROOT=/data", "-e", "PYTHONPATH=/app", "-e", "HF_HUB_OFFLINE=1",
                "-e", "TRANSFORMERS_OFFLINE=1", "-e", "CUDA_VISIBLE_DEVICES=-1", "-e", "OMP_NUM_THREADS=2",
                "-v", "observatory_rag_api_data:/data:ro", "-v", f"{ROOT}/scripts/evaluation:/workspace/scripts/evaluation:ro",
                "-v", f"{work}:/private", "-v", f"{folder}:/reports", IMAGE,
                "python", "-u", "/workspace/scripts/evaluation/compare_models.py", "pilot", "--private", "/private",
                "--cases", "/workspace/scripts/evaluation/model_cases_en_v2.json", "--output", f"/reports/pilot-{key}.json",
                "--model", key, "--digest", pins[key], "--repeats", str(args.repeats), "--profile-suffix", "english-v2-ctx32k",
                "--raw-subdirectory", stage + "-outputs"]
            if args.all_cases:
                cmd.append("--all-cases")
            status = subprocess.run(cmd).returncode
            path = folder / f"pilot-{key}.json"
            report = json.loads(path.read_text()) if path.exists() else {}
            row = {"model": key, "exitCode": status, "complete": report.get("complete", False), "responses": len(report.get("results", [])), "passed": report.get("passed")}
            statuses.append(row)
            atomic_json(folder / "run-status.json", {"models": statuses, "requestedModels": models, "driverSha256": sha(Path(__file__).read_bytes()), "complete": len(statuses) == len(models)})
            print(json.dumps({"modelStatus": row}), flush=True)
            summarize(folder, models, stage)
            if status or report.get("requestErrors") or not report.get("complete"):
                subprocess.run(["docker", "restart", ENGINE], check=True, stdout=subprocess.DEVNULL)
                print(json.dumps({"isolatedEngineRestarted": key}), flush=True)
    finally:
        stopped.set()
        thread.join(timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("download", "run", "summary"))
    parser.add_argument("--private", type=Path)
    parser.add_argument("--models", nargs="+", choices=MODELS)
    parser.add_argument("--all-cases", action="store_true")
    parser.add_argument("--repeats", type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    if args.mode == "download":
        download()
    elif args.mode == "run":
        run(args)
    else:
        stage = "full" if args.all_cases else "pilot"
        result = summarize(REPORTS / stage, args.models or list(SCREEN), stage)
        print(json.dumps({"allComplete": result["allComplete"], "models": [{k:v for k,v in r.items() if k not in ("failures",)} for r in result["models"]]}, indent=2))


if __name__ == "__main__":
    main()
