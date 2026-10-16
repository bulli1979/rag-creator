"""HTML conversion which preserves data tables but removes layout wrappers."""
import re
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify


def meaningful_title(html: str, url: str = "") -> str:
    soup = BeautifulSoup(html, "html5lib")
    for tag in [*soup.find_all(["h1", "h2"]), soup.find("title")]:
        if tag:
            title = tag.get_text(" ", strip=True)
            if title and not re.fullmatch(r"Nordic\s+Optical\s+Telescope", title, re.I):
                return title
    return url.rstrip("/").rsplit("/", 1)[-1] or "Document"


def html_to_markdown(html: str) -> str:
    # html5lib repairs the site's missing </TD>/<TR> tags before inspecting rows.
    soup = BeautifulSoup(html, "html5lib")
    for tag in list(soup.find_all(["script", "style", "nav", "footer", "noscript", "iframe", "head"])):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    for link in list(soup.find_all("a")):
        if re.fullmatch(r"(?:back to top|top)", link.get_text(" ", strip=True), re.I):
            link.decompose()
    tables = {}
    # Innermost tables first: outer layout tables must never swallow their data.
    for table in reversed(list(soup.find_all("table"))):
        rows = [r for r in table.find_all("tr") if r.find_parent("table") is table]
        cells = [r.find_all(["th", "td"], recursive=False) for r in rows]
        widths = [sum(int(c.get("colspan", 1)) for c in row) for row in cells]
        layout = (not rows or max((len(row) for row in cells), default=0) < 2
                  or table.find(["h1", "h2", "h3", "h4", "ul", "ol", "pre", "table"]) is not None
                  or "NOTBOTDATATABLE" in table.get_text()
                  or len(rows) <= 2 and any(len(c.get_text()) > 1000 for row in cells for c in row))
        if layout:
            for tag in list(table.find_all(["tr", "td", "th", "tbody", "thead", "tfoot"])):
                if tag.find_parent("table") is table:
                    tag.unwrap()
            table.unwrap()
            continue
        caption = ""
        if cells and len(cells[0]) == 1 and int(cells[0][0].get("colspan", 1)) > 1:
            caption = cells.pop(0)[0].get_text(" ", strip=True)
        if not cells:
            table.unwrap()
            continue
        # Expand spans to a rectangular grid. Otherwise a second wind row under
        # a three-row humidity label silently becomes a humidity instruction.
        width = max(sum(int(c.get("colspan", 1)) for c in row) for row in cells)
        rendered = []
        spanning = {}
        for row_number, row in enumerate(cells):
            values = [""] * width
            occupied = set()
            for column, (last_row, value) in list(spanning.items()):
                if row_number <= last_row:
                    values[column] = value
                    occupied.add(column)
                else:
                    del spanning[column]
            column = 0
            for cell in row:
                while column in occupied:
                    column += 1
                # Retain sentence boundaries in multi-instruction cells. The
                # blank line between closing and reopening is not whitespace.
                for br in cell.find_all("br"):
                    br.replace_with(soup.new_string("\n"))
                parts = [" ".join(part.split()) for part in cell.get_text("", strip=False).splitlines()]
                value = "; ".join(part for part in parts if part).replace("|", "\\|")
                if not value:
                    value = cell.get_text(" ", strip=True).replace("|", "\\|")
                colspan = max(1, int(cell.get("colspan", 1)))
                rowspan = max(1, int(cell.get("rowspan", 1)))
                for index in range(column, column + colspan):
                    if index >= len(values):
                        values.append("")
                    values[index] = value
                    occupied.add(index)
                    if rowspan > 1:
                        spanning[index] = (row_number + rowspan - 1, value)
                column += colspan
            rendered.append(values)
        width = max(len(row) for row in rendered)
        rendered = [row + [""] * (width - len(row)) for row in rendered]
        # Carry component column semantics into shorthand '#4' row labels.
        first_heading = rendered[0][0].lower()
        entity = "fiber" if re.search(r"fib(?:er|re)", first_heading) else ""
        if entity:
            for row in rendered[1:]:
                row[0] = re.sub(r"^#(?=\d)", entity + " #", row[0])
        has_header = any(c.name == "th" for c in cells[0])
        if not has_header:
            rendered.insert(0, [f"Column {i+1}" for i in range(width)])
        lines = ["| " + " | ".join(rendered[0]) + " |",
                 "| " + " | ".join(["---"] * width) + " |"]
        lines += ["| " + " | ".join(row) + " |" for row in rendered[1:]]
        marker = f"NOTBOTDATATABLE{len(tables)}TOKEN"
        # A table caption becomes section scope, keeping spare/default tables apart.
        tables[marker] = ("\n\n#### " + caption + "\n\n" if caption else "\n\n") + "\n".join(lines) + "\n\n"
        table.replace_with(soup.new_string(marker))
    # Short bold standalone labels commonly indicate configuration subsections.
    for bold in list(soup.find_all(["b", "strong"])):
        label = bold.get_text(" ", strip=True)
        if re.match(r"(?:New|Spare|Old|Current|Default) bundle\s*:", label, re.I):
            heading = soup.new_tag("h4")
            heading.string = label
            bold.replace_with(heading)
    text = markdownify(str(soup), heading_style="ATX", strip=["img"])
    for marker, value in reversed(list(tables.items())):
        text = text.replace(marker, value)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
