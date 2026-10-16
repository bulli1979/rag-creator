#!/usr/bin/env python3
"""Bounded Qwen27 parameter screen; no live config/profile mutation or promotion."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading

from compare_models import atomic_json, private_dir, quantiles, sha
from run_model_pilot import ENGINE, IMAGE, PINS, sample

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports/model-evaluation/qwen27-chat-tuning-v1"
VARIANTS = {"t03": (0.3, 4), "t01": (0.1, 4), "t00": (0.0, 4), "t03-nodraft": (0.3, 0)}


def summarize(variants, full=False):
    rows, identities = [], set()
    for name in variants:
        path = REPORTS / (name + ".json")
        if not path.exists():
            rows.append({"variant": name, "complete": False})
            continue
        receipt = json.loads(path.read_text())
        if full:
            bank = ROOT / "scripts/evaluation/model_cases_en_v2.json"
            case_ids = {c["id"] for c in json.loads(bank.read_text())}
            if set(receipt["caseIds"]) != case_ids or receipt["repeats"] != 3 or receipt["casesSha256"] != sha(bank.read_bytes()):
                raise ValueError("Full quality receipt does not cover the unchanged English bank three times")
        expected = {(p, c) for p in range(1, receipt["repeats"] + 1) for c in receipt["caseIds"]}
        seen = {(r["pass"], r["id"]) for r in receipt["results"]}
        if len(seen) != len(receipt["results"]) or not seen.issubset(expected):
            raise ValueError("Duplicate/unexpected tuning response")
        temp, draft = VARIANTS[name]
        if receipt["explicitProfileParameters"] != {"num_ctx": 32768, "num_predict": 2048,
            "temperature": temp, "draft_num_predict": draft}:
            raise ValueError("Parameter identity differs")
        if receipt["baseManifestDigest"] != PINS["qwen38-27b"]:
            raise ValueError("Qwen weights changed")
        identities.add(tuple(receipt[k] for k in ("casesSha256", "frozenSha256", "appPythonSha256", "harnessSha256")))
        results = receipt["results"]
        supported = [r for r in results if r["category"] == "supported"]
        rows.append({"variant": name, "parameters": receipt["explicitProfileParameters"],
            "complete": receipt["complete"] and seen == expected,
            "responses": len(results), "passed": sum(r["passed"] for r in results),
            "supportedPassed": sum(r["passed"] for r in supported), "supportedResponses": len(supported),
            "falseRefusals": sum(r["abstained"] and r["category"] != "gap" for r in results),
            "repairResponses": sum(r["generationAttempts"] > 1 for r in results),
            "requestErrors": receipt["requestErrors"],
            "postFirstRequestMixedCacheLatency": quantiles(results[1:]),
            "firstRequestMs": results[0]["elapsedMs"] if results else None,
            "noReasoningOutputObserved": receipt["noReasoningOutputObserved"],
            "profile": receipt["profile"], "profileManifestDigest": receipt["profileManifestDigest"],
            "receiptSha256": sha(path.read_bytes()),
            "categoryScores": {category: {"responses": sum(r["category"] == category for r in results),
                "passed": sum(r["category"] == category and r["passed"] for r in results)}
                for category in sorted({r["category"] for r in results})},
            "failures": [{"id": r["id"], "pass": r["pass"], "errors": r["errors"]} for r in results if not r["passed"]]})
    if len(identities) > 1:
        raise ValueError("Tuning mixes frozen/application/harness identities")
    value = {"recordedAt": datetime.now(timezone.utc).isoformat(), "models": rows,
        "allComplete": all(r["complete"] for r in rows), "requestedVariants": variants,
        "scope": "Qwen27 full English generator quality comparison" if full else "Qwen27 parameter screen, same frozen English evidence/production validation; NOT whole chatbot or PHP",
        "fullEnglishBank": full, "notHttpPhpCertification": True,
        "qualityApproved": False, "automaticPromotion": False,
        "generatorHarnessModifiedForExplicitTuningKnobs": True,
        "oldEnglishReceiptsOverwritten": False}
    atomic_json(REPORTS / "summary.json", value)
    return value


def run(args):
    global REPORTS
    if args.full:
        REPORTS = ROOT / "reports/model-evaluation/qwen27-quality-v1"
    work = private_dir(args.private)
    variants = args.variants or ["t03", "t01", "t00"]
    if len(set(variants)) != len(variants):
        raise ValueError("Duplicate variants are not independent experiments")
    REPORTS.mkdir(parents=True, exist_ok=True)
    resources, statuses = [], []
    stop = threading.Event()
    current = {"name": None}
    def sampler():
        while not stop.is_set():
            try:
                resources.append(sample(current["name"]))
            except Exception as exc:
                resources.append({"error": type(exc).__name__})
            atomic_json(REPORTS / "resources.json", {"condition": "Existing services retained; no host-exclusive guarantee", "samples": resources})
            stop.wait(15)
    for name in variants:
        if (REPORTS / (name + ".json")).exists():
            raise ValueError("Do not overwrite existing tuning receipts; use a separately versioned run")
    subprocess.run(["docker", "start", ENGINE], check=True, stdout=subprocess.DEVNULL)
    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    try:
        for name in variants:
            current["name"] = name
            temp, draft = VARIANTS[name]
            print(json.dumps({"startingQwenVariant": name, "temperature": temp, "draftTokens": draft}), flush=True)
            cmd = ["docker", "run", "--rm", "--name", "notbot-qwen-chat-" + name, "--network", "observatory_default",
                "-e", "RAG_DATA_ROOT=/data", "-e", "PYTHONPATH=/app", "-e", "HF_HUB_OFFLINE=1",
                "-e", "TRANSFORMERS_OFFLINE=1", "-e", "CUDA_VISIBLE_DEVICES=-1", "-e", "OMP_NUM_THREADS=2",
                "-v", "observatory_rag_api_data:/data:ro", "-v", f"{ROOT}/scripts/evaluation:/workspace/scripts/evaluation:ro",
                "-v", f"{work}:/private", "-v", f"{REPORTS}:/reports", IMAGE,
                "python", "-u", "/workspace/scripts/evaluation/compare_models.py", "pilot", "--private", "/private",
                "--cases", "/workspace/scripts/evaluation/model_cases_en_v2.json", "--output", f"/reports/{name}.json",
                "--model", "qwen38-27b", "--digest", PINS["qwen38-27b"], "--repeats", "3" if args.full else "2",
                "--profile-suffix", ("chat-quality-v1-" if args.full else "chat-tune-v1-") + name, "--raw-subdirectory", "qwen-tuning-outputs",
                "--temperature", str(temp), "--draft-tokens", str(draft)]
            if args.full:
                cmd.append("--all-cases")
            code = subprocess.run(cmd).returncode
            report_path = REPORTS / (name + ".json")
            receipt = json.loads(report_path.read_text()) if report_path.exists() else {}
            statuses.append({"variant": name, "exitCode": code, "complete": receipt.get("complete", False),
                "responses": len(receipt.get("results", [])), "passed": receipt.get("passed")})
            atomic_json(REPORTS / "run-status.json", {"models": statuses, "requestedVariants": variants,
                "driverSha256": sha(Path(__file__).read_bytes()), "complete": len(statuses) == len(variants)})
            print(json.dumps(statuses[-1]), flush=True)
            summarize(variants, full=args.full)
            if code or receipt.get("requestErrors") or not receipt.get("complete"):
                raise RuntimeError("Stop tuning after failed/incomplete request; do not queue abandoned requests")
    finally:
        stop.set()
        thread.join(timeout=30)
        subprocess.run(["docker", "stop", ENGINE], check=True, stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--variants", choices=VARIANTS, nargs="+")
    parser.add_argument("--full", action="store_true", help="All forty English cases three times, in a new versioned report directory")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
