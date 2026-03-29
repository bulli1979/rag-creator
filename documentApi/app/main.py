from __future__ import annotations

from .services.quiet_ml_env import apply_quiet_ml_env

apply_quiet_ml_env()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .chat_service import ChatService
from .config import ensure_directories, get_app_paths, load_settings
from .crypto_service import CryptoService
from .database import IndexDatabase
from .dependencies import set_chat_service, set_ingest_service
from .file_store import FileStore
from .ingest_service import IngestService
from .routers import chat, corpus, documents, health, jobs, settings
from .services.thread_pool import init_thread_pool, shutdown_thread_pool
from .vector_service import PostgresVectorService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_thread_pool(max_workers=4)
    try:
        ensure_directories()
        paths = get_app_paths()
        app_settings = load_settings()
        active_pg = app_settings.get_active_postgres()

        db = IndexDatabase(paths["database"])
        fs = FileStore(paths["files"], paths["corpus"])
        vs = PostgresVectorService(
            host=active_pg.db_host,
            port=active_pg.db_port,
            database=active_pg.db_name,
            user=active_pg.db_user,
            password=active_pg.db_password,
            schema=active_pg.db_schema,
        )

        svc = IngestService(db, fs, vs)
        await svc.initialize()
        set_ingest_service(svc)

        crypto = CryptoService()
        chat_svc = ChatService(vs, crypto)
        chat_svc.update_settings(app_settings)
        set_chat_service(chat_svc)

        yield
    finally:
        shutdown_thread_pool(wait=False, cancel_futures=True)


app = FastAPI(
    title="RAG Ingest API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(corpus.router)
app.include_router(settings.router)
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {"name": "RAG Ingest API", "version": "1.0.0"}
