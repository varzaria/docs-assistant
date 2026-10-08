"""Render the company documents in source/*.md to paginated PDFs in documents/.

The Markdown files are the editable originals; the PDFs are what the assistant
reads, so answers can cite page numbers like a real document would.
Supports a small Markdown subset: # / ## / ### headings, paragraphs, **bold**,
- bullets, 1. numbered lists, and | pipe | tables |.
"""

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).parent
SOURCE = ROOT / "source"
OUT = ROOT / "documents"

base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("title", parent=base["Title"], fontSize=20, alignment=TA_LEFT, spaceAfter=4),
    "meta": ParagraphStyle("meta", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#555555"), spaceAfter=10),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4),
    "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=11, spaceBefore=6, spaceAfter=2),
    "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10.5, leading=14, spaceAfter=6),
    "cell": ParagraphStyle("cell", parent=base["Normal"], fontSize=9.5, leading=12),
}


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def make_table(rows: list[list[str]]) -> Table:
    data = [[Paragraph(inline(c), STYLES["cell"]) for c in row] for row in rows]
    table = Table(data, colWidths=[(A4[0] - 40 * mm) / len(rows[0])] * len(rows[0]), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def parse(markdown: str) -> tuple[str, list]:
    lines = markdown.splitlines()
    title, story, i = "", [], 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
        elif line.startswith("# "):
            title = line[2:]
            story.append(Paragraph(inline(title), STYLES["title"]))
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            story.append(Paragraph(inline(lines[i].strip()), STYLES["meta"]))  # line under the title
            i += 1
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), STYLES["h3"]))
            i += 1
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), STYLES["h2"]))
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):
                    rows.append(cells)
                i += 1
            story += [make_table(rows), Spacer(1, 6)]
        elif re.match(r"^(- |\d+\. )", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(ListItem(Paragraph(inline(re.sub(r"^(- |\d+\. )", "", lines[i])), STYLES["body"]), leftIndent=12))
                i += 1
            story.append(ListFlowable(items, bulletType="1" if ordered else "bullet", start="1" if ordered else None, leftIndent=14))
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||- |\d+\. )", lines[i]):
                para.append(lines[i].strip())
                i += 1
            story.append(Paragraph(inline(" ".join(para)), STYLES["body"]))
    return title, story


def build(md_path: Path) -> Path:
    title, story = parse(md_path.read_text(encoding="utf-8"))
    out_path = OUT / (re.sub(r"^\d+_", "", md_path.stem) + ".pdf")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(20 * mm, 12 * mm, f"Kildare Craft Coffee Ltd  |  {title}")
        canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, title=title, author="Kildare Craft Coffee Ltd",
                            leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out_path


def main() -> None:
    OUT.mkdir(exist_ok=True)
    from pypdf import PdfReader
    for md in sorted(SOURCE.glob("*.md")):
        pdf = build(md)
        print(f"{pdf.name:<32} {len(PdfReader(pdf).pages)} pages")


if __name__ == "__main__":
    main()
