#!/usr/bin/env python3
"""Build docs/APP_FLOW_AND_ARCHITECTURE.pdf from docs/APP_FLOW_AND_ARCHITECTURE.md.

Professional layout: cover page, section accents, tables, code blocks, page footers.

  uv run python scripts/gen_architecture_pdf.py
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ACCENT = colors.HexColor("#b8860b")
ACCENT_HEX = "#b8860b"
ACCENT_LIGHT = colors.HexColor("#e8d5a3")
TEXT = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#555555")
RULE = colors.HexColor("#cccccc")


def _split_md_bold(s: str) -> str:
    parts = re.split(r"\*\*", s)
    if len(parts) % 2 == 0:
        return escape(s)
    out: list[str] = []
    bold = False
    for p in parts:
        if bold:
            out.append(f"<b>{escape(p)}</b>")
        else:
            out.append(escape(p))
        bold = not bold
    return "".join(out)


def _para_html(block: str) -> str:
    return _split_md_bold(block).replace("\n", "<br/>")


def _md_table_to_flowable(block: str, body_style: ParagraphStyle) -> Table | None:
    lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
    if not lines or not lines[0].startswith("|"):
        return None
    rows: list[list[str]] = []
    for ln in lines:
        if re.match(r"^\|?[\s\-:|]+\|?$", ln):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return None
    max_cols = max(len(r) for r in rows)
    normalized: list[list[Paragraph]] = []
    for i, r in enumerate(rows):
        padded = r + [""] * (max_cols - len(r))
        row_p: list[Paragraph] = []
        for c in padded:
            font = "Helvetica-Bold" if i == 0 else "Helvetica"
            sz = 8 if i == 0 else 8.5
            st = ParagraphStyle(
                f"tbl_{i}",
                parent=body_style,
                fontName=font,
                fontSize=sz,
                leading=sz + 2,
                textColor=TEXT,
            )
            row_p.append(Paragraph(_para_html(c), st))
        normalized.append(row_p)
    t = Table(normalized, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT_LIGHT),
                ("TEXTCOLOR", (0, 0), (-1, 0), TEXT),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ]
        )
    )
    return t


def _parse_body_blocks(md_body: str) -> list[str]:
    """Split markdown into blocks (paragraphs / headings); keep fenced code as one block each."""
    parts: list[str] = []
    lines = md_body.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        if line.strip().startswith("```"):
            fence_lines = [line]
            i += 1
            while i < n:
                fence_lines.append(lines[i])
                if lines[i].strip() == "```":
                    i += 1
                    break
                i += 1
            parts.append("\n".join(fence_lines).strip())
            continue

        if not line.strip():
            i += 1
            continue

        buf: list[str] = [line]
        i += 1
        while i < n and lines[i].strip() != "":
            if re.match(r"^```", lines[i].strip()):
                i -= 1
                break
            buf.append(lines[i])
            i += 1
        block = "\n".join(buf).strip()
        if block:
            parts.append(block)
        while i < n and not lines[i].strip():
            i += 1

    return [p for p in parts if p]


def _block_to_flowables(
    block: str,
    *,
    h2: ParagraphStyle,
    h3: ParagraphStyle,
    body: ParagraphStyle,
    code: ParagraphStyle,
) -> list:
    block = block.strip()
    if not block:
        return []
    if block == "---":
        return [
            Spacer(1, 0.12 * inch),
            HRFlowable(width="100%", thickness=0.8, color=ACCENT, spaceAfter=10, spaceBefore=4),
            Spacer(1, 0.08 * inch),
        ]
    if block.startswith("```"):
        lines = block.splitlines()
        inner = "\n".join(lines[1:-1] if len(lines) > 2 else [])
        fixed = "<br/>".join(escape(line) for line in inner.splitlines())
        return [
            Spacer(1, 0.06 * inch),
            Paragraph(f'<font face="Courier" size="8" color="#333333">{fixed}</font>', code),
            Spacer(1, 0.08 * inch),
        ]
    if block.startswith("## "):
        title = escape(block[3:].strip())
        return [
            Spacer(1, 0.14 * inch),
            HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=6, spaceBefore=2),
            Paragraph(
                f'<font color="{ACCENT_HEX}">■</font> &nbsp; <b>{title}</b>',
                h2,
            ),
            Spacer(1, 0.06 * inch),
        ]
    if block.startswith("### "):
        return [
            Spacer(1, 0.1 * inch),
            Paragraph(f"<b>{escape(block[4:].strip())}</b>", h3),
            Spacer(1, 0.04 * inch),
        ]
    if block.startswith("|"):
        tbl = _md_table_to_flowable(block, body)
        if tbl:
            return [Spacer(1, 0.06 * inch), tbl, Spacer(1, 0.12 * inch)]
    lines = block.splitlines()
    if lines and all(
        re.match(r"^[-*]\s+", ln.strip()) or not ln.strip() for ln in lines
    ) and any(re.match(r"^[-*]\s+", ln.strip()) for ln in lines):
        out = []
        for line in lines:
            t = re.sub(r"^[-*]\s+", "", line.strip()).strip()
            if t:
                out.append(Paragraph("• &nbsp; " + _para_html(t), body))
        out.append(Spacer(1, 0.06 * inch))
        return out
    # Paragraph (may contain **bold**)
    if block.startswith("*") and block.endswith("*") and "\n" not in block:
        inner = block.strip("*").strip()
        return [
            Paragraph(f"<i>{escape(inner)}</i>", body),
            Spacer(1, 0.08 * inch),
        ]
    return [Paragraph(_para_html(block), body), Spacer(1, 0.06 * inch)]


def _footer_canvas(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    w, _h = letter
    y = 0.55 * inch
    canvas.drawString(doc.leftMargin, y, "AI Career Assistant — Architecture & Agentic Design")
    # Physical page 2 = first body page → show as page 1 for readers
    body_page = canvas.getPageNumber() - 1
    canvas.drawRightString(w - doc.rightMargin, y, f"Page {max(1, body_page)}")
    canvas.restoreState()


def _cover_canvas(_canvas, _doc) -> None:
    """Cover page: no footer chrome."""
    return


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    md_path = root / "docs" / "APP_FLOW_AND_ARCHITECTURE.md"
    pdf_path = root / "docs" / "APP_FLOW_AND_ARCHITECTURE.pdf"
    raw = md_path.read_text(encoding="utf-8")

    marker = "## Document scope"
    idx = raw.find(marker)
    if idx == -1:
        head, body_md = "", raw
    else:
        head, body_md = raw[:idx], raw[idx:]

    title_line = "AI Career Assistant"
    m = re.search(r"^#\s+(.+)$", head, re.MULTILINE)
    if m:
        title_line = m.group(1).strip()

    styles = getSampleStyleSheet()
    cover_title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=30,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    cover_sub = ParagraphStyle(
        "CoverSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=13,
        leading=17,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceAfter=24,
    )
    cover_meta = ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=MUTED,
        alignment=TA_CENTER,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=TEXT,
        spaceAfter=4,
        spaceBefore=0,
    )
    h3 = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=TEXT,
        spaceAfter=4,
        spaceBefore=0,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=TEXT,
        spaceAfter=4,
        alignment=TA_LEFT,
    )
    code = ParagraphStyle(
        "CodeBlock",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=7.5,
        leading=9,
        leftIndent=8,
        rightIndent=8,
        backColor=colors.HexColor("#f4f4f4"),
        borderColor=RULE,
        borderWidth=0.5,
        borderPadding=6,
    )

    story: list = []

    # —— Cover ——
    story.append(Spacer(1, 2.0 * inch))
    story.append(Paragraph(escape(title_line), cover_title))
    story.append(Spacer(1, 0.25 * inch))
    story.append(
        Paragraph(
            escape("Architecture, user flow, agentic design, tradeoffs & performance"),
            cover_sub,
        )
    )
    story.append(HRFlowable(width="40%", thickness=2, color=ACCENT, hAlign="CENTER", spaceAfter=16, spaceBefore=4))
    story.append(Paragraph(escape("Technical reference — April 2026"), cover_meta))
    story.append(Paragraph(escape("Source: docs/APP_FLOW_AND_ARCHITECTURE.md"), cover_meta))
    story.append(PageBreak())

    for block in _parse_body_blocks(body_md):
        story.extend(
            _block_to_flowables(
                block,
                h2=h2,
                h3=h3,
                body=body,
                code=code,
            )
        )

    def _first_page(c, d):
        _cover_canvas(c, d)

    def _later_pages(c, d):
        _footer_canvas(c, d)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.9 * inch,
        bottomMargin=0.85 * inch,
        title="AI Career Assistant — Architecture",
        author="AI Career Assistant",
    )

    doc.build(story, onFirstPage=_first_page, onLaterPages=_later_pages)
    print(f"Wrote {pdf_path} ({pdf_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
