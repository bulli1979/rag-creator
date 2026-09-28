from __future__ import annotations


def ollama_origin_from_openai_base_url(openai_base: str) -> str:
    """
    OpenAI-kompatible Chat-Basis (z. B. http://localhost:11434/v1) auf die Ollama-Origin
    (http://localhost:11434) abbilden. Ollamas native API liegt unter /api/tags ohne /v1.
    """
    raw = (openai_base or "").strip()
    if not raw:
        raise ValueError("llmBaseUrl ist leer")
    base = raw.rstrip("/")
    if base.lower().endswith("/v1"):
        base = base[:-3].rstrip("/")
    if "://" not in base:
        base = f"http://{base}"
    return base
