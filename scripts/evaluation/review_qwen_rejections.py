#!/usr/bin/env python3
"""Source-aware review of fresh Qwen test refusals, with no validator change.

Reports hashes, structural proof booleans and scoped public quantities only.
No prompts, raw claims, source bodies, historical audits or reasoning published.
"""
import argparse
import json
from pathlib import Path
import re

from compare_models import app_modules, application_identity, atomic_json, facets, private_dir, sha


def validate_receipt(receipt, full=False):
    if not receipt["complete"] or receipt.get("requestErrors"):
        raise ValueError("Review requires complete error-free receipts")
    if not full:
        if len(receipt["results"]) != 20:
            raise ValueError("Review requires the completed tuning stage")
        return
    bank = Path(__file__).with_name("model_cases_en_v2.json")
    ids = {c["id"] for c in json.loads(bank.read_text())}
    expected = {(repeat, case) for repeat in (1, 2, 3) for case in ids}
    actual = {(row["pass"], row["id"]) for row in receipt["results"]}
    if (receipt["casesSha256"] != sha(bank.read_bytes()) or receipt["repeats"] != 3
            or set(receipt["caseIds"]) != ids or actual != expected
            or len(actual) != len(receipt["results"])):
        raise ValueError("Full review requires the unchanged complete English bank three times")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full", action="store_true", help="Review completed 40-case/three-repeat receipts, not the initial tuning screen")
    args = parser.parse_args()
    paths = sorted(args.receipts.glob("t0*.json"))
    if not args.receipts.is_dir() or len(paths) != 3:
        raise ValueError("Exactly three complete tuning receipts required; empty review is not evidence")
    work = private_dir(args.private)
    _, _, validate, entails, available, revision = app_modules()
    from app import grounding
    from app.reference_answers import answer_reference
    from app.wavelength_reasoning import compare_wavelength
    if not available():
        raise ValueError("Pinned verifier required")
    frozen = json.loads((work / "frozen.json").read_text())
    if application_identity() != frozen["appPythonSha256"]:
        raise ValueError("Application differs from capture")
    entries = {entry["case"]["id"]: entry for entry in frozen["cases"]}
    reviews = []
    for path in paths:
        receipt = json.loads(path.read_text())
        validate_receipt(receipt, full=args.full)
        if receipt["frozenSha256"] != sha(frozen):
            raise ValueError("Frozen inputs differ")
        relative = Path(receipt["rawOutputsRelativeDirectory"])
        raw_directory = (work / relative).resolve()
        if relative.is_absolute() or not raw_directory.is_relative_to(work):
            raise ValueError("Refusing raw location outside private work")
        for row in receipt["results"]:
            if row["id"] not in {"fies_count", "notcam_below", "fabricated_citation"}:
                continue
            entry = entries[row["id"]]
            by_id = {key: item for item in entry["evidence"] for key in (item["citationId"], item.get("sourceRef")) if key}
            direct = answer_reference(entry["retrievalQuery"], entry["evidence"], "en") or compare_wavelength(entry["retrievalQuery"], entry["evidence"], "en")
            route = {"available": bool(direct)}
            if direct:
                route.update({"operation": direct.derivation["operation"], "abstained": direct.validation.abstained,
                    "facetsPass": not facets(entry["case"], direct.validation.answer, direct.validation.abstained, entry["chunks"]),
                    "answerSha256": sha(direct.validation.answer.encode())})
            for attempt in row["attempts"]:
                record = json.loads((raw_directory / f"{row['pass']}-{row['id']}-{attempt['attempt']}.json").read_text())
                raw = record["raw"]
                if sha(raw.encode()) != attempt["rawOutputSha256"]:
                    raise ValueError("Raw answer hash differs")
                checked = validate(raw, entry["evidence"], "en", historical_intent=entry["historicalIntent"],
                                   question=entry["retrievalQuery"], semantic_check=entails)
                if list(checked.rejection_reasons) != attempt["rejectionReasons"]:
                    raise ValueError("Rejection not reproducible against final checker")
                claims = (grounding._parse_json_object(raw) or {}).get("claims", [])
                details = []
                for claim in claims:
                    text = claim.get("text", "") if isinstance(claim, dict) else ""
                    supports = claim.get("evidence", []) if isinstance(claim, dict) else []
                    resolved = [by_id[s.get("citationId")] for s in supports if isinstance(s, dict) and s.get("citationId") in by_id]
                    quotes = [s.get("quote", "") for s in supports if isinstance(s, dict)]
                    exact = len(resolved) == len(supports) and all(isinstance(q, str) and grounding._normalized(q) in grounding._normalized(item["content"])
                        for q, item in zip(quotes, resolved))
                    counts = re.findall(r"\b(?:has|are|contains|provides|offers)\s+(?:a total of\s+)?(\d+)\s+(science|calibration|total)\s+(fibers?|fibres?)\b", grounding._number_words(text), re.I)
                    matches = [{"role": role.lower(), "assertedCount": int(count),
                        "derivedCounts": sorted({f["value"] for item in resolved for f in item.get("derivedFacts", []) if f["role"] == role.lower() and f["entity"] == "fiber"})}
                        for count, role, _ in counts]
                    for match in matches:
                        match["matchesDerivedFacts"] = match["derivedCounts"] == [match["assertedCount"]]
                    question_topics = grounding._question_topics(entry["retrievalQuery"])
                    claim_topics = grounding._question_topics(text + " " + " ".join(item.get("section", "") for item in resolved))
                    details.append({"claimSha256": sha(text.encode()), "supportsCount": len(supports),
                        "knownCitations": len(resolved) == len(supports), "exactQuotes": exact,
                        "inventoryAssertions": matches, "lexicalTopicIntersection": bool(question_topics & claim_topics),
                        "claimContainsExpectedFacets": all(re.search(p, text, re.I | re.S) for p in entry["case"].get("expect", [])),
                        "claimMentionsOutOfRangeOrNo": bool(re.search(r"\bno\b|cannot|can't|below|outside", text, re.I)),
                        "claimMentionsPublishedRange": bool(re.search(r"0\.8", text) and re.search(r"2\.5", text)),
                        "semanticEntailment": entails(text, quotes, resolved, "en") if text and resolved and all(isinstance(q,str) for q in quotes) else None})
                reviews.append({"profile": receipt["profile"], "id": row["id"], "pass": row["pass"], "attempt": attempt["attempt"],
                    "receiptSha256": sha(path.read_bytes()), "rejectionReasons": attempt["rejectionReasons"],
                    "acceptedClaims": checked.accepted_claims, "rejectedClaims": checked.rejected_claims,
                    "emptyClaims": not claims, "directRouteOnSameEvidence": route, "claims": details})
    atomic_json(args.output, {"appPythonSha256": frozen["appPythonSha256"], "frozenSha256": sha(frozen),
        "reviewerSha256": sha(Path(__file__).read_bytes()), "semanticCheckerRevision": revision,
        "scope": "Source-aware replay of fresh three-case Qwen refusals; proof diagnostics not human approval",
        "fullBankInputs": args.full,
        "liveCodeModified": False, "validatorRelaxed": False, "rawContentPublished": False,
        "historicalAuditsRead": False, "reviews": reviews})
    print(json.dumps({"attemptsReviewed": len(reviews), "rejectionsReproduced": True,
        "countClaimsMatchingDerivedFactsButNliFalse": sum(c["semanticEntailment"] is False and any(f["matchesDerivedFacts"] for f in c["inventoryAssertions"]) for r in reviews for c in r["claims"]),
        "rangeClaimsWithNoLexicalTopicIntersection": sum(r["id"] == "notcam_below" and c["claimMentionsPublishedRange"] and not c["lexicalTopicIntersection"] for r in reviews for c in r["claims"])}))


if __name__ == "__main__":
    main()
