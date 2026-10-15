#!/usr/bin/env python3
"""Review new NOTCAM procedure outputs against their supplied source scope.

No proof/score change and no prompt/source body published. Accepts partial
receipts as diagnostic snapshots only, never as complete model certification.
"""
import argparse
import json
from pathlib import Path
import re

from compare_models import app_modules, application_identity, atomic_json, facets, private_dir, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    work = private_dir(args.private)
    paths = sorted(args.receipts.glob("t0*.json"))
    if not paths:
        raise ValueError("No model receipts to review")
    app_modules()
    from app import grounding
    from app.evidence_selection import classify_query
    from app.sourced_procedures import answer_procedure
    frozen = json.loads((work / "frozen.json").read_text())
    if application_identity() != frozen["appPythonSha256"]:
        raise ValueError("Application differs")
    entries = {e["case"]["id"]: e for e in frozen["cases"]}
    reviews = []
    for path in paths:
        receipt = json.loads(path.read_text())
        if receipt["frozenSha256"] != sha(frozen):
            raise ValueError("Frozen identity differs")
        directory = (work / receipt["rawOutputsRelativeDirectory"]).resolve()
        if not directory.is_relative_to(work):
            raise ValueError("Not a private test output location")
        for row in receipt["results"]:
            if row["id"] not in {"notcam_abort", "notcam_unsafe_abort"}:
                continue
            entry = entries[row["id"]]
            matches = []
            for attempt in row["attempts"]:
                record = json.loads((directory / f"{row['pass']}-{row['id']}-{attempt['attempt']}.json").read_text())
                if sha(record["raw"].encode()) != attempt["rawOutputSha256"]:
                    raise ValueError("Raw output differs")
                if sha(record["validatedAnswer"].encode()) == row["answerSha256"]:
                    matches.append(record)
            if not matches:
                raise ValueError("Final answer not found by hash")
            record = matches[-1]
            by_id = {key: item for item in entry["evidence"] for key in (item["citationId"], item.get("sourceRef")) if key}
            claims = (grounding._parse_json_object(record["raw"]) or {}).get("claims", [])
            details = []
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                text = claim.get("text", "")
                supports = claim.get("evidence", [])
                sources = []
                for support in supports:
                    item = by_id.get(support.get("citationId"))
                    if not item:
                        continue
                    quote = support.get("quote", "")
                    sources.append({"citationId": item["citationId"], "instrument": item.get("instrument"),
                        "sourceRole": item.get("sourceRole"), "status": item.get("status"),
                        "sectionSha256": sha(item.get("section", "").encode()),
                        "quoteMentionsNOTCAM": "NOTCAM" in classify_query(quote).instruments,
                        "quoteExactInSource": grounding._normalized(quote) in grounding._normalized(item["content"]),
                        "citedItemContainsNOTCAMAbortException": bool(re.search(r"abort.{0,100}not.{0,40}NOTCam", item["content"], re.I | re.S))})
                details.append({"claimSha256": sha(text.encode()),
                    "claimMentionsNOTCAM": "NOTCAM" in classify_query(text).instruments,
                    "claimContainsTypeAbort": bool(re.search(r"\btype\s+abort\b", text, re.I)),
                    "claimContainsAbortNegation": bool(re.search(r"abort.{0,80}(?:not|never)|(?:not|never).{0,80}abort", text, re.I)),
                    "sources": sources})
            direct = answer_procedure(entry["retrievalQuery"], entry["evidence"], "en")
            answer = record["validatedAnswer"]
            reviews.append({"profile": receipt["profile"], "receiptComplete": receipt["complete"],
                "receiptSha256": sha(path.read_bytes()), "id": row["id"], "pass": row["pass"],
                "originalPassed": row["passed"], "abstained": row["abstained"], "answerSha256": row["answerSha256"],
                "validatedAnswerContainsTypeAbort": bool(re.search(r"\btype\s+abort\b", answer, re.I)),
                "validatedAnswerContainsAbortNegation": bool(re.search(r"abort.{0,80}(?:not|never)|(?:not|never).{0,80}abort", answer, re.I)),
                "directProcedureRouteOnSameEvidence": {"available": bool(direct),
                    "operation": direct.derivation["operation"] if direct else None,
                    "facetsPass": not facets(entry["case"], direct.validation.answer, direct.validation.abstained, entry["chunks"]) if direct else None},
                "claims": details})
    if not reviews:
        raise ValueError("No NOTCAM procedure results available")
    atomic_json(args.output, {"scope": "New test procedure/source scope diagnostic, not human safety approval",
        "appPythonSha256": frozen["appPythonSha256"], "reviewerSha256": sha(Path(__file__).read_bytes()),
        "liveCodeModified": False, "scoresModified": False, "rawContentPublished": False,
        "allInputReceiptsComplete": all(r["receiptComplete"] for r in reviews), "reviews": reviews})
    print(json.dumps({"answersReviewed": len(reviews), "validatedTypeAbortAnswers": sum(r["validatedAnswerContainsTypeAbort"] for r in reviews),
        "negationAndTypeAbortTogether": sum(r["validatedAnswerContainsTypeAbort"] and r["validatedAnswerContainsAbortNegation"] for r in reviews)}))


if __name__ == "__main__":
    main()
