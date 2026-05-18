import csv
import re
import unicodedata
from pathlib import Path


def to_ascii(value: str) -> str:
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
        "–": "-",
        "—": "-",
        "’": "'",
        "“": '"',
        "”": '"',
        "…": "...",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    normalized = unicodedata.normalize("NFKD", value)
    return normalized.encode("ascii", "ignore").decode("ascii")


def main() -> None:
    md_path = Path("D:/dev/git/privat/Studium/AFE/jira.md")
    csv_path = Path("D:/dev/git/privat/Studium/AFE/jira_import.csv")

    lines = md_path.read_text(encoding="utf-8").splitlines()
    rows = []

    epic_id = "KAIP-001"
    rows.append(
        {
            "Issue Id": epic_id,
            "Issue Type": "Epic",
            "Summary": "KnowledgeAI Plattform Neuaufbau (Clean Architecture)",
            "Description": (
                "End-to-End Neuaufbau von Backend, Admin-App und UI mit Domain-Driven Modulen, "
                "testbarer Architektur und klaren API-Verträgen."
            ),
            "Priority": "High",
            "Labels": "knowledgeai,platform,clean-architecture",
            "Epic Name": "KnowledgeAI Plattform Neuaufbau",
            "Epic Link": "",
        }
    )

    section = ""
    phase = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("## 4) Tickets - KnowledgeAi-BE"):
            section = "backend"
        elif line.startswith("## 5) Tickets - KnowledgeAI-AdminApp"):
            section = "adminapp"
        elif line.startswith("## 6) Tickets - Knowledge-AI-UI"):
            section = "ui"
        elif line.startswith("## 7) Cross-Cutting Tickets"):
            section = "cross-cutting"
        elif line.startswith("### PHASE 1"):
            phase = "phase-1"
        elif line.startswith("### PHASE 2"):
            phase = "phase-2"
        elif line.startswith("### PHASE 3"):
            phase = "phase-3"

        match = re.match(r"^###\s+STORY\s+([A-Z0-9-]+)\s+-\s+(.+)$", line)
        if not match:
            i += 1
            continue

        issue_id = match.group(1).strip()
        summary = match.group(2).strip()

        j = i + 1
        block = []
        while j < len(lines):
            nxt = lines[j].strip()
            if nxt.startswith("### STORY ") or nxt.startswith("---") or nxt.startswith("## "):
                break
            block.append(lines[j].rstrip())
            j += 1

        references = []
        acceptance = []
        notes = []
        mode = "notes"

        for raw in block:
            current = raw.strip()
            if current.startswith("**Referenzbild(er):**"):
                references.append(current.replace("**Referenzbild(er):**", "").strip())
                continue
            if current == "**Akzeptanzkriterien**":
                mode = "acceptance"
                continue
            if current.startswith("- "):
                if mode == "acceptance":
                    acceptance.append(current[2:].strip())
                else:
                    notes.append(current[2:].strip())
            elif current:
                notes.append(current)

        description_parts = [f"Bereich: {section}"]
        if phase:
            description_parts.append(f"Empfohlene Phase: {phase}")
        if references:
            description_parts.append("Referenzbild(er): " + " | ".join(references))
        if notes:
            description_parts.append("Notizen:\n- " + "\n- ".join(notes))
        if acceptance:
            description_parts.append("Akzeptanzkriterien:\n- " + "\n- ".join(acceptance))

        labels = ["knowledgeai", section]
        if phase:
            labels.append(phase)

        rows.append(
            {
                "Issue Id": issue_id,
                "Issue Type": "Story",
                "Summary": summary,
                "Description": "\n\n".join(description_parts),
                "Priority": "Medium",
                "Labels": ",".join(labels),
                "Epic Name": "",
                "Epic Link": epic_id,
            }
        )

        i = j

    fieldnames = [
        "Issue Id",
        "Issue Type",
        "Summary",
        "Description",
        "Priority",
        "Labels",
        "Epic Name",
        "Epic Link",
    ]
    ascii_rows = []
    for row in rows:
        ascii_row = {}
        for key, val in row.items():
            if isinstance(val, str):
                ascii_row[key] = to_ascii(val)
            else:
                ascii_row[key] = val
        ascii_rows.append(ascii_row)

    with csv_path.open("w", newline="", encoding="ascii") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(ascii_rows)

    print(f"Wrote {len(rows)} issues to {csv_path}")


if __name__ == "__main__":
    main()
