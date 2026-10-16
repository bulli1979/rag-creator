#!/usr/bin/env python3
"""Recover reporting after a driver interruption; never rerun inference.

Verify all three complete receipts and their private outputs before rebuilding
the derived summary. Preserve the interrupted driver checkpoint verbatim.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from compare_models import atomic_json, private_dir, sha
import run_qwen_chat_tuning as tuning


def verify_outputs(work, receipt, frozen):
    if not receipt["complete"] or receipt["requestErrors"]:
        raise ValueError("Incomplete/error receipt cannot be recovered as complete")
    if receipt["frozenSha256"] != sha(frozen):
        raise ValueError("Frozen evidence identity differs")
    if receipt["appPythonSha256"] != frozen["appPythonSha256"]:
        raise ValueError("Application identity differs")
    entries = {entry["case"]["id"]: entry for entry in frozen["cases"]}
    directory = (work / receipt["rawOutputsRelativeDirectory"]).resolve()
    if not directory.is_relative_to(work):
        raise ValueError("Private output directory escaped")
    attempts = 0
    for row in receipt["results"]:
        entry = entries[row["id"]]
        if row["promptSha256"] != sha(entry["messages"]) or row["evidenceSha256"] != sha(entry["evidence"]):
            raise ValueError("Initial prompt/evidence identity differs")
        if row["requestError"] or len(row["attempts"]) != row["generationAttempts"]:
            raise ValueError("Attempt completeness differs")
        answer_found = False
        for attempt in row["attempts"]:
            path = directory / f"{row['pass']}-{row['id']}-{attempt['attempt']}.json"
            if not path.resolve().is_relative_to(work):
                raise ValueError("Private output file escaped")
            record = json.loads(path.read_text())
            if sha(record["raw"].encode()) != attempt["rawOutputSha256"]:
                raise ValueError("Raw output hash differs")
            answer_found |= sha(record["validatedAnswer"].encode()) == row["answerSha256"]
            attempts += 1
        if not answer_found:
            raise ValueError("Final validated answer hash absent")
    if sum(row["passed"] for row in receipt["results"]) != receipt["passed"]:
        raise ValueError("Stored pass count differs")
    return attempts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    args = parser.parse_args()
    work = private_dir(args.private)
    reports = args.receipts.resolve()
    frozen = json.loads((work / "frozen.json").read_text())
    identities = {}
    total_attempts = 0
    for name in ("t03", "t01", "t00"):
        path = reports / (name + ".json")
        receipt = json.loads(path.read_text())
        if receipt["harnessSha256"] != sha(Path(__file__).with_name("compare_models.py").read_bytes()):
            raise ValueError("Generator harness identity differs")
        total_attempts += verify_outputs(work, receipt, frozen)
        identities[name] = sha(path.read_bytes())
    tuning.REPORTS = reports
    summary = tuning.summarize(["t03", "t01", "t00"], full=True)
    if not summary["allComplete"]:
        raise ValueError("Full English bank not complete")
    checkpoint = reports / "run-status.json"
    atomic_json(reports / "interruption-recovery.json", {
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "responses": sum(row["responses"] for row in summary["models"]),
        "generationAttemptsVerified": total_attempts,
        "receiptSha256": identities,
        "frozenSha256": sha(frozen),
        "appPythonSha256": frozen["appPythonSha256"],
        "originalDriverCheckpointSha256": sha(checkpoint.read_bytes()),
        "originalDriverCheckpointModified": False,
        "originalDriverComplete": json.loads(checkpoint.read_text())["complete"],
        "recoveredAllResponseReceiptsComplete": True,
        "rawOutputsAndFinalAnswerHashesVerified": True,
        "recoveryScriptSha256": sha(Path(__file__).read_bytes()),
        "inferenceRerun": False, "qualityApproved": False,
        "liveSettingsModified": False, "originalReceiptsModified": False,
    })
    print(json.dumps({"responses": 360, "attemptsVerified": total_attempts,
                      "allComplete": True, "qualityApproved": False}))


if __name__ == "__main__":
    main()
