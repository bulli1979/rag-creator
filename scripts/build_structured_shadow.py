#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "documentApi"))

from app.document_processing import structured_chunks

REQUIRED_METADATA = ("canonicalSource", "section", "authority", "status", "corpusVersion")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build(manifest_path: Path, input_root: Path, output_root: Path, target_chars: int) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus_version = str(manifest["corpusVersion"]) + "-structured-v1"
    documents = [d for d in manifest["documents"] if d["disposition"] in {"active", "historical"}]
    counts: Counter[str] = Counter()
    text_hashes = {"active": Counter(), "historical": Counter()}
    lengths: list[int] = []
    missing_files: list[str] = []
    phone_redaction_documents: list[str] = []
    preexisting_phone_placeholder_documents: list[str] = []
    quarantined_damaged_documents: list[str] = []
    built_files: list[dict] = []

    for record in sorted(documents, key=lambda item: (item["disposition"], item["sourcePath"])):
        group = "searchable" if record["disposition"] == "active" else "historical"
        source_path = input_root / group / record["sourcePath"]
        if not source_path.is_file():
            missing_files.append(str(source_path))
            continue
        raw = source_path.read_text(encoding="utf-8")
        if "[phone removed]" in raw.lower():
            preexisting_phone_placeholder_documents.append(record["sourcePath"])
        cid_count = raw.count("(cid:")
        replacement_count = raw.count("�")
        if cid_count >= 20 or replacement_count >= 20:
            quarantined_damaged_documents.append(record["sourcePath"])
            counts["documentsQuarantinedDamaged"] += 1
            counts[f"quarantined:{record['disposition']}"] += 1
            continue
        base_metadata = {
            "sourceId": record["sourceId"],
            "canonicalSource": record["canonicalLocation"],
            "canonicalUrl": record.get("sourceUrl") or "",
            "category": "" if record.get("category") == "[missing]" else record.get("category", ""),
            "instrument": "" if record.get("instrument") == "[missing]" else record.get("instrument", ""),
            "authority": record.get("authorityTier", "unclassified"),
            "status": record["disposition"],
            "validity": record.get("validity", ""),
            "corpusVersion": corpus_version,
            "contentHash": record["contentHash"],
            "version": record["version"],
        }
        chunks = structured_chunks(raw, target_chars=target_chars, base_metadata=base_metadata)
        if not chunks:
            counts["documentsWithoutChunks"] += 1
            continue
        document_id = sha256(f"{record['sourceId']}\n{record['contentHash']}")
        rows: list[str] = []
        redaction_in_doc = False
        for index, chunk in enumerate(chunks):
            metadata = {**chunk.metadata, "sourcePath": record["sourcePath"]}
            missing = [key for key in REQUIRED_METADATA if not metadata.get(key)]
            if missing:
                counts["chunksMissingRequiredMetadata"] += 1
            if "[phone removed]" in chunk.text.lower():
                counts["chunksWithPhoneRedaction"] += 1
                redaction_in_doc = True
            lowered = chunk.text.lower()
            if "back to top" in lowered or "last modified" in lowered:
                counts["chunksWithNavigationBoilerplate"] += 1
            for content_type in metadata.get("contentTypes", []):
                counts[f"contentType:{content_type}"] += 1
            lengths.append(len(chunk.text))
            text_hashes[record["disposition"]][sha256(chunk.text)] += 1
            rows.append(json.dumps({
                "chunkId": sha256(f"{document_id}:{index}"),
                "documentId": document_id,
                "chunkIndex": index,
                "text": chunk.text,
                "metadata": metadata,
            }, sort_keys=True, ensure_ascii=False))
        if redaction_in_doc:
            phone_redaction_documents.append(record["sourcePath"])
        destination = output_root / group / f"{Path(record['sourcePath']).stem}.jsonl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("\n".join(rows) + "\n", encoding="utf-8")
        built_files.append({
            "sourcePath": record["sourcePath"], "outputPath": str(destination.relative_to(output_root)),
            "disposition": record["disposition"], "chunks": len(chunks), "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        })
        counts["documentsBuilt"] += 1
        counts["chunksBuilt"] += len(chunks)
        counts[f"chunks:{record['disposition']}"] += len(chunks)
        counts[f"documents:{record['disposition']}"] += 1

    duplicate_metrics = {}
    for disposition, hashes in text_hashes.items():
        duplicate_metrics[disposition] = {
            "groups": sum(1 for count in hashes.values() if count > 1),
            "rowsBeyondFirst": sum(count - 1 for count in hashes.values() if count > 1),
        }

    report = {
        "schemaVersion": 1,
        "corpusVersion": corpus_version,
        "sourceManifest": str(manifest_path),
        "sourceManifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "inputRoot": str(input_root),
        "outputRoot": str(output_root),
        "targetChars": target_chars,
        "documentsSelected": len(documents),
        "documentsBuilt": counts["documentsBuilt"],
        "activeDocumentsBuilt": counts["documents:active"],
        "historicalDocumentsBuilt": counts["documents:historical"],
        "chunksBuilt": counts["chunksBuilt"],
        "activeChunksBuilt": counts["chunks:active"],
        "historicalChunksBuilt": counts["chunks:historical"],
        "documentsWithoutChunks": counts["documentsWithoutChunks"],
        "documentsQuarantinedDamaged": counts["documentsQuarantinedDamaged"],
        "activeDocumentsQuarantinedDamaged": counts["quarantined:active"],
        "historicalDocumentsQuarantinedDamaged": counts["quarantined:historical"],
        "quarantinedDamagedDocuments": quarantined_damaged_documents,
        "missingFiles": missing_files,
        "chunksMissingRequiredMetadata": counts["chunksMissingRequiredMetadata"],
        "chunksWithNavigationBoilerplate": counts["chunksWithNavigationBoilerplate"],
        "chunksWithPhoneRedaction": counts["chunksWithPhoneRedaction"],
        "documentsWithPhoneRedaction": phone_redaction_documents,
        "documentsWithPreexistingPhonePlaceholder": preexisting_phone_placeholder_documents,
        "exactDuplicateChunks": duplicate_metrics,
        "chunkCharacters": {
            "minimum": min(lengths) if lengths else 0,
            "median": statistics.median(lengths) if lengths else 0,
            "maximum": max(lengths) if lengths else 0,
        },
        "contentTypeCounts": {
            key.split(":", 1)[1]: value for key, value in sorted(counts.items()) if key.startswith("contentType:")
        },
        "files": built_files,
    }
    return report


def markdown_report(report: dict) -> str:
    return "\n".join([
        "# Phase 3 structured shadow audit", "",
        f"- Corpus version: `{report['corpusVersion']}`",
        f"- Documents selected/built: {report['documentsSelected']} / {report['documentsBuilt']} ({report['activeDocumentsBuilt']} active; {report['historicalDocumentsBuilt']} historical)",
        f"- Structured chunks: {report['chunksBuilt']} ({report['activeChunksBuilt']} active; {report['historicalChunksBuilt']} historical)",
        f"- Documents without meaningful chunks: {report['documentsWithoutChunks']}",
        f"- Damaged conversions quarantined: {report['documentsQuarantinedDamaged']} ({report['activeDocumentsQuarantinedDamaged']} active; {report['historicalDocumentsQuarantinedDamaged']} historical)",
        f"- Missing input files: {len(report['missingFiles'])}",
        f"- Chunks missing required metadata: {report['chunksMissingRequiredMetadata']}",
        f"- Chunks with navigation/modification boilerplate: {report['chunksWithNavigationBoilerplate']}",
        f"- Chunks with contact phone redaction: {report['chunksWithPhoneRedaction']}",
        f"- Input documents with pre-existing `[phone removed]`: {len(report['documentsWithPreexistingPhonePlaceholder'])}",
        f"- Active exact-duplicate rows beyond first: {report['exactDuplicateChunks']['active']['rowsBeyondFirst']}",
        f"- Historical exact-duplicate rows beyond first: {report['exactDuplicateChunks']['historical']['rowsBeyondFirst']}",
        f"- Documents with contact phone redaction: {len(report['documentsWithPhoneRedaction'])}",
        f"- Chunk characters min/median/max: {report['chunkCharacters']['minimum']} / {report['chunkCharacters']['median']} / {report['chunkCharacters']['maximum']}",
        "", "## Damaged conversions quarantined", "",
        *[f"- `{path}`" for path in report["quarantinedDamagedDocuments"]],
        "", "## Structure types", "",
        *[f"- {key}: {value}" for key, value in report["contentTypeCounts"].items()],
        "", "## Contact phone redactions", "",
        "These historical documents contain contact-formatted phone values redacted by the Phase 3 context-aware rule.", "",
        *[f"- `{path}`" for path in report["documentsWithPhoneRedaction"]], "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and audit the Phase 3 structured shadow corpus")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--report-json", required=True, type=Path)
    parser.add_argument("--report-markdown", required=True, type=Path)
    parser.add_argument("--target-chars", type=int, default=1200)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output_root.exists():
        if not args.force:
            raise SystemExit(f"Output exists; pass --force to rebuild: {args.output_root}")
        shutil.rmtree(args.output_root)
    report = build(args.manifest, args.input_root, args.output_root, max(400, args.target_chars))
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    args.report_markdown.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "documentsBuilt", "chunksBuilt", "activeChunksBuilt", "historicalChunksBuilt", "documentsWithoutChunks", "documentsQuarantinedDamaged", "chunksMissingRequiredMetadata",
        "chunksWithNavigationBoilerplate", "chunksWithPhoneRedaction",
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
