"""Exact source-derived answers for complete operational component tables.

Generic table operations, not instrument answer constants. Prose, incomplete
inventories, designs and unsupported identifiers use grounded generation.
"""
from dataclasses import dataclass
import re
from .evidence_selection import classify_query
from .grounding import ValidationResult
from .table_facts import reference_rows


@dataclass(frozen=True)
class ReferenceAnswer:
    validation: ValidationResult
    derivation: dict


def answer_reference(query: str, evidence: list[dict], language: str = "en") -> ReferenceAnswer | None:
    intent = classify_query(query)
    if len(intent.instruments) != 1 or intent.historical or "technical_reference" in intent.categories:
        return None
    instrument = next(iter(intent.instruments))
    if re.search(r"\b(?:can|could|safe|bypass|override|why|troubleshoot|how to)\b", query, re.I):
        return None
    if not re.search(r"\bfib(?:er|re)s?\b|\bfaser\w*\b", query, re.I):
        return None
    count = bool(re.search(r"\bhow many\b|\bwie viele\b", query, re.I))
    measurements = re.search(r"\bresolution|resolving|aperture|diameter|size|arcsec|auflösung|durchmesser|bogensekund", query, re.I)
    calibration = bool(re.search(r"\b(?:calibration|calib|kalibration)\b", query, re.I))
    purpose = bool(re.search(r"\bused for\b|\bpurpose\b|\bwofür\b", query,re.I))
    ids = re.findall(r"(?:fib(?:er|re)|faser)\s*(?:\(\s*)?(?:#|number\s*|nummer\s*)?(\d+)\b|#(\d+)\b", query, re.I)
    wanted = {a or b for a,b in ids}
    if not (count or measurements or calibration or purpose and wanted):
        return None
    inventories = []
    for item in evidence:
        if (item.get("instrument", "").upper() != instrument or item.get("status") not in ("active","current")
                or item.get("sourceRole") != "operator_guide"):
            continue
        facts = item.get("derivedFacts", [])
        rows = reference_rows(item["content"])
        if facts and rows:
            inventories.append((item, rows, facts))
    if not inventories:
        return None
    item, rows, facts = inventories[0]
    citation = item["citationId"]
    if count:
        science = next((f for f in facts if f["role"] == "science"), None)
        calib = next((f for f in facts if f["role"] == "calibration"), None)
        if not science or not calib:
            return None
        text = (f"{instrument} hat {science['value']} wissenschaftliche Fasern und {calib['value']} Kalibrationsfaser."
                if language == "de" else
                f"{instrument} has {science['value']} science fibers and {calib['value']} calibration fiber.")
        selected_rows = rows
        operation = "complete-table-inventory-count-v1"
    else:
        selected_rows = [r for r in rows if (r["id"] in wanted if wanted else
                         r["role"] == "calibration" if calibration else r["role"] == "science")]
        if wanted and {r["id"] for r in selected_rows} != wanted:
            answer = (f"Die aktuelle Instrumenttabelle enthält keine Dokumentation für Faser {', '.join(sorted(wanted))}."
                      if language == "de" else
                      f"The current instrument table does not document fiber {', '.join(sorted(wanted))}. I cannot establish its requested specification.")
            return ReferenceAnswer(ValidationResult(answer, 0, 0, 0, True),
                                   {"operation":"unsupported-component-id-v1", "requestedIds":sorted(wanted),
                                    "knownIds":[r["id"] for r in rows],"citationId":citation})
        if not selected_rows:
            return None
        if re.search(r"\b(?:diameter|aperture|size|arcsec|durchmesser|bogensekund)", query, re.I):
            if not all(re.search(r"\d+(?:[.,]\d+)?\s*arcsec", r["text"], re.I) for r in selected_rows):
                return None
        label = "Dokumentierte Konfiguration für" if language == "de" else "Documented observing configuration for"
        text = f"{label} {instrument}:\n\n"
        text += "\n".join("- " + r["text"].replace(" | ", " — ").strip(" |") for r in selected_rows)
        operation = "complete-table-reference-rows-v1"
        if re.search(r"resolution|resolving|auflösung", query, re.I):
            primary_values = set(re.findall(r"\bR\s*=\s*(\d+)", item["content"]))
            for other in evidence:
                if (other.get("instrument", "").upper() != instrument
                        or other.get("sourceRole") != "instrument_landing" or other.get("status") not in ("active","current")):
                    continue
                other_values = set(re.findall(r"\bR\s*=\s*(\d+)", other["content"]))
                if len(other_values) >= 2 and primary_values and other_values != primary_values:
                    text += ("\n\nDocumentation discrepancy: the current operator guide above lists R="
                             + ", R=".join(sorted(primary_values, key=int))
                             + "; the instrument overview lists R=" + ", R=".join(sorted(other_values, key=int))
                             + f". Confirm the exact resolving power with the instrument specialist. [{other['citationId']}]")
                    break
    return ReferenceAnswer(
        ValidationResult(f"{text} [{citation}]", 1, 0, 0, False),
        {"operation":operation, "citationId":citation,"rowIds":[r["id"] for r in selected_rows],
         "source":item["source"],"quotedRows":[r["text"] for r in selected_rows]},
    )
