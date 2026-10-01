"""Derive small auditable facts from numbered reference-table rows.

No instrument values are encoded here. Only unique, explicitly labeled rows in
supplied evidence can establish identifiers, their attributes and counts.
"""
import re

_ENTITY = re.compile(r"\b(fib(?:er|re)|faser|grism|filter)\s*(?:#|number\s*|nummer\s*)?(\d+)\b", re.I)


def reference_rows(text: str) -> list[dict]:
    matches = list(_ENTITY.finditer(text))
    rows = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else min(len(text), start+240)
        row = text[start:end].split("\n")[0].strip(" |\n")
        # Rows require a table/list boundary and an explicit technical role/value;
        # a prose mention of a numbered component is not an enumerable catalogue.
        before = text[max(0,start-3):start]
        if "|" not in before and start and "\n" not in before:
            continue
        if not re.search(r"\b(?:low.res|med(?:ium)?.res|high.res|calibration|arcsec|R\s*=|nm|Å)\b", row, re.I):
            continue
        entity = "fiber" if match.group(1).lower() in ("fiber","fibre","faser") else match.group(1).lower()
        rows.append({"entity":entity,"id":match.group(2),"text":row,
                     "role":"calibration" if re.search(r"calib|simultaneous.ThAr",row,re.I) else "science"})
    return rows


def derived_facts(text: str) -> list[dict]:
    rows = reference_rows(text)
    facts = []
    for entity in sorted({row["entity"] for row in rows}):
        relevant = [row for row in rows if row["entity"]==entity]
        ids = [row["id"] for row in relevant]
        if len(ids)<2 or len(ids)!=len(set(ids)):
            continue
        for role in ("science","calibration","total"):
            matching = relevant if role=="total" else [row for row in relevant if row["role"]==role]
            if matching:
                facts.append({"operation":"count_rows","entity":entity,"role":role,
                              "value":len(matching),"rowIds":[row["id"] for row in matching]})
    return facts
