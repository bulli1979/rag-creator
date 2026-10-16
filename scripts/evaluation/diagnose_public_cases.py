#!/usr/bin/env python3
"""Inspect newly generated claims for explicit public regression questions.

Never reads chat audits or historic conversations. Uses a fresh, unaudited
service and a new ephemeral encryption key; no credentials are printed.
Run inside the API container with an explicit public question as argv[1].
"""
import asyncio
import json
import sys
sys.path.insert(0, '/app')
from app import chat_service
from app.config import load_settings, get_app_paths
from app.crypto_service import CryptoService
from app.models import ChatRequest
from app.services.thread_pool import init_thread_pool, shutdown_thread_pool
from app.vector_store.factory import create_vector_store


async def main():
    settings = load_settings()
    store = create_vector_store(settings.get_active_postgres(), get_app_paths()['base'])
    original = chat_service.validate_and_render
    def inspect(raw, evidence, *args, **kwargs):
        result = original(raw, evidence, *args, **kwargs)
        print(json.dumps({'newPublicClaims': raw, 'reasons': result.rejection_reasons}), flush=True)
        return result
    chat_service.validate_and_render = inspect
    service = chat_service.ChatService(store, CryptoService(), audit=None)
    service.update_settings(settings)
    response = await service.chat(ChatRequest(message=sys.argv[1], history=[], language='en'))
    print(json.dumps({'answer': response.answer, 'trace': response.trace}), flush=True)


if __name__ == '__main__':
    init_thread_pool(max_workers=4)
    try:
        asyncio.run(main())
    finally:
        shutdown_thread_pool(wait=True)
