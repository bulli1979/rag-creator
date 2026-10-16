#!/usr/bin/env python3
"""Read only installed Qwen metadata; never publish prompts or system text."""
import argparse
from datetime import datetime, timezone
import re
from compare_models import api, atomic_json, sha

NAMES = (
    "qwen3.8:27b", "qwen3.8-27b-coding:latest",
    "qwen3.8-27b-coding-stable:latest", "qwen3.8-27b-coding-256k:latest",
    "qwen3.8-27b-coding-stable-256k:latest",
)
OPTIONS = {"num_ctx", "num_predict", "temperature", "top_k", "top_p",
           "min_p", "repeat_penalty", "presence_penalty", "frequency_penalty",
           "draft_num_predict", "seed", "repeat_last_n"}


def safe_options(text):
    result = {}
    for line in text.splitlines():
        key, _, value = line.strip().partition(" ")
        if key in OPTIONS and re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()):
            result[key] = float(value) if "." in value else int(value)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--tuning", action="store_true", help="Inspect task-owned tuning profiles rather than live coding tags")
    args = parser.parse_args()
    # Run in the coding container's network namespace; its Docker network is
    # separate from NOTBot's. This makes metadata GET/POST only, never inference.
    engine = "http://127.0.0.1:11434"
    tags = api(engine, "/api/tags")["models"]
    rows = []
    names = ("qwen3.8:27b",) + tuple("notbot-eval-qwen38-27b:chat-tune-v1-" + v for v in ("t03", "t01", "t00")) if args.tuning else NAMES
    for name in names:
        tag = next(m for m in tags if m["name"] == name)
        shown = api(engine, "/api/show", {"model": name})
        match = re.search(r"(?m)^FROM .*sha256-([0-9a-f]{64})", shown.get("modelfile", ""))
        rows.append({"name": name, "manifestDigest": tag["digest"], "sizeBytes": tag["size"],
            "weightBlobSha256": match.group(1) if match else None,
            "parameters": safe_options(shown.get("parameters", "")),
            "parametersSha256": sha(shown.get("parameters", "").encode()),
            "templateSha256": sha(shown.get("template", "").encode()),
            "systemPresent": bool(shown.get("system")),
            "systemSha256": sha(shown["system"].encode()) if shown.get("system") else None,
            "details": tag.get("details"), "capabilities": shown.get("capabilities")})
    reference = rows[0]
    for row in rows:
        row["sameWeightsAsBase"] = bool(row["weightBlobSha256"]) and row["weightBlobSha256"] == reference["weightBlobSha256"]
        row["sameTemplateAsBase"] = row["templateSha256"] == reference["templateSha256"]
    atomic_json(args.output, {"recordedAt": datetime.now(timezone.utc).isoformat(),
        "models": rows, "residency": api(engine, "/api/ps"), "inferencePerformedByInspection": False,
        "inspectionScope": "task-owned tuning profiles" if args.tuning else "live coding profiles",
        "liveProfilesModified": False, "systemTextPublished": False})


if __name__ == "__main__":
    main()
