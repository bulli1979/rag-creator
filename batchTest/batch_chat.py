"""
Batch-Aufrufe der documentApi Chat-Route (/api/chat) mit Konfiguration aus JSON.
Schreibt eine Excel-Datei mit Fragen, Antworten, Metriken und Kontext-Chunks.

Abhängigkeiten: pip install -r requirements.txt
Aufruf: python batch_chat.py --config batch_config.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

DEFAULT_CONFIG = "batch_config.json"
EXCEL_MAX_CELL = 32000


def _truncate(s: str, max_len: int = EXCEL_MAX_CELL) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 40] + "\n… [gekürzt wegen Excel-Zellenlimit]"


def load_questions_from_file(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def format_chunks_for_row(chunks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for i, ch in enumerate(chunks, start=1):
        fn = ch.get("fileName") or ch.get("file_name") or ""
        idx = ch.get("chunkIndex", ch.get("chunk_index", ""))
        doc_id = ch.get("documentId", ch.get("document_id", ""))
        sim = ch.get("similarity", "")
        src = ch.get("source", ch.get("sourcePath", ""))
        text = str(ch.get("text", "")).strip().replace("\r\n", "\n")
        if len(text) > 2000:
            text = text[:1997] + "..."
        parts.append(
            f"--- Chunk {i} ---\n"
            f"Datei: {fn}\n"
            f"chunkIndex: {idx}\n"
            f"documentId: {doc_id}\n"
            f"Ähnlichkeit: {sim}\n"
            f"Quelle: {src}\n"
            f"Text:\n{text}"
        )
    return "\n\n".join(parts) if parts else ""


def format_chunks_one_line(chunks: list[dict[str, Any]]) -> str:
    bits: list[str] = []
    for ch in chunks:
        fn = ch.get("fileName") or ch.get("file_name") or "?"
        idx = ch.get("chunkIndex", ch.get("chunk_index", "?"))
        sim = ch.get("similarity", "")
        bits.append(f"{fn}#{idx}(sim={sim})")
    return "; ".join(bits)


def merge_chat_settings(server: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(server)
    for k, v in overlay.items():
        if v is not None:
            out[k] = v
    return out


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Konfiguration muss ein JSON-Objekt sein.")
    return data


def resolve_output_path(cfg: dict[str, Any]) -> Path:
    raw = cfg.get("outputExcel") or "batch_results.xlsx"
    p = Path(str(raw))
    if not p.is_absolute():
        p = Path.cwd() / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-Chat gegen documentApi, Export nach Excel.")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Pfad zur JSON-Konfiguration (Standard: {DEFAULT_CONFIG})",
    )
    args = parser.parse_args()
    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"Konfigurationsdatei fehlt: {config_path}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config(config_path)
    base = str(cfg.get("apiBaseUrl") or "http://localhost:8000").rstrip("/")
    timeout = float(cfg.get("requestTimeoutSeconds") or 300)

    questions: list[str] = list(cfg.get("questions") or [])
    qfile = cfg.get("questionsFile")
    if qfile:
        qp = Path(str(qfile))
        if not qp.is_file():
            print(f"questionsFile nicht gefunden: {qp}", file=sys.stderr)
            sys.exit(1)
        questions.extend(load_questions_from_file(qp))

    questions = [q.strip() for q in questions if str(q).strip()]
    if not questions:
        print("Keine Fragen: 'questions' und/oder 'questionsFile' angeben.", file=sys.stderr)
        sys.exit(1)

    history = cfg.get("history") or []
    language = cfg.get("language")

    apply_settings = bool(cfg.get("applyChatSettings", False))
    restore_after = bool(cfg.get("restoreChatSettingsAfterRun", False))
    chat_overlay = cfg.get("chatSettings") if isinstance(cfg.get("chatSettings"), dict) else {}

    result_headers = [
        "Nr",
        "Frage",
        "Antwort",
        "Fehler_HTTP",
        "Antwortzeit_ms",
        "Prompt_Tokens",
        "Completion_Tokens",
        "Total_Tokens",
        "Tokens_pro_Sekunde",
        "Anzahl_Chunks",
        "Chunks_Kurzliste",
        "Chunks_Detail",
    ]

    rows: list[list[Any]] = []
    chunk_rows: list[list[Any]] = []
    chunk_headers = [
        "Frage_Nr",
        "Chunk_Pos",
        "Dateiname",
        "chunkIndex",
        "documentId",
        "Ähnlichkeit",
        "Quelle",
        "Text_Auszug",
    ]
    snapshot_before: dict[str, Any] | None = None

    with httpx.Client(base_url=base, timeout=timeout) as client:
        if apply_settings and chat_overlay:
            r0 = client.get("/api/chat/settings")
            if r0.status_code != 200:
                print(f"GET /api/chat/settings fehlgeschlagen: {r0.status_code} {r0.text}", file=sys.stderr)
                sys.exit(1)
            snapshot_before = r0.json()
            merged = merge_chat_settings(snapshot_before, chat_overlay)
            r_put = client.put("/api/chat/settings", json=merged)
            if r_put.status_code != 200:
                print(f"PUT /api/chat/settings fehlgeschlagen: {r_put.status_code} {r_put.text}", file=sys.stderr)
                sys.exit(1)

        for i, message in enumerate(questions, start=1):
            body: dict[str, Any] = {"message": message, "history": history}
            if language in ("de", "en"):
                body["language"] = language

            err_http = ""
            answer = ""
            metrics: dict[str, Any] = {}
            chunks: list[dict[str, Any]] = []

            try:
                resp = client.post("/api/chat", json=body)
                if resp.status_code != 200:
                    err_http = f"{resp.status_code}: {resp.text[:2000]}"
                else:
                    payload = resp.json()
                    answer = str(payload.get("answer", ""))
                    metrics = payload.get("metrics") or {}
                    raw_chunks = payload.get("contextChunks") or payload.get("context_chunks") or []
                    chunks = [c for c in raw_chunks if isinstance(c, dict)]
            except httpx.RequestError as exc:
                err_http = str(exc)

            rows.append(
                [
                    i,
                    message,
                    _truncate(answer),
                    err_http,
                    metrics.get("elapsedMs", ""),
                    metrics.get("promptTokens", ""),
                    metrics.get("completionTokens", ""),
                    metrics.get("totalTokens", ""),
                    metrics.get("tokensPerSecond", ""),
                    len(chunks),
                    _truncate(format_chunks_one_line(chunks), 8000),
                    _truncate(format_chunks_for_row(chunks)),
                ]
            )
            for pos, ch in enumerate(chunks, start=1):
                fn = ch.get("fileName") or ch.get("file_name") or ""
                idx = ch.get("chunkIndex", ch.get("chunk_index", ""))
                doc_id = ch.get("documentId", ch.get("document_id", ""))
                sim = ch.get("similarity", "")
                src = str(ch.get("source", ch.get("sourcePath", "")))
                preview = _truncate(str(ch.get("text", "")).strip().replace("\r\n", "\n"), 12000)
                chunk_rows.append([i, pos, fn, idx, doc_id, sim, src, preview])

        if restore_after and snapshot_before is not None:
            r_rest = client.put("/api/chat/settings", json=snapshot_before)
            if r_rest.status_code != 200:
                print(
                    f"Warnung: Chat-Einstellungen konnten nicht wiederhergestellt werden: "
                    f"{r_rest.status_code} {r_rest.text}",
                    file=sys.stderr,
                )

    out_path = resolve_output_path(cfg)
    wb = Workbook()
    ws = wb.active
    ws.title = "Ergebnisse"

    meta = wb.create_sheet("Meta", 0)
    meta["A1"] = "Erstellt (UTC)"
    meta["B1"] = datetime.now(timezone.utc).isoformat()
    meta["A2"] = "API"
    meta["B2"] = base
    meta["A3"] = "Konfiguration"
    meta["B3"] = str(config_path.resolve())
    meta["A4"] = "Fragen (Anzahl)"
    meta["B4"] = len(questions)
    if apply_settings and chat_overlay:
        meta["A5"] = "Chat-Einstellungen"
        meta["B5"] = json.dumps(chat_overlay, ensure_ascii=False, indent=2)
        meta["B5"].alignment = Alignment(wrap_text=True, vertical="top")
    for col in range(1, 3):
        meta.column_dimensions[get_column_letter(col)].width = 22 if col == 1 else 80

    ws.append(result_headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for row in rows:
        ws.append(row)

    ws_chunks = wb.create_sheet("Chunks")
    ws_chunks.append(chunk_headers)
    for cell in ws_chunks[1]:
        cell.font = Font(bold=True)
    for crow in chunk_rows:
        ws_chunks.append(crow)

    for col_idx in range(1, len(result_headers) + 1):
        letter = get_column_letter(col_idx)
        if col_idx in (2, 3, 12, 13):
            ws.column_dimensions[letter].width = 48 if col_idx == 2 else 60
            for r in range(2, ws.max_row + 1):
                c = ws.cell(row=r, column=col_idx)
                c.alignment = Alignment(wrap_text=True, vertical="top")
        else:
            ws.column_dimensions[letter].width = 14

    for col_idx in range(1, len(chunk_headers) + 1):
        letter = get_column_letter(col_idx)
        w = 12
        if col_idx in (3, 7, 8):
            w = 36 if col_idx == 3 else (28 if col_idx == 7 else 70)
        ws_chunks.column_dimensions[letter].width = w
        if col_idx == 8:
            for r in range(2, ws_chunks.max_row + 1):
                ws_chunks.cell(row=r, column=col_idx).alignment = Alignment(
                    wrap_text=True, vertical="top"
                )

    wb.save(out_path)
    print(f"Excel geschrieben: {out_path}")


if __name__ == "__main__":
    main()
