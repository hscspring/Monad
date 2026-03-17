"""markdown_to_pdf — Convert Markdown text to a styled PDF with CJK support."""

import os
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

_FONT = "STSong-Light"


def _make_styles():
    def _s(name, size=11, leading=18, align=TA_LEFT, sb=0, sa=6, bold=False):
        font = _FONT
        return ParagraphStyle(
            name, fontName=font, fontSize=size, leading=leading,
            alignment=align, spaceBefore=sb, spaceAfter=sa,
        )
    return {
        "h1": _s("h1", 18, 26, TA_CENTER, sa=10),
        "h2": _s("h2", 15, 22, sb=14, sa=8),
        "h3": _s("h3", 13, 20, sb=10, sa=6),
        "body": _s("body"),
        "li": _s("li", 11, 18, sa=3),
        "footer": _s("footer", 9, 14, TA_CENTER, sa=4),
    }


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text):
    """Handle bold (**), italic (*), and inline code (`)."""
    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)
    return text


def _parse_markdown(md_text, styles):
    """Parse markdown into a list of reportlab flowables."""
    story = []
    lines = md_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(_inline(stripped[4:]), styles["h3"]))
        elif stripped.startswith("## "):
            story.append(Paragraph(_inline(stripped[3:]), styles["h2"]))
        elif stripped.startswith("# "):
            story.append(Paragraph(_inline(stripped[2:]), styles["h1"]))
            story.append(HRFlowable(width="100%", thickness=1, color="grey"))
            story.append(Spacer(1, 6))
        elif stripped == "---" or stripped == "***":
            story.append(HRFlowable(width="100%", thickness=0.5, color="lightgrey"))
            story.append(Spacer(1, 4))
        elif re.match(r"^[-*+] ", stripped):
            bullet_text = re.sub(r"^[-*+] ", "", stripped)
            story.append(Paragraph("&nbsp;&nbsp;• " + _inline(bullet_text), styles["li"]))
        elif re.match(r"^\d+\. ", stripped):
            story.append(Paragraph("&nbsp;&nbsp;" + _inline(stripped), styles["li"]))
        else:
            para_lines = [stripped]
            while i + 1 < len(lines) and lines[i + 1].strip() and not _is_block_start(lines[i + 1].strip()):
                i += 1
                para_lines.append(lines[i].strip())
            story.append(Paragraph(_inline(" ".join(para_lines)), styles["body"]))

        i += 1

    return story


def _is_block_start(s):
    if s.startswith("#"):
        return True
    if s in ("---", "***"):
        return True
    if re.match(r"^[-*+] ", s):
        return True
    if re.match(r"^\d+\. ", s):
        return True
    return False


def run(**kwargs):
    """Convert Markdown to PDF.

    Args:
        content: Markdown string (mutually exclusive with file_path)
        file_path: Path to a .md file (mutually exclusive with content)
        output_filename: Output PDF filename (default: output.pdf)
    """
    content = kwargs.get("content", "")
    file_path = kwargs.get("file_path", "")
    output_filename = kwargs.get("output_filename", "output.pdf")

    if not content and file_path:
        fp = os.path.expanduser(file_path)
        if not os.path.exists(fp):
            return f"Error: file not found: {fp}"
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()

    if not content:
        return "Error: no content provided (pass content= or file_path=)"

    if not output_filename.endswith(".pdf"):
        output_filename += ".pdf"

    output_dir = globals().get("MONAD_OUTPUT_DIR", os.path.expanduser("~/.monad/output"))
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, output_filename)

    styles = _make_styles()
    story = _parse_markdown(content, styles)

    if not story:
        return "Error: parsed markdown is empty"

    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    doc.build(story)

    return f"PDF 已生成: {out_path}"
