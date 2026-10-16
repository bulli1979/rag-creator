#!/usr/bin/env python3
"""Reconvert only already-approved active sources from the preserved crawl.

Never crawls, expands access, reactivates excluded material, or changes originals.
Output belongs in a private ignored shadow directory, not in Git.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "documentApi"))
from app.document_processing import parse_frontmatter, scrub_sensitive_text
from app.html_processing import html_to_markdown, meaningful_title
from app.source_policy import annotate_source


def build(curated: Path, crawl: Path, output: Path, version: str, reviewed: set[str] | None = None,
          verified_excerpts: Path | None = None, reviewed_extraction: dict | None = None) -> dict:
    if output.exists():
        raise ValueError("Output already exists; choose a new recovery version")
    manifest = json.loads((curated / "manifest.json").read_text())
    raw_manifest = json.loads((crawl / "crawl_manifest.json").read_text())["entries"]
    destination = output / "searchable"
    destination.mkdir(parents=True)
    reviewed=reviewed or set()
    known={r['sourcePath']:r for r in manifest['documents']}
    for name in reviewed:
        record=known.get(name)
        if not record or record['disposition']!='quarantine' or '/intranot/' in record['canonicalLocation']:
            raise ValueError('Reviewed additions must be explicit public quarantined sources')
    report = {"corpusVersion": version, "convertedHtml": [], "repairedPdf": [], "retainedMarkdown": [], "quarantinedDamaged": [], "missingRawHtml": [],'reviewedAdditions':sorted(reviewed)}
    for record in manifest["documents"]:
        if record["disposition"] != "active" and record['sourcePath'] not in reviewed:
            continue
        source = curated / "searchable" / record["sourcePath"]
        if record['sourcePath'] in reviewed:
            source=crawl/'processed'/record['sourcePath']
        raw = source.read_text()
        metadata, body = parse_frontmatter(raw)
        # Preserve the original crawl URL (including significant trailing slash)
        # so ingestion resolves to the existing stable source identity.
        url = metadata.get("source_url") or record.get("sourceUrl") or record["canonicalLocation"]
        entry = raw_manifest.get(url)
        if entry and "html" in entry.get("content_type", ""):
            path = crawl / entry["local_path"]
            if path.is_file():
                html = path.read_text(errors="replace")
                body = html_to_markdown(html)
                metadata["title"] = meaningful_title(html, url)
                report["convertedHtml"].append(record["sourcePath"])
            else:
                report["missingRawHtml"].append(record["sourcePath"])
        else:
            report["retainedMarkdown"].append(record["sourcePath"])
        extraction=(reviewed_extraction or {}).get(record['sourcePath'])
        if ("(cid:" in body or body.count("�") >= 3 or record['sourcePath'] in reviewed or extraction) and entry and "pdf" in entry.get("content_type", ""):
            path = crawl / entry["local_path"]
            if path.is_file():
                if extraction and hashlib.sha256(path.read_bytes()).hexdigest()!=extraction['sourceHash']:
                    raise ValueError('Reviewed extraction does not match the original PDF')
                options=['-layout'] if not extraction or extraction.get('layout',True) else []
                recovered = subprocess.run(["pdftotext", *options, str(path), "-"],
                                           check=True, capture_output=True, text=True).stdout
                if recovered.strip() and "(cid:" not in recovered and recovered.count("�") < 3:
                    # Preserve page boundaries; this does not promote a design
                    # paper into current operational guidance.
                    body = "\n\n".join(page.strip() for page in recovered.split("\f") if page.strip()) + "\n"
                    metadata["conversion_method"] = "pdftotext-layout-recovery"
                    report["repairedPdf"].append(record["sourcePath"])
                    if extraction:
                        for control in extraction.get('discardControls',[]):
                            if len(control)!=1 or ord(control)>31:
                                raise ValueError('Only reviewed control glyphs may be discarded')
                            body=body.replace(control,'')
                        metadata['conversion_method']='reviewed-pdftotext-reading-order'
        if verified_excerpts and (verified_excerpts/record['sourcePath']).is_file():
            overlay_metadata,body=parse_frontmatter((verified_excerpts/record['sourcePath']).read_text())
            path=crawl/entry['local_path'] if entry else None
            if not path or hashlib.sha256(path.read_bytes()).hexdigest()!=overlay_metadata.get('source_hash'):
                raise ValueError('Verified excerpt does not match the original source hash')
            metadata.update(overlay_metadata)
        if "(cid:" in body or body.count("�") >= 3 or re.search(r'[\x00-\x08\x0b\x0e-\x1f]',body):
            report["quarantinedDamaged"].append(record["sourcePath"])
            continue
        # Retain the producer's credential/host/address redaction too when
        # reconverting raw files; recovery must not undo prior privacy work.
        producer=ROOT.parent/'NOTBot-documents'
        if str(producer) not in sys.path:
            sys.path.insert(0,str(producer))
        from scrubber import scrub
        body = scrub_sensitive_text(scrub(body,source_label=record['sourcePath']))
        instrument = annotate_source({"canonicalLocation":url, "instrument":metadata.get('instrument') or record.get("instrument", "")}).get("instrument", "")
        metadata.update(source_url=url, category=record.get("category", ""),
                        instrument=instrument, authority=record["authorityTier"],
                        status=metadata.get('status','active'), corpus_version=version,
                        content_hash=hashlib.sha256(body.encode()).hexdigest())
        front = "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in metadata.items())
        (destination / record["sourcePath"]).write_text("---\n" + front + "\n---\n\n" + body)
    report["documentsBuilt"] = len(list(destination.glob("*.md")))
    (output / "conversion-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curated", type=Path, required=True)
    parser.add_argument("--crawl-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument('--reviewed-sources',type=Path,help='Explicit reviewed public quarantined paths (JSON array)')
    parser.add_argument('--verified-excerpts',type=Path,help='Private source-hash-verified visual transcriptions')
    parser.add_argument('--reviewed-extraction',type=Path,help='Source-hash-bound PDF extraction review JSON')
    args = parser.parse_args()
    reviewed=set(json.loads(args.reviewed_sources.read_text())) if args.reviewed_sources else set()
    extraction=json.loads(args.reviewed_extraction.read_text()) if args.reviewed_extraction else {}
    report = build(args.curated, args.crawl_data, args.output, args.version, reviewed,args.verified_excerpts,extraction)
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k,v in report.items()}, indent=2))
