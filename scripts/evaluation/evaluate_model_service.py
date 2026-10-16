#!/usr/bin/env python3
"""Exercise final ChatService routing and candidate-own history, read-only.

This is an isolated in-process service test, not HTTP/PHP deployment certification.
The only transport adapter disables SDK retries and requests no thinking uniformly.
No production code, settings, model store or audit history is changed.
"""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from types import SimpleNamespace

from compare_models import MODELS, api, application_identity, atomic_json, private_dir, sha
from evaluate_operational import assess


async def run(args):
    work = private_dir(args.private)
    from app import chat_service
    from app.config import load_settings, get_app_paths
    from app.crypto_service import CryptoService
    from app.models import ChatRequest
    from app.vector_store.factory import create_vector_store
    from app.semantic_support import available
    if not available():
        raise ValueError("Pinned semantic checker unavailable")
    if "notbot-model-eval-20261001" not in args.engine:
        raise ValueError("Only the named isolated engine is allowed")
    pins = json.loads(args.pins.read_text())["models"]
    base = MODELS[args.model]
    expected = next(m["digest"] for m in pins if m["name"] == base)
    actual = next(m["digest"] for m in api(args.engine, "/api/tags")["models"] if m["name"] == base)
    if actual != expected:
        raise ValueError("Model pin differs")
    profile = f"notbot-eval-{args.model}:english-v2-ctx32k"
    api(args.engine, "/api/create", {"model": profile, "from": base, "parameters":
        {"num_ctx": 32768, "num_predict": 2048, "temperature": 0.3}, "stream": False})
    corpus = json.loads((work / "frozen.json").read_text())
    if application_identity() != corpus["appPythonSha256"]:
        raise ValueError("Application differs from capture")
    settings = load_settings()
    env = settings.get_active_postgres()
    store = create_vector_store(env, get_app_paths()["base"])
    original_conn = store._get_conn
    def readonly():
        conn = original_conn()
        conn.rollback()
        conn.set_session(readonly=True)
        return conn
    store._get_conn = readonly
    with readonly() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*), count(DISTINCT source_id), array_agg(DISTINCT corpus_version) FROM {store._qualified_table(env.db_table_name)} WHERE is_active")
            count, sources, versions = cur.fetchone()
    store._put_conn(conn)
    if (count, sources, versions) != (5479, 483, ["phase6-2026-10-01-v10"]):
        raise ValueError("Corpus identity changed")
    original_client = chat_service.OpenAI
    observations = []
    class Client:
        def __init__(self, **kwargs):
            self.client = original_client(**kwargs, max_retries=0, timeout=180)
            self.chat = SimpleNamespace(completions=self)
        def create(self, **kwargs):
            kwargs["reasoning_effort"] = "none"
            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            reason = getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None) or ""
            observations.append({"finishReason": response.choices[0].finish_reason, "reasoningChars": len(reason)})
            return response
    chat_service.OpenAI = Client
    service = chat_service.ChatService(store, CryptoService(), audit=None)
    service.update_settings(settings)
    service._chat_settings = service.get_chat_settings().model_copy(update={
        "llm_base_url": args.engine.rstrip("/") + "/v1", "llm_api_key": "ollama",
        "llm_model": profile, "temperature": 0.3, "max_tokens": 2048})
    service._record = lambda *a, **kw: None
    raw_cases = args.cases.read_bytes()
    cases = [c for c in json.loads(raw_cases) if c.get("language", "en") == "en"]
    rows, history_by_id = [], {}
    if args.output.exists():
        raise ValueError("Use a new receipt; service history must not silently resume")
    for case in cases:
        history = deepcopy(case.get("history", []))
        if case.get("after"):
            prior = history_by_id[case["after"]]
            history = prior["history"] + [{"role": "user", "content": prior["question"]},
                                          {"role": "assistant", "content": prior["answer"]}]
        observations.clear()
        started = time.monotonic()
        result = await service.chat(ChatRequest(message=case["question"], history=history, language="en"))
        result = result.model_dump(by_alias=True)
        elapsed = round((time.monotonic() - started) * 1000)
        errors = assess(case, result)
        if any(o["reasoningChars"] for o in observations):
            errors.append("reasoning observed despite disabled request")
        if any(o["finishReason"] == "length" for o in observations):
            errors.append("output cap reached")
        trace = result.get("trace", {})
        row = {"id": case["id"], "passed": not errors, "errors": errors, "elapsedMs": elapsed,
            "abstained": result.get("metrics", {}).get("abstained"), "answerSha256": sha(result.get("answer", "").encode()),
            "trace": {k: trace.get(k) for k in ("answerMethod", "generationAttempts", "generationMs", "validationMs",
                "contextResolution", "acceptedClaims", "rejectedClaims", "rejectionReasons", "abstentionReason",
                "corpusVersion", "indexId", "model")}, "transportObservations": deepcopy(observations)}
        rows.append(row)
        history_by_id[case["id"]] = {"question": case["question"], "answer": result.get("answer", ""), "history": history}
        atomic_json(work / "service-outputs" / args.model / (case["id"] + ".json"), result, private=True)
        atomic_json(args.output, {"recordedAt": datetime.now(timezone.utc).isoformat(), "model": args.model,
            "baseModel": base, "baseManifestDigest": expected, "appPythonSha256": corpus["appPythonSha256"],
            "casesSha256": sha(raw_cases), "englishCases": len(cases), "complete": len(rows) == len(cases),
            "passed": sum(r["passed"] for r in rows), "results": rows, "driverSha256": sha(Path(__file__).read_bytes()),
            "scope": "In-process final ChatService, CPU embeddings, read-only PostgreSQL, dynamic actual validated history; NOT HTTP/PHP",
            "transportAdapter": "Uniform explicit reasoning_effort none; SDK retries disabled; timeout180",
            "liveSettingsModified": False, "historicalAuditsRead": False, "automaticPromotion": False})
        print(json.dumps({k: row[k] for k in ("id", "passed", "errors", "elapsedMs")}), flush=True)
        if trace.get("abstentionReason") == "model_unavailable":
            raise RuntimeError("Stop after failed model transport; cancel only test engine")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("operational_cases.json"))
    parser.add_argument("--pins", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", default="http://notbot-model-eval-20261001:11434")
    args = parser.parse_args()
    from app.services.thread_pool import init_thread_pool, shutdown_thread_pool
    init_thread_pool(max_workers=2)
    try:
        asyncio.run(run(args))
    finally:
        shutdown_thread_pool(wait=True)


if __name__ == "__main__":
    main()
