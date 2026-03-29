"""
Eigener ThreadPool statt Default-Executor von asyncio:
verhindert beim Reload/Shutdown haengende Joins (RuntimeWarning 300s) und
begrenzt parallele CPU/IO-Last (Embeddings, Parsing).
"""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

_logger = logging.getLogger(__name__)

T = TypeVar("T")

_executor: ThreadPoolExecutor | None = None


def init_thread_pool(*, max_workers: int = 4) -> ThreadPoolExecutor:
    global _executor
    if _executor is not None:
        return _executor
    _executor = ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="rag-ingest",
    )
    _logger.info("thread pool started (max_workers=%s)", max_workers)
    return _executor


def get_thread_pool() -> ThreadPoolExecutor:
    if _executor is None:
        return init_thread_pool()
    return _executor


async def run_in_worker_pool(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """CPU-/Blockierarbeit ausfuehren ohne den Default-asyncio-Executor zu fuellen."""
    loop = asyncio.get_running_loop()
    executor = get_thread_pool()
    if kwargs:
        call = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, call)
    return await loop.run_in_executor(executor, func, *args)


def shutdown_thread_pool(*, wait: bool = False, cancel_futures: bool = True) -> None:
    global _executor
    if _executor is None:
        return
    try:
        _executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        _logger.info("thread pool shutdown (wait=%s cancel_futures=%s)", wait, cancel_futures)
    except Exception as exc:
        _logger.warning("thread pool shutdown: %s", exc)
    finally:
        _executor = None
