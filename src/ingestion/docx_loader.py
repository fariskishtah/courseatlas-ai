"""DOCX extraction: paragraphs, headings and tables in document order. No page numbers are invented."""
from __future__ import annotations

from pathlib import Path

from ..models import Block, ExtractedDoc
from . import cleaning
from .common import IngestionError, finalize


def load_docx(path: Path) -> ExtractedDoc:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    try:
        d = docx.Document(str(path))
    except Exception as e:
        raise IngestionError(f"Cannot open DOCX: {e}") from e
    blocks: list[Block] = []
    section: str | None = None
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            text = cleaning.clean_text(p.text, unwrap=False)
            if not text:
                continue
            style = (p.style.name or "") if p.style is not None else ""
            if style.startswith("Heading") or style == "Title":
                section = text
                if style == "Title":
                    continue
                blocks.append(Block(text=text, section=section))   # keep heading text searchable
            else:
                blocks.append(Block(text=text, section=section))
        elif tag == "tbl":
            t = Table(child, d)
            rows = [[cleaning.clean_text(c.text, unwrap=False) for c in r.cells] for r in t.rows]
            if not rows:
                continue
            header = rows[0]
            for ri, r in enumerate(rows[1:], start=1):
                cells = "; ".join(f"{h}: {v}" for h, v in zip(header, r))
                blocks.append(Block(text=f"Table row {ri} ({section or 'table'}) - {cells}", section=section))
    blocks = finalize(blocks)
    if not blocks:
        raise IngestionError("DOCX contains no text")
    return ExtractedDoc(blocks=blocks, method="python-docx (paragraphs + tables, document order)", page_count=None)
