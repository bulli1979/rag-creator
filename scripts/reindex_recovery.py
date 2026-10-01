#!/usr/bin/env python3
"""Upload a versioned recovery shadow, then verify every queued indexing job.

Back up both catalogue and vector database before running. This script never
deletes old source versions or prints settings/credentials.
"""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--folder", required=True, help="Path visible inside the API container")
    parser.add_argument("--version", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--llm-profile", help="Restore a known local profile; do not change model weights")
    parser.add_argument("--embedding-model",help="Use only with a new isolated environment/table")
    parser.add_argument("--new-environment",help="Unique catalogue environment ID for an isolated index")
    parser.add_argument("--new-table",help="Unique PostgreSQL table for an isolated index")
    args = parser.parse_args()
    def call(path, payload=None, method=None):
        req = Request(args.api + path, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type":"application/json"}, method=method)
        with urlopen(req, timeout=240) as response:
            return json.load(response)
    if args.embedding_model:
        if not args.new_environment or not args.new_table:
            raise ValueError("Changing embedding dimensions requires an isolated environment and table")
        app = call("/api/settings")
        if any(e["id"] == args.new_environment for e in app["postgresEnvironments"]):
            raise ValueError("Environment already exists; no existing index will be overwritten")
        if any(e['dbTableName']==args.new_table for e in app['postgresEnvironments']):
            raise ValueError('Table is already configured; choose a new isolated table')
        current = next(e for e in app["postgresEnvironments"] if e["id"] == app["activePostgresEnvironmentId"])
        if current["vectorBackend"] != "postgres":
            raise ValueError("Isolated recovery switch currently supports PostgreSQL only")
        new = {**current,"id":args.new_environment,"name":"NOTBot verified recovery", "dbTableName":args.new_table}
        app["postgresEnvironments"].append(new)
        app.update(activePostgresEnvironmentId=args.new_environment,embeddingModel=args.embedding_model)
        call("/api/settings", app, "PUT")
    connection = call("/api/database/test-connection", {}, "POST")
    if connection.get("status") != "ok":
        raise RuntimeError("Database connection did not validate")
    settings = call("/api/chat/settings")
    settings.update(topK=8, maxChunksPerSource=2, minEvidenceSimilarity=.30)
    if args.llm_profile:
        settings["llmModel"] = args.llm_profile
    call("/api/chat/settings", settings, "PUT")
    offset = 0
    ids = []
    while True:
        result = call("/api/documents/upload-folder-path", {
            "folderPath":args.folder, "offset":offset, "batchSize":100,
            "corpusVersion":args.version, "source":"NOT official approved recovery corpus"})
        ids += result["queuedDocIds"] + result.get("skippedDocIds", [])
        print(json.dumps({"uploadedOrExisting":len(ids), "total":result["fileCount"]}), flush=True)
        if result["done"]:
            break
        offset = result["nextOffset"]
    wanted = set(ids)
    deadline = time.monotonic() + 3600
    while True:
        docs = [d for d in call("/api/documents") if d["docId"] in wanted]
        pending = [d for d in docs if d["status"] not in ("done","error")]
        failed = [{"id":d["docId"],"file":d["fileName"],"error":d.get("errorMessage")} for d in docs if d["status"] == "error"]
        report = {"corpusVersion":args.version,"documentsRequested":len(wanted),"documentsFound":len(docs),
                  "done":sum(d["status"]=="done" for d in docs),"pending":len(pending),"failed":failed,
                  "chunks":sum(d["chunkCount"] for d in docs if d["status"]=="done")}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+"\n")
        print(json.dumps(report), flush=True)
        if failed or len(docs) != len(wanted):
            raise RuntimeError("Recovery indexing incomplete; inspect report and restore if needed")
        if not pending:
            return 0
        if time.monotonic() > deadline:
            raise TimeoutError("Indexing did not finish within one hour")
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
