"""Checked unit conversion and interval comparison, not model-generated facts.

Only unambiguous instrument-wide wavelength ranges in current reviewed evidence
are eligible. In-range does not imply that every filter or mode supports a value.
"""

from dataclasses import dataclass
from decimal import Decimal
import re

from .evidence_selection import classify_query
from .grounding import ValidationResult


_UNIT = r"(?:[µμu]m|nm|(?:micro|nano)met(?:er|re)s?)"
_VALUE = r"\d+(?:[.,]\d+)?"
_QUANTITY = re.compile(rf"(?<![\w.+-])({_VALUE})\s*({_UNIT})(?!\w)", re.I)
_RANGE = re.compile(rf"(?<![\w.+-])({_VALUE})\s*({_UNIT})?\s*(?:[-–—]|to|bis)\s*({_VALUE})\s*({_UNIT})(?!\w)", re.I)
_QUESTION = re.compile(r"\b(?:can|could|possible|kann|könnte)\b", re.I)
_OBSERVE = re.compile(r"\b(?:observ\w*|detect\w*|used|wavelength\w*|wellenlänge\w*)\b", re.I)


def _micrometres(value: str, unit: str) -> Decimal:
    number = Decimal(value.replace(",", "."))
    return number / 1000 if unit.lower().startswith(("nm", "nano")) else number


def _display(value: Decimal) -> str:
    return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else format(value, "f")


@dataclass(frozen=True)
class WavelengthAnswer:
    validation: ValidationResult
    derivation: dict


def compare_wavelength(query: str, evidence: list[dict], language: str = "en") -> WavelengthAnswer | None:
    intent = classify_query(query)
    named = intent.instruments
    if intent.historical or len(named) != 1:
        return None
    instrument = next(iter(named))
    name = re.escape(instrument)
    range_question = any(re.fullmatch(pattern, query.strip(), re.I) for pattern in (
        rf"(?:what|which) wavelengths?(?: range)? does (?:the )?{name} (?:cover|observe|detect)[?.!]*",
        rf"(?:what|which) is (?:the )?(?:wavelength|spectral) range (?:of|for) (?:the )?{name}[?.!]*",
        rf"what is (?:the )?{name}(?:'s)? (?:wavelength|spectral) range[?.!]*",
    ))
    quantities = list(_QUANTITY.finditer(query))
    if not range_question and (len(quantities) != 1 or not _QUESTION.search(query) or not _OBSERVE.search(query)):
        return None
    # Comparisons with mode/filter/safety qualifiers need more than a whole-
    # instrument interval. Leave those questions to ordinary grounded generation.
    if re.search(r"\b(?:filter\w*|mode\w*|spectro\w*|resolution|safe\w*|calibrat\w*|only|not|without|except)\b", query, re.I):
        return None
    quantity = None if range_question else quantities[0]
    requested = None
    if quantity:
        # A second bare number or a negative/scientific quantity is not a single
        # wavelength request. Avoid silently ignoring unsupported numerical syntax.
        remainder = query[:quantity.start()] + query[quantity.end():]
        if re.search(r"\d", remainder):
            return None
        requested = _micrometres(*quantity.groups())
        if requested <= 0:
            return None
    ranges = []
    for item in evidence:
        if (str(item.get("instrument", "")).upper() != instrument
                or item.get("status", "").lower() not in ("active", "current")
                or not item.get("authority", "").startswith(("tier_1", "tier_2"))):
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n", item.get("content", "")):
            if classify_query(sentence).instruments != named:
                continue
            if not re.search(r"\b(?:wavelength\w*|infrared|spectral|cover\w*|wellenlänge\w*)\b", sentence, re.I):
                continue
            if re.search(r"\b(?:filter\w*|spectro\w*|mode\s+only|pixel\w*|calibrat\w*|formerly|previously|not|except|without|design|planned|proposed)\b", sentence, re.I):
                continue
            matches = list(_RANGE.finditer(sentence))
            if len(matches) != 1:
                continue
            match = matches[0]
            lower, lower_unit, upper, upper_unit = match.groups()
            lo = _micrometres(lower, lower_unit or upper_unit)
            hi = _micrometres(upper, upper_unit)
            if 0 < lo < hi:
                ranges.append((lo, hi, item["citationId"], sentence.strip()))
    if not ranges or len({(lo, hi) for lo, hi, _, _ in ranges}) != 1:
        return None
    lo, hi, citation, quote = ranges[0]
    relation = "range" if requested is None else "below" if requested < lo else "above" if requested > hi else "within"
    original = quantity.group(0) if quantity else ""
    converted = _display(requested) if requested is not None else ""
    lower, upper = _display(lo), _display(hi)
    if range_question:
        text = (f"Der dokumentierte Wellenlängenbereich von {instrument} beträgt {lower}–{upper} µm."
                if language == "de" else
                f"{instrument}'s documented wavelength range is {lower}–{upper} µm.")
    elif language == "de":
        if relation == "within":
            text = (f"{original} (= {converted} µm) liegt im dokumentierten Wellenlängenbereich von "
                    f"{instrument} ({lower}–{upper} µm). Das allein bestätigt nicht die Verfügbarkeit "
                    "eines bestimmten Filters oder Modus.")
        else:
            position = "unterhalb" if relation == "below" else "oberhalb"
            text = (f"Nein. {original} (= {converted} µm) liegt {position} des dokumentierten "
                    f"Wellenlängenbereichs von {instrument} ({lower}–{upper} µm).")
    elif relation == "within":
        text = (f"{original} (= {converted} µm) is within {instrument}'s documented wavelength "
                f"range ({lower}–{upper} µm). This alone does not confirm availability "
                "of a particular filter or mode.")
    else:
        text = (f"No. {original} (= {converted} µm) is {relation} {instrument}'s documented "
                f"wavelength range ({lower}–{upper} µm).")
    return WavelengthAnswer(
        ValidationResult(f"{text} [{citation}]", 1, 0, 0, False),
        {"operation": "wavelength-range-v1", "requestedMicrometres": str(requested) if requested is not None else None,
         "lowerMicrometres": str(lo), "upperMicrometres": str(hi), "relation": relation,
         "citationId": citation, "quote": quote},
    )
