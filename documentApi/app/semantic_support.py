"""Optional, pinned, local-only entailment verification (not an answer model).

No chat or document content leaves this process. We never download weights in a
request: provision them explicitly with scripts/provision_semantic_checker.py.
Numerical, identifier, quotation and source-policy checks remain independent.
"""
from functools import lru_cache
import logging
import os
import re
import threading
from .config import get_base_directory

MODEL = "cross-encoder/nli-deberta-v3-base"
REVISION = "6c749ce3425cd33b46d187e45b92bbf96ee12ec7"
_lock = threading.Lock()
_logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _model():
    if os.environ.get("NOTBOT_SEMANTIC_CHECK", "1") == "0":
        return None
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(MODEL, revision=REVISION, device="cpu", max_length=512,
                            cache_dir=str(get_base_directory() / "model_cache"),
                            local_files_only=True, trust_remote_code=False,
                            automodel_args={"use_safetensors": True})
    except Exception as exc:
        _logger.warning("Local semantic checker unavailable (%s); using deterministic fallback", type(exc).__name__)
        return None


def available() -> bool:
    return _model() is not None


def _prose(text: str) -> str:
    # Only equivalent notation, never value conversion or invented facts.
    text=text.replace('−','-')
    text=re.sub(r'(?<=\d)\s*◦\s*([CF])\b',r'°\1',text)
    text = re.sub(r'(\d(?:[.,]\d+)?)\s*["″]', r'\1 arcseconds', text)
    text = re.sub(r"(\d(?:[.,]\d+)?)\s*['′]", r'\1 arcminutes', text)
    text = re.sub(r"\b(?:fibre|fibres)\b", lambda m: "fibers" if m.group().endswith("s") else "fiber", text, flags=re.I)
    return " ".join(text.split())


def entails(statement: str, quotes: list[str], items: list[dict], language: str) -> bool | None:
    if language != "en":
        return None  # This model's training/evaluation is English, not German.
    model = _model()
    if model is None:
        return None
    scope = "; ".join(dict.fromkeys(
        value for item in items for value in (item.get("title", ""), item.get("instrument", ""), item.get("section", "")) if value))
    # Check bounded windows of the actual evidence rather than letting a long
    # copied item overflow/truncate the proof. Windows never mix source items;
    # each retains its title/section scope. A single overlong sentence is not
    # accepted. This helps miscopied quotes without trusting model quotations.
    premises=[]
    for quote in quotes:
        parts=re.split(r'\n\s*\n|(?<=[.!?])\s+(?=[A-Z])',quote)
        window=[]
        for part in parts:
            candidate=_prose(scope+'. '+' '.join([*window,part]))
            if len(model.tokenizer.encode(candidate,statement))>512:
                if window:
                    premises.append(_prose(scope+'. '+' '.join(window)))
                window=[]
                if len(model.tokenizer.encode(_prose(scope+'. '+part),statement))>512:
                    continue
            window.append(part)
        if window:
            premises.append(_prose(scope+'. '+' '.join(window)))
    if not premises:
        return False
    try:
        import torch
        with _lock:
            scores = model.predict([(premise, _prose(statement)) for premise in premises], show_progress_bar=False,
                                   activation_fct=torch.nn.Softmax(dim=1))
        # Label order is pinned in the official model card/config.
        return any(float(score[1]) >= .80 and float(score[0]) < .10 for score in scores)
    except Exception:
        _logger.exception("Local semantic support check failed")
        return False
