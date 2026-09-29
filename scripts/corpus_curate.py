#!/usr/bin/env python3
"""Build a deterministic, reversible NOTBot corpus manifest and shadow tree."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_audit


DISPOSITIONS = {"active", "historical", "quarantine", "excluded"}
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
YEAR_RE = re.compile(r"(?:^|[_-])((?:19|20)\d{2})(?:\D|$)")


def load_policy(path: Path) -> dict[str, Any]:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schemaVersion",
        "policyVersion",
        "corpusVersion",
        "expectedCorpusSnapshotSha256",
        "authorityByCategory",
        "qualityPolicy",
    }
    missing = sorted(required - set(policy))
    if missing:
        raise ValueError(f"Policy is missing required keys: {', '.join(missing)}")
    return policy


def stable_source_id(canonical_location: str) -> str:
    return hashlib.sha256(canonical_location.encode("utf-8")).hexdigest()


def canonical_location(
    source_url: str, relative_path: str, policy: dict[str, Any]
) -> tuple[str, str | None]:
    if not source_url:
        return f"urn:notbot:path:{relative_path}", None
    canonical = corpus_audit.canonicalize_url(source_url)
    url_path = urlsplit(source_url).path
    for family in policy.get("queryVariantFamilies", []):
        if url_path == family["path"]:
            return str(family["canonicalUrl"]), "query_variant_family"
    return canonical, None


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def shingles(text: str, width: int = 5) -> set[str]:
    tokens = tokenize(text)
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def simhash(items: set[str]) -> int:
    if not items:
        return 0
    weights = [0] * 64
    for item in items:
        value = int.from_bytes(hashlib.blake2b(item.encode(), digest_size=8).digest(), "big")
        for bit in range(64):
            weights[bit] += 1 if value & (1 << bit) else -1
    result = 0
    for bit, weight in enumerate(weights):
        if weight >= 0:
            result |= 1 << bit
    return result


def find_near_duplicates(
    bodies: dict[str, str], threshold: float, max_distance: int
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    prepared: dict[str, tuple[set[str], int]] = {}
    for path, body in sorted(bodies.items()):
        grams = shingles(body)
        prepared[path] = (grams, simhash(grams))

    parent = {path: path for path in prepared}

    def root(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        a, b = root(left), root(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    candidates: list[dict[str, Any]] = []
    paths = sorted(prepared)
    for index, left in enumerate(paths):
        left_grams, left_hash = prepared[left]
        if not left_grams:
            continue
        for right in paths[index + 1 :]:
            right_grams, right_hash = prepared[right]
            if (left_hash ^ right_hash).bit_count() > max_distance or not right_grams:
                continue
            score = len(left_grams & right_grams) / len(left_grams | right_grams)
            if score >= threshold:
                candidates.append({"left": left, "right": right, "jaccard": round(score, 6)})
                union(left, right)

    grouped: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        grouped[root(path)].append(path)
    clusters: dict[str, str] = {}
    for members in grouped.values():
        if len(members) < 2:
            continue
        cluster_id = "near-" + hashlib.sha256("\n".join(sorted(members)).encode()).hexdigest()[:12]
        for member in members:
            clusters[member] = cluster_id
    candidates.sort(key=lambda item: (-item["jaccard"], item["left"], item["right"]))
    return candidates, clusters


def projected_chunks(body: str, size: int = 900, overlap: int = 150) -> int:
    length = len(" ".join(body.split()))
    if not length:
        return 0
    if length <= size:
        return 1
    return 1 + math.ceil((length - size) / (size - overlap))


def classify(record: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    category = record["category"]
    instrument = record["instrument"]
    url = record["sourceUrl"] or ""
    url_path = urlsplit(url).path
    flags = set(record["qualityFlags"])
    if record["phoneRemovedOccurrences"]:
        flags.add("phone_removed")
    reasons: list[str] = []
    disposition = "active"
    proposed: str | None = None
    review_required = False

    if any(url_path.startswith(prefix) for prefix in policy.get("generatedPathPrefixes", [])):
        disposition, reasons = "excluded", ["generated_or_live_page"]
    else:
        for family in policy.get("queryVariantFamilies", []):
            if url_path == family["path"] and corpus_audit.canonicalize_url(url) != family["canonicalUrl"]:
                disposition, reasons = "excluded", ["redundant_query_variant"]
                break

    if disposition == "active" and category in policy.get("lowValueCategories", []):
        disposition, reasons = "excluded", ["non_operational_category"]
    quality = policy["qualityPolicy"]
    if disposition == "active" and quality.get("quarantineEncodingDamage") and flags & {
        "replacement_character",
        "nul_character",
    }:
        disposition, proposed, review_required = "quarantine", "active", True
        reasons = ["encoding_or_conversion_damage"]
    if disposition == "active" and quality.get("quarantinePhoneRemoved") and "phone_removed" in flags:
        disposition, proposed, review_required = "quarantine", "active", True
        reasons = ["pii_redaction_may_corrupt_technical_values"]
    if disposition == "active" and quality.get("quarantineMissingFrontmatter") and "missing_frontmatter" in flags:
        disposition, review_required = "quarantine", True
        reasons = ["missing_required_metadata"]
    if disposition == "active" and category in policy.get("quarantineCategories", []):
        disposition, review_required = "quarantine", True
        proposed = (
            "active"
            if any(url_path.startswith(prefix) for prefix in policy.get("internalActiveReviewPrefixes", []))
            else "quarantine"
        )
        reasons = ["internal_operations_requires_domain_review"]
    if disposition == "active" and category in policy.get("historicalCategories", []):
        disposition, proposed, review_required = "historical", "historical", True
        reasons = ["historical_fault_record_requires_domain_review"]
    if disposition == "active" and instrument in policy.get("historicalInstruments", []):
        disposition, proposed, review_required = "historical", "historical", True
        reasons = ["retired_instrument_documentation"]
    if disposition == "active" and record["nonWhitespaceBodyCharacters"] < policy["shortBodyReviewThreshold"]:
        disposition, proposed, review_required = "quarantine", "active", True
        reasons = ["short_content_requires_review"]
    if disposition == "active" and urlsplit(url).query:
        allowed = url_path in policy.get("queryPathAllowlist", []) or any(
            url_path == family["path"]
            and corpus_audit.canonicalize_url(url) == family["canonicalUrl"]
            for family in policy.get("queryVariantFamilies", [])
        )
        if not allowed:
            disposition, proposed, review_required = "quarantine", "active", True
            reasons = ["non_allowlisted_query_source"]

    if disposition not in DISPOSITIONS:
        raise AssertionError(disposition)
    authority = policy["authorityByCategory"].get(category, "tier_4_unknown")
    validity = {
        "active": "current",
        "historical": "historical",
        "quarantine": "review_pending",
        "excluded": "excluded",
    }[disposition]
    return {
        "disposition": disposition,
        "reasons": reasons or ["policy_default_active"],
        "reviewRequired": review_required,
        "proposedDisposition": proposed,
        "authorityTier": authority,
        "validity": validity,
        "qualityFlags": sorted(flags),
    }


def build_manifest(source_dir: Path, policy: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    audit = corpus_audit.audit_sources(source_dir)
    expected = policy["expectedCorpusSnapshotSha256"]
    if expected and audit["snapshotSha256"] != expected:
        raise ValueError(
            f"Corpus snapshot mismatch: expected {expected}, got {audit['snapshotSha256']}"
        )

    bodies: dict[str, str] = {}
    by_path = {item["path"]: item for item in audit["files"]}
    for relative in sorted(by_path):
        text = (source_dir / relative).read_text(encoding="utf-8", errors="replace")
        _, body = corpus_audit.parse_frontmatter(text)
        bodies[relative] = corpus_audit.normalize_body(body)
    pairs, near_clusters = find_near_duplicates(
        bodies,
        float(policy["nearDuplicateJaccardThreshold"]),
        int(policy["nearDuplicateMaxSimhashDistance"]),
    )

    exact_groups: dict[str, list[str]] = defaultdict(list)
    for item in audit["files"]:
        exact_groups[item["normalizedBodySha256"]].append(item["path"])
    exact_clusters: dict[str, str] = {}
    for members in exact_groups.values():
        if len(members) < 2:
            continue
        members = sorted(members)
        cluster = "exact-" + hashlib.sha256("\n".join(members).encode()).hexdigest()[:12]
        for member in members:
            exact_clusters[member] = cluster

    entries: list[dict[str, Any]] = []
    for relative, record in sorted(by_path.items()):
        location, family = canonical_location(record["sourceUrl"] or "", relative, policy)
        decision = classify(record, policy)
        match = YEAR_RE.search(relative)
        entries.append(
            {
                "sourceId": stable_source_id(location),
                "canonicalLocation": location,
                "sourcePath": relative,
                "sourceUrl": record["sourceUrl"],
                "processedSha256": record["sha256"],
                "contentHash": record.get("sourceHash") or record["normalizedBodySha256"],
                "version": 1,
                "lastCrawled": record["lastCrawled"],
                "category": record["category"],
                "instrument": record["instrument"],
                "year": int(match.group(1)) if match else None,
                "sourceType": record["sourceType"],
                "bodyCharacters": record["nonWhitespaceBodyCharacters"],
                "projectedLegacyChunks": projected_chunks(bodies[relative]),
                "duplicateCluster": exact_clusters.get(relative),
                "nearDuplicateCluster": near_clusters.get(relative),
                "queryVariantFamily": family,
                **decision,
            }
        )

    entry_by_path = {entry["sourcePath"]: entry for entry in entries}
    disposition_priority = {"active": 0, "historical": 1, "quarantine": 2, "excluded": 3}
    for members in exact_groups.values():
        if len(members) < 2:
            continue
        ranked = sorted(
            (entry_by_path[path] for path in members),
            key=lambda entry: (disposition_priority[entry["disposition"]], entry["sourcePath"]),
        )
        for loser in ranked[1:]:
            loser.update(
                disposition="excluded",
                reasons=["exact_duplicate_processed_body"],
                reviewRequired=False,
                proposedDisposition=None,
                validity="excluded",
            )

    active_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        if entry["disposition"] == "active":
            active_by_source[entry["sourceId"]].append(entry)
    for duplicates in active_by_source.values():
        for loser in sorted(duplicates, key=lambda x: x["sourcePath"])[1:]:
            loser.update(
                disposition="excluded",
                reasons=["duplicate_stable_source_identity"],
                reviewRequired=False,
                proposedDisposition=None,
                validity="excluded",
            )

    disposition_counts = Counter(entry["disposition"] for entry in entries)
    projected = Counter()
    for entry in entries:
        projected[entry["disposition"]] += entry["projectedLegacyChunks"]
    manifest = {
        "schemaVersion": 1,
        "policyVersion": policy["policyVersion"],
        "corpusVersion": policy["corpusVersion"],
        "sourceSnapshotSha256": audit["snapshotSha256"],
        "sourceFileCount": len(entries),
        "dispositionCounts": dict(sorted(disposition_counts.items())),
        "projectedLegacyChunkCounts": dict(sorted(projected.items())),
        "nearDuplicatePairCount": len(pairs),
        "documents": entries,
    }
    return manifest, pairs


def validate_manifest(manifest: dict[str, Any]) -> None:
    documents = manifest["documents"]
    if len(documents) != manifest["sourceFileCount"]:
        raise ValueError("Manifest source count mismatch")
    paths = [item["sourcePath"] for item in documents]
    if len(paths) != len(set(paths)):
        raise ValueError("A source path received multiple manifest decisions")
    active_ids = [item["sourceId"] for item in documents if item["disposition"] == "active"]
    if len(active_ids) != len(set(active_ids)):
        raise ValueError("Multiple active documents share a stable source ID")
    for item in documents:
        if item["disposition"] not in DISPOSITIONS or not item["reasons"]:
            raise ValueError(f"Invalid disposition for {item['sourcePath']}")


def write_review_queue(path: Path, manifest: dict[str, Any]) -> None:
    fields = [
        "sourcePath",
        "category",
        "instrument",
        "disposition",
        "proposedDisposition",
        "authorityTier",
        "reasons",
        "qualityFlags",
        "sourceUrl",
        "ownerDecision",
        "ownerNotes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in manifest["documents"]:
            if not item["reviewRequired"]:
                continue
            writer.writerow(
                {
                    **{key: item.get(key) for key in fields},
                    "reasons": ";".join(item["reasons"]),
                    "qualityFlags": ";".join(item["qualityFlags"]),
                    "ownerDecision": "",
                    "ownerNotes": "",
                }
            )


def write_report(path: Path, manifest: dict[str, Any], pairs: list[dict[str, Any]]) -> None:
    docs = manifest["documents"]
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    reasons = Counter()
    review = 0
    for item in docs:
        by_category[item["category"]][item["disposition"]] += 1
        reasons.update(item["reasons"])
        review += int(item["reviewRequired"])
    active_chunks = manifest["projectedLegacyChunkCounts"].get("active", 0)
    baseline_chunks = 44419
    reduction = 100 * (1 - active_chunks / baseline_chunks)
    lines = [
        "# Phase 1 corpus-policy dry run",
        "",
        f"Policy: `{manifest['policyVersion']}`  ",
        f"Corpus version: `{manifest['corpusVersion']}`  ",
        f"Source snapshot: `{manifest['sourceSnapshotSha256']}`",
        "",
        "## Outcome",
        "",
        "| Disposition | Documents | Projected legacy chunks |",
        "|---|---:|---:|",
    ]
    for disposition in sorted(DISPOSITIONS):
        lines.append(
            f"| {disposition} | {manifest['dispositionCounts'].get(disposition, 0)} | "
            f"{manifest['projectedLegacyChunkCounts'].get(disposition, 0)} |"
        )
    lines.extend(
        [
            "",
            f"Projected default-search active chunks: **{active_chunks:,}**, a **{reduction:.1f}%** reduction from the 44,419 live-row baseline. This projection removes stale versions as well as policy-excluded sources; it is not an evaluation result.",
            "",
            f"Domain-owner review queue: **{review} documents**.  ",
            f"Near-duplicate candidate pairs: **{len(pairs)}**.",
            "",
            "## Dispositions by category",
            "",
            "| Category | Active | Historical | Quarantine | Excluded |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for category, counts in sorted(by_category.items()):
        lines.append(
            f"| {category} | {counts['active']} | {counts['historical']} | "
            f"{counts['quarantine']} | {counts['excluded']} |"
        )
    lines.extend(
        [
            "",
            "## Decision reasons",
            "",
            "| Reason | Documents |",
            "|---|---:|",
        ]
    )
    for reason, count in sorted(reasons.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {reason} | {count} |")
    lines.extend(
        [
            "",
            "## Readiness",
            "",
            "The shadow corpus is a policy candidate, not a production-ready replacement. Domain-owner decisions and comparative retrieval/answer evaluation remain required before rollout.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_shadow(source_dir: Path, target: Path, manifest: dict[str, Any]) -> None:
    if target.exists():
        raise FileExistsError(f"Shadow target already exists: {target}")
    (target / "searchable").mkdir(parents=True)
    (target / "historical").mkdir(parents=True)
    copied = Counter()
    for item in manifest["documents"]:
        disposition = item["disposition"]
        if disposition not in {"active", "historical"}:
            continue
        section = "searchable" if disposition == "active" else "historical"
        destination = target / section / item["sourcePath"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_dir / item["sourcePath"], destination)
        copied[disposition] += 1
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (target / "README.md").write_text(
        "# NOTBot shadow corpus\n\n"
        f"Corpus version: `{manifest['corpusVersion']}`\n\n"
        "- `searchable/` contains active sources for default retrieval.\n"
        "- `historical/` is isolated and must only be searched explicitly.\n"
        "- Quarantine and excluded sources are represented only in `manifest.json`.\n\n"
        f"Copied active: {copied['active']}  \nCopied historical: {copied['historical']}\n",
        encoding="utf-8",
    )
    validation = validate_shadow(source_dir, target, manifest)
    (target / "validation.json").write_text(
        json.dumps(validation, indent=2) + "\n", encoding="utf-8"
    )


def validate_shadow(
    source_dir: Path, target: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    expected = {
        "active": {
            item["sourcePath"]
            for item in manifest["documents"]
            if item["disposition"] == "active"
        },
        "historical": {
            item["sourcePath"]
            for item in manifest["documents"]
            if item["disposition"] == "historical"
        },
    }
    roots = {"active": target / "searchable", "historical": target / "historical"}
    by_path = {item["sourcePath"]: item for item in manifest["documents"]}
    checked = 0
    for disposition, root in roots.items():
        actual = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        if actual != expected[disposition]:
            raise ValueError(
                f"Shadow {disposition} membership mismatch: "
                f"missing={sorted(expected[disposition] - actual)[:5]}, "
                f"extra={sorted(actual - expected[disposition])[:5]}"
            )
        for relative in sorted(actual):
            copied_hash = corpus_audit.sha256_file(root / relative)
            if copied_hash != by_path[relative]["processedSha256"]:
                raise ValueError(f"Shadow hash mismatch: {relative}")
            if copied_hash != corpus_audit.sha256_file(source_dir / relative):
                raise ValueError(f"Shadow differs from source: {relative}")
            checked += 1
    return {
        "status": "ok",
        "activeFiles": len(expected["active"]),
        "historicalFiles": len(expected["historical"]),
        "filesHashChecked": checked,
        "quarantineOrExcludedFilesInShadow": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--report-out", type=Path, required=True)
    parser.add_argument("--review-queue-out", type=Path, required=True)
    parser.add_argument("--near-duplicates-out", type=Path, required=True)
    parser.add_argument("--shadow-dir", type=Path)
    args = parser.parse_args()

    policy = load_policy(args.policy)
    manifest, pairs = build_manifest(args.source_dir, policy)
    validate_manifest(manifest)
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_report(args.report_out, manifest, pairs)
    write_review_queue(args.review_queue_out, manifest)
    args.near_duplicates_out.parent.mkdir(parents=True, exist_ok=True)
    args.near_duplicates_out.write_text(
        json.dumps(
            {
                "threshold": policy["nearDuplicateJaccardThreshold"],
                "maxSimhashDistance": policy["nearDuplicateMaxSimhashDistance"],
                "pairCount": len(pairs),
                "pairs": pairs,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if args.shadow_dir:
        build_shadow(args.source_dir, args.shadow_dir, manifest)
    print(json.dumps({"dispositions": manifest["dispositionCounts"], "nearDuplicatePairs": len(pairs)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
