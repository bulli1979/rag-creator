from __future__ import annotations


def create_vector_store(*args, **kwargs):
    from .factory import create_vector_store as implementation

    return implementation(*args, **kwargs)


def resolve_sqlite_path(*args, **kwargs):
    from .factory import resolve_sqlite_path as implementation

    return implementation(*args, **kwargs)


def resolve_qdrant_path(*args, **kwargs):
    from .factory import resolve_qdrant_path as implementation

    return implementation(*args, **kwargs)


__all__ = ["create_vector_store", "resolve_sqlite_path", "resolve_qdrant_path"]
