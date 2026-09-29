#!/usr/bin/env python3
"""Create a deterministic NOTBot corpus/index baseline report.

The command audits processed source documents, the API's SQLite document
metadata, and the live PostgreSQL vector table. It does not read deployment
secrets; Docker-based PostgreSQL access uses local container authentication.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlsplit, urlunsplit


SHORT_BODY_NON_WHITESPACE = 100
SAMPLE_LIMIT = 20
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
PHONE_REMOVED_RE = re.compile(r"\[phone removed\]", re.IGNORECASE)
BOILERPLATE_PATTERNS = {
    "backToTop": re.compile(r"\bback\s+to\s+top\b", re.IGNORECASE),
    "lastModified": re.compile(r"\blast\s+modified\b", re.IGNORECASE),
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse scalar frontmatter fields without requiring a YAML package."""

    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    metadata: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        key, separator, value = raw_line.partition(":")
        if not separator or not key.strip():
            continue
        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1]
        metadata[key.strip()] = cleaned
    return metadata, text[match.end() :]


def normalize_body(body: str) -> str:
    return " ".join(body.split())


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = "&".join(
        f"{key}={value}"
        for key, value in sorted(parse_qsl(parts.query, keep_blank_values=True))
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def infer_source_type(metadata: dict[str, str], source_url: str, path: Path) -> str:
    explicit = (metadata.get("source_format") or metadata.get("file_type") or "").lower()
    if "pdf" in explicit:
        return "pdf"
    if explicit:
        return explicit
    url_path = urlsplit(source_url).path.lower() if source_url else ""
    filename = path.name.lower()
    if url_path.endswith(".pdf") or filename.endswith("-pdf.md"):
        return "pdf"
    if url_path.endswith(".php") or "-php" in filename:
        return "dynamic_php"
    if url_path.endswith((".html", ".htm")) or filename.endswith(
        ("-html.md", "-htm.md")
    ):
        return "html"
    if source_url and urlsplit(source_url).query:
        return "dynamic_web"
    return "web_or_generated_markdown"


def _duplicate_summary(groups: dict[str, list[str]]) -> dict[str, Any]:
    duplicates = [sorted(paths) for paths in groups.values() if len(paths) > 1]
    duplicates.sort(key=lambda paths: (-len(paths), paths[0]))
    return {
        "groups": len(duplicates),
        "rowsBeyondFirst": sum(len(paths) - 1 for paths in duplicates),
        "maxCopies": max((len(paths) for paths in duplicates), default=1),
        "samples": duplicates[:SAMPLE_LIMIT],
    }


def audit_sources(source_dir: Path) -> dict[str, Any]:
    if not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    extension_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    instrument_counts: Counter[str] = Counter()
    source_type_counts: Counter[str] = Counter()
    content_hash_groups: dict[str, list[str]] = defaultdict(list)
    normalized_body_groups: dict[str, list[str]] = defaultdict(list)
    source_url_groups: dict[str, list[str]] = defaultdict(list)
    source_hash_groups: dict[str, list[str]] = defaultdict(list)
    phone_files: list[str] = []
    phone_occurrences = 0
    boilerplate_files: dict[str, list[str]] = defaultdict(list)
    boilerplate_occurrences: Counter[str] = Counter()
    short_body_files: list[str] = []
    empty_body_files: list[str] = []
    query_parameter_sources: list[dict[str, str]] = []
    missing_frontmatter: list[str] = []
    replacement_character_files: list[str] = []
    nul_character_files: list[str] = []
    records: list[dict[str, Any]] = []
    total_bytes = 0
    fingerprint = hashlib.sha256()

    for path in files:
        relative = path.relative_to(source_dir).as_posix()
        raw = path.read_bytes()
        total_bytes += len(raw)
        raw_hash = sha256_bytes(raw)
        fingerprint.update(relative.encode("utf-8"))
        fingerprint.update(b"\0")
        fingerprint.update(raw_hash.encode("ascii"))
        fingerprint.update(b"\n")
        extension_counts[path.suffix.lower() or "[none]"] += 1

        text = raw.decode("utf-8", errors="replace")
        metadata, body = parse_frontmatter(text)
        normalized = normalize_body(body)
        non_whitespace_length = len(re.sub(r"\s+", "", body))
        category = metadata.get("category", "[missing]") or "[missing]"
        instrument = metadata.get("instrument", "[missing]") or "[missing]"
        source_url = metadata.get("source_url", "").strip()
        source_hash = metadata.get("source_hash", "").strip()
        source_type = infer_source_type(metadata, source_url, path)

        category_counts[category] += 1
        instrument_counts[instrument] += 1
        source_type_counts[source_type] += 1
        content_hash_groups[raw_hash].append(relative)
        normalized_body_groups[sha256_bytes(normalized.encode("utf-8"))].append(relative)
        if not metadata:
            missing_frontmatter.append(relative)
        if source_url:
            source_url_groups[canonicalize_url(source_url)].append(relative)
            if urlsplit(source_url).query:
                query_parameter_sources.append({"file": relative, "sourceUrl": source_url})
        if source_hash:
            source_hash_groups[source_hash].append(relative)

        phone_count = len(PHONE_REMOVED_RE.findall(text))
        if phone_count:
            phone_files.append(relative)
            phone_occurrences += phone_count
        for name, pattern in BOILERPLATE_PATTERNS.items():
            count = len(pattern.findall(text))
            if count:
                boilerplate_files[name].append(relative)
                boilerplate_occurrences[name] += count
        if non_whitespace_length == 0:
            empty_body_files.append(relative)
        if non_whitespace_length < SHORT_BODY_NON_WHITESPACE:
            short_body_files.append(relative)
        if "\ufffd" in text:
            replacement_character_files.append(relative)
        if "\x00" in text:
            nul_character_files.append(relative)

        records.append(
            {
                "path": relative,
                "bytes": len(raw),
                "sha256": raw_hash,
                "normalizedBodySha256": sha256_bytes(normalized.encode("utf-8")),
                "nonWhitespaceBodyCharacters": non_whitespace_length,
                "category": category,
                "instrument": instrument,
                "sourceType": source_type,
                "sourceUrl": source_url or None,
                "sourceHash": source_hash or None,
                "lastCrawled": metadata.get("last_crawled") or None,
                "phoneRemovedOccurrences": phone_count,
                "qualityFlags": sorted(
                    flag
                    for flag, enabled in {
                        "empty_body": non_whitespace_length == 0,
                        "short_body": non_whitespace_length < SHORT_BODY_NON_WHITESPACE,
                        "missing_frontmatter": not metadata,
                        "query_parameter_url": bool(
                            source_url and urlsplit(source_url).query
                        ),
                        "replacement_character": "\ufffd" in text,
                        "nul_character": "\x00" in text,
                        "back_to_top": bool(
                            BOILERPLATE_PATTERNS["backToTop"].search(text)
                        ),
                        "last_modified": bool(
                            BOILERPLATE_PATTERNS["lastModified"].search(text)
                        ),
                    }.items()
                    if enabled
                ),
            }
        )

    query_parameter_sources.sort(key=lambda item: item["file"])
    return {
        "root": str(source_dir.resolve()),
        "snapshotSha256": fingerprint.hexdigest(),
        "fileCount": len(files),
        "totalBytes": total_bytes,
        "extensionCounts": dict(sorted(extension_counts.items())),
        "categoryCounts": dict(sorted(category_counts.items())),
        "instrumentCounts": dict(sorted(instrument_counts.items())),
        "sourceTypeCounts": dict(sorted(source_type_counts.items())),
        "uniqueCanonicalSourceUrls": len(source_url_groups),
        "filesMissingFrontmatter": len(missing_frontmatter),
        "filesMissingFrontmatterSamples": sorted(missing_frontmatter)[:SAMPLE_LIMIT],
        "exactFileDuplicates": _duplicate_summary(content_hash_groups),
        "normalizedBodyDuplicates": _duplicate_summary(normalized_body_groups),
        "canonicalUrlsWithMultipleFiles": _duplicate_summary(source_url_groups),
        "sourceHashesWithMultipleFiles": _duplicate_summary(source_hash_groups),
        "queryParameterSourceCount": len(query_parameter_sources),
        "queryParameterSources": query_parameter_sources,
        "phoneRemovedFileCount": len(phone_files),
        "phoneRemovedOccurrences": phone_occurrences,
        "phoneRemovedFileSamples": sorted(phone_files)[:SAMPLE_LIMIT],
        "boilerplate": {
            name: {
                "fileCount": len(boilerplate_files[name]),
                "occurrences": boilerplate_occurrences[name],
                "samples": sorted(boilerplate_files[name])[:SAMPLE_LIMIT],
            }
            for name in sorted(BOILERPLATE_PATTERNS)
        },
        "emptyBodyFileCount": len(empty_body_files),
        "emptyBodyFileSamples": sorted(empty_body_files)[:SAMPLE_LIMIT],
        "shortBodyThresholdNonWhitespaceCharacters": SHORT_BODY_NON_WHITESPACE,
        "shortBodyFileCount": len(short_body_files),
        "shortBodyFileSamples": sorted(short_body_files)[:SAMPLE_LIMIT],
        "strongEncodingDamageFlags": {
            "replacementCharacterFileCount": len(replacement_character_files),
            "replacementCharacterFileSamples": sorted(replacement_character_files)[
                :SAMPLE_LIMIT
            ],
            "nulCharacterFileCount": len(nul_character_files),
            "nulCharacterFileSamples": sorted(nul_character_files)[:SAMPLE_LIMIT],
        },
        "files": records,
    }


def audit_metadata_sqlite(database_path: Path) -> dict[str, Any]:
    if not database_path.is_file():
        raise ValueError(f"SQLite metadata database does not exist: {database_path}")
    connection = sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "documents" not in tables:
            raise ValueError(f"SQLite database has no documents table: {database_path}")

        status_counts = {
            str(row["status"]): int(row["count"])
            for row in connection.execute(
                "SELECT status, COUNT(*) AS count FROM documents GROUP BY status ORDER BY status"
            ).fetchall()
        }
        environment_counts = {
            str(row["environmentId"]): int(row["count"])
            for row in connection.execute(
                "SELECT environmentId, COUNT(*) AS count FROM documents GROUP BY environmentId ORDER BY environmentId"
            ).fetchall()
        }
        tag_counts: Counter[str] = Counter()
        for row in connection.execute("SELECT tags FROM documents").fetchall():
            try:
                tags = json.loads(row["tags"] or "[]")
                if isinstance(tags, list):
                    tag_counts.update(str(tag) for tag in tags)
            except (TypeError, json.JSONDecodeError):
                tag_counts["[invalid JSON]"] += 1

        version_rows = connection.execute(
            """
            SELECT fileName, COUNT(DISTINCT docId) AS versions, SUM(chunkCount) AS chunks
            FROM documents
            GROUP BY fileName
            HAVING COUNT(DISTINCT docId) > 1
            ORDER BY versions DESC, fileName ASC
            """
        ).fetchall()
        return {
            "path": str(database_path.resolve()),
            "sha256": sha256_file(database_path),
            "documentCount": int(
                connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            ),
            "distinctDocumentIds": int(
                connection.execute("SELECT COUNT(DISTINCT docId) FROM documents").fetchone()[0]
            ),
            "distinctFileNames": int(
                connection.execute("SELECT COUNT(DISTINCT fileName) FROM documents").fetchone()[0]
            ),
            "filenamesWithMultipleDocumentIds": len(version_rows),
            "maximumDocumentIdsPerFilename": max(
                (int(row["versions"]) for row in version_rows), default=1
            ),
            "declaredChunkCount": int(
                connection.execute(
                    "SELECT COALESCE(SUM(chunkCount), 0) FROM documents"
                ).fetchone()[0]
            ),
            "statusCounts": status_counts,
            "environmentCounts": environment_counts,
            "tagCounts": dict(sorted(tag_counts.items())),
            "topMultiVersionFilenames": [
                {
                    "fileName": str(row["fileName"]),
                    "documentIds": int(row["versions"]),
                    "declaredChunks": int(row["chunks"] or 0),
                }
                for row in version_rows[:SAMPLE_LIMIT]
            ],
        }
    finally:
        connection.close()


def _validated_identifier(value: str, option: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid SQL identifier for {option}: {value!r}")
    return value


def audit_postgres_container(
    container: str,
    user: str,
    database: str,
    schema: str,
    table: str,
) -> dict[str, Any]:
    schema = _validated_identifier(schema, "--postgres-schema")
    table = _validated_identifier(table, "--postgres-table")
    qualified = f'"{schema}"."{table}"'
    sql = f"""
    WITH
    duplicate_text AS (
        SELECT text_content, COUNT(*) AS copies
        FROM {qualified}
        GROUP BY text_content
        HAVING COUNT(*) > 1
    ),
    filename_versions AS (
        SELECT file_name, COUNT(DISTINCT document_id) AS versions, COUNT(*) AS chunks
        FROM {qualified}
        GROUP BY file_name
        HAVING COUNT(DISTINCT document_id) > 1
    ),
    source_versions AS (
        SELECT source, COUNT(DISTINCT document_id) AS versions
        FROM {qualified}
        WHERE source IS NOT NULL AND source <> ''
        GROUP BY source
        HAVING COUNT(DISTINCT document_id) > 1
    )
    SELECT json_build_object(
        'chunkCount', (SELECT COUNT(*) FROM {qualified}),
        'distinctPointIds', (SELECT COUNT(DISTINCT point_id) FROM {qualified}),
        'distinctDocumentIds', (SELECT COUNT(DISTINCT document_id) FROM {qualified}),
        'distinctFileNames', (SELECT COUNT(DISTINCT file_name) FROM {qualified}),
        'distinctSources', (SELECT COUNT(DISTINCT source) FROM {qualified}),
        'filenamesWithMultipleDocumentIds', (SELECT COUNT(*) FROM filename_versions),
        'maximumDocumentIdsPerFilename', (SELECT COALESCE(MAX(versions), 1) FROM filename_versions),
        'sourcesWithMultipleDocumentIds', (SELECT COUNT(*) FROM source_versions),
        'exactDuplicateChunkGroups', (SELECT COUNT(*) FROM duplicate_text),
        'duplicateChunkRowsBeyondFirst', (SELECT COALESCE(SUM(copies - 1), 0) FROM duplicate_text),
        'maximumExactChunkCopies', (SELECT COALESCE(MAX(copies), 1) FROM duplicate_text),
        'chunksContainingPhoneRemoved', (SELECT COUNT(*) FROM {qualified} WHERE text_content ILIKE '%[phone removed]%'),
        'chunksContainingBackToTop', (SELECT COUNT(*) FROM {qualified} WHERE text_content ILIKE '%back to top%'),
        'chunksContainingLastModified', (SELECT COUNT(*) FROM {qualified} WHERE text_content ILIKE '%last modified%'),
        'distinctQueryParameterSources', (SELECT COUNT(DISTINCT source) FROM {qualified} WHERE source LIKE '%?%'),
        'topMultiVersionFilenames', (
            SELECT COALESCE(json_agg(row_to_json(item)), '[]'::json)
            FROM (
                SELECT file_name AS "fileName", versions AS "documentIds", chunks
                FROM filename_versions
                ORDER BY versions DESC, file_name ASC
                LIMIT {SAMPLE_LIMIT}
            ) item
        ),
        'tagDistributions', (
            SELECT COALESCE(json_agg(row_to_json(item)), '[]'::json)
            FROM (
                SELECT tags, COUNT(*) AS chunks
                FROM {qualified}
                GROUP BY tags
                ORDER BY chunks DESC, tags::text ASC
                LIMIT {SAMPLE_LIMIT}
            ) item
        )
    )::text;
    """
    command = [
        "docker",
        "exec",
        container,
        "psql",
        "-X",
        "-U",
        user,
        "-d",
        database,
        "-A",
        "-t",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = result.stdout.strip()
    if not payload:
        raise RuntimeError("PostgreSQL audit returned no data")
    parsed = json.loads(payload)
    return {
        "access": "docker-exec",
        "container": container,
        "database": database,
        "schema": schema,
        "table": table,
        **parsed,
    }


def audit_evaluation_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "systems": rows,
    }


def parse_metadata(values: Iterable[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for value in values:
        key, separator, raw = value.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"Metadata must use KEY=VALUE syntax: {value!r}")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        metadata[key.strip()] = parsed
    return dict(sorted(metadata.items()))


def _markdown_table(
    mapping: dict[str, Any], left: str = "Metric", right: str = "Value"
) -> list[str]:
    lines = [f"| {left} | {right} |", "|---|---:|"]
    for key, value in mapping.items():
        lines.append(f"| {key} | {value} |")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# NOTBot Phase 0 Baseline",
        "",
        f"Snapshot: `{report['snapshotLabel']}`  ",
        f"Application commit: `{report['applicationCommit']}`  ",
        f"Report schema: `{report['reportSchemaVersion']}`",
        "",
        "Generated by `scripts/corpus_audit.py`. The JSON report is the machine-readable source of truth.",
        "",
    ]
    runtime = report.get("runtimeMetadata", {})
    if runtime:
        lines.extend(["## Runtime identifiers", "", *_markdown_table(runtime), ""])

    source = report.get("sources")
    if source:
        lines.extend(
            [
                "## Processed source corpus",
                "",
                *_markdown_table(
                    {
                        "Files": source["fileCount"],
                        "Bytes": source["totalBytes"],
                        "Snapshot SHA-256": f"`{source['snapshotSha256']}`",
                        "Unique canonical source URLs": source[
                            "uniqueCanonicalSourceUrls"
                        ],
                        "Exact duplicate file groups": source["exactFileDuplicates"][
                            "groups"
                        ],
                        "Normalized-body duplicate groups": source[
                            "normalizedBodyDuplicates"
                        ]["groups"],
                        "Canonical URLs with multiple files": source[
                            "canonicalUrlsWithMultipleFiles"
                        ]["groups"],
                        "Query-parameter sources": source[
                            "queryParameterSourceCount"
                        ],
                        "Files containing `[phone removed]`": source[
                            "phoneRemovedFileCount"
                        ],
                        "`[phone removed]` occurrences": source[
                            "phoneRemovedOccurrences"
                        ],
                        "Files with `Back to top`": source["boilerplate"][
                            "backToTop"
                        ]["fileCount"],
                        "Files with `Last modified`": source["boilerplate"][
                            "lastModified"
                        ]["fileCount"],
                        "Empty bodies": source["emptyBodyFileCount"],
                        f"Bodies under {source['shortBodyThresholdNonWhitespaceCharacters']} non-whitespace characters": source[
                            "shortBodyFileCount"
                        ],
                    }
                ),
                "",
                "### Categories",
                "",
                *_markdown_table(source["categoryCounts"], "Category", "Files"),
                "",
                "### Instruments",
                "",
                *_markdown_table(source["instrumentCounts"], "Instrument", "Files"),
                "",
                "### Source types",
                "",
                *_markdown_table(source["sourceTypeCounts"], "Source type", "Files"),
                "",
            ]
        )

    sqlite = report.get("metadataDatabase")
    if sqlite:
        lines.extend(
            [
                "## SQLite document metadata",
                "",
                *_markdown_table(
                    {
                        "Documents": sqlite["documentCount"],
                        "Distinct document IDs": sqlite["distinctDocumentIds"],
                        "Distinct filenames": sqlite["distinctFileNames"],
                        "Filenames with multiple document IDs": sqlite[
                            "filenamesWithMultipleDocumentIds"
                        ],
                        "Maximum document IDs per filename": sqlite[
                            "maximumDocumentIdsPerFilename"
                        ],
                        "Declared chunks": sqlite["declaredChunkCount"],
                    }
                ),
                "",
                "### Document statuses",
                "",
                *_markdown_table(sqlite["statusCounts"], "Status", "Documents"),
                "",
            ]
        )

    postgres = report.get("vectorDatabase")
    if postgres:
        lines.extend(
            [
                "## PostgreSQL vector index",
                "",
                *_markdown_table(
                    {
                        "Chunks": postgres["chunkCount"],
                        "Distinct point IDs": postgres["distinctPointIds"],
                        "Distinct document IDs": postgres["distinctDocumentIds"],
                        "Distinct filenames": postgres["distinctFileNames"],
                        "Filenames with multiple document IDs": postgres[
                            "filenamesWithMultipleDocumentIds"
                        ],
                        "Maximum document IDs per filename": postgres[
                            "maximumDocumentIdsPerFilename"
                        ],
                        "Exact duplicate chunk groups": postgres[
                            "exactDuplicateChunkGroups"
                        ],
                        "Duplicate chunk rows beyond first": postgres[
                            "duplicateChunkRowsBeyondFirst"
                        ],
                        "Maximum exact chunk copies": postgres[
                            "maximumExactChunkCopies"
                        ],
                        "Chunks containing `[phone removed]`": postgres[
                            "chunksContainingPhoneRemoved"
                        ],
                        "Chunks containing `Back to top`": postgres[
                            "chunksContainingBackToTop"
                        ],
                        "Chunks containing `Last modified`": postgres[
                            "chunksContainingLastModified"
                        ],
                    }
                ),
                "",
            ]
        )

    evaluation = report.get("evaluationSummary")
    if evaluation:
        lines.extend(["## Evaluation summary", ""])
        for system in evaluation["systems"]:
            lines.append(f"### `{system.get('system_version', '[unknown]')}`")
            lines.append("")
            metric_values = {
                key: value
                for key, value in system.items()
                if key.endswith("_mean") or key.endswith("_count")
            }
            lines.extend([*_markdown_table(metric_values), ""])

    lines.extend(
        [
            "## Reproduction",
            "",
            "See `reports/phase0/README.md` for exact snapshot, audit, and evaluation commands.",
            "",
        ]
    )
    return "\n".join(lines)


def current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--metadata-sqlite", type=Path)
    parser.add_argument("--postgres-container")
    parser.add_argument("--postgres-user", default="postgres")
    parser.add_argument("--postgres-db", default="rag")
    parser.add_argument("--postgres-schema", default="public")
    parser.add_argument("--postgres-table", default="rag_documents")
    parser.add_argument("--evaluation-summary", type=Path)
    parser.add_argument("--snapshot-label", required=True)
    parser.add_argument("--application-commit", default="")
    parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Non-secret runtime identifier; JSON scalar values are accepted.",
    )
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report: dict[str, Any] = {
        "reportSchemaVersion": 1,
        "snapshotLabel": args.snapshot_label,
        "applicationCommit": args.application_commit or current_commit(),
        "runtimeMetadata": parse_metadata(args.metadata),
        "sources": audit_sources(args.source_dir),
    }
    if args.metadata_sqlite:
        report["metadataDatabase"] = audit_metadata_sqlite(args.metadata_sqlite)
    if args.postgres_container:
        report["vectorDatabase"] = audit_postgres_container(
            args.postgres_container,
            args.postgres_user,
            args.postgres_db,
            args.postgres_schema,
            args.postgres_table,
        )
    if args.evaluation_summary:
        report["evaluationSummary"] = audit_evaluation_summary(
            args.evaluation_summary
        )

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.markdown_out.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {args.json_out}")
    print(f"Wrote {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
