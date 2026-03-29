"""
Vor sentence_transformers/torch: Fortschrittsbalken (tqdm) und Hub-Spinner unterdruecken.

Ohne das erscheint oft pro Mini-Batch eine Zeile 'Batches: 100%|...' — wirkt wie Haenger.
"""

from __future__ import annotations

import os

_applied = False


def apply_quiet_ml_env() -> None:
    global _applied
    if _applied:
        return
    _applied = True

    # Kein Ersetzen von tqdm.tqdm durch eine Funktion: huggingface_hub baut
    # `class tqdm(old_tqdm)` und braucht eine echte tqdm-Klasse (sonst TypeError).
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("TQDM_DISABLE", "1")
