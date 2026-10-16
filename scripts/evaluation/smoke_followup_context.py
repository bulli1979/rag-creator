#!/usr/bin/env python3
"""Live multi-turn regression for instrument context and checked wavelength reasoning."""

import argparse
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = []

    def check(question, history, patterns, resolution, method=None, abstained=False):
        request = Request(args.api_base_url.rstrip("/") + "/api/chat",
                          data=json.dumps({"message": question, "history": history, "language": "en"}).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=180) as response:
            result = json.load(response)
        answer, trace = result["answer"], result.get("trace", {})
        chunks = result.get("contextChunks", [])
        ids = set(re.findall(r"\[(D-[a-fA-F0-9]+-C\d+)\]", answer))
        errors = []
        if result.get("metrics", {}).get("abstained") != abstained:
            errors.append("wrong abstention status")
        if trace.get("contextResolution") != resolution:
            errors.append("wrong context resolution")
        if method and trace.get("answerMethod") != method:
            errors.append("wrong answer method")
        if not abstained and (not ids or not ids.issubset({c.get("citationId") for c in chunks})):
            errors.append("missing or unsupplied citation")
        for pattern in patterns:
            if not re.search(pattern, answer, re.I):
                errors.append(f"missing expected content: {pattern}")
        row = {"question": question, "answer": answer, "passed": not errors, "errors": errors,
               "historyUserTurns": [m["content"] for m in history if m["role"] == "user"],
               "sources": [c.get("fileName") for c in chunks],
               "trace": {key: trace.get(key) for key in (
                   "contextResolution", "answerMethod", "promptVersion", "promptSha256", "model", "corpusVersion",
                   "elapsedMs", "generationAttempts", "acceptedClaims", "rejectedClaims", "invalidCitations", "auditStored")}}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return answer

    first = "what is NOTCAM?"
    first_answer = check(first, [], ("NOTCAM", "infrared|SWIR"), "explicit")
    history = [{"role": "user", "content": first}, {"role": "assistant", "content": first_answer}]
    followup = "can the instrument be used to observer at 500nm?"
    answer = check(followup, history, (r"^No\.", "NOTCAM", r"0\.5", "below", r"0\.8", r"2\.5"),
                   "inherited", "wavelength-range-v1")
    chain = history + [{"role": "user", "content": followup}, {"role": "assistant", "content": answer}]
    check("Can it observe at 1000nm?", chain, ("NOTCAM", "within", "does not confirm"), "inherited", "wavelength-range-v1")
    check("Can it observe at 3000nm?", history, (r"^No\.", "NOTCAM", "above"), "inherited", "wavelength-range-v1")
    check("Can NOTCAM observe at 500nm?", [], (r"^No\.", "below"), "explicit", "wavelength-range-v1")
    check("Which wavelength range does it cover?", history, ("NOTCAM", r"0\.8", r"2\.5"), "inherited", "wavelength-range-v1")
    check("What is FIES?", history, ("FIES", "spectro"), "explicit")
    check("Can the instrument observe at 500nm?", [{"role": "user", "content": "Compare NOTCAM and ALFOSC."}],
          ("Which instrument",), "ambiguous", abstained=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
