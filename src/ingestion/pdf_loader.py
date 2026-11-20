"""PDF extraction with PyMuPDF. Page numbers are preserved. Scanned (image-only) pages are reported, never OCR'd."""
from __future__ import annotations

import re
from pathlib import Path

from ..models import Block, ExtractedDoc
from . import cleaning
from .common import IngestionError, finalize

_HEADING = re.compile(r"^\d+\.\s+\S.{0,80}$")
_CODEISH = re.compile(r"(^|\n)\s*(def |class |import |for .*:$|if .*:$|\w+ = .+|    \S)")


def load_pdf(path: Path) -> ExtractedDoc:
    import pymupdf
    try:
        doc = pymupdf.open(str(path))
    except Exception as e:  # corrupt / not a pdf
        raise IngestionError(f"Cannot open PDF: {e}") from e
    if doc.needs_pass:
        raise IngestionError("PDF is encrypted")
    warnings: list[str] = []
    raw_pages = []
    for page in doc:
        blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0]  # text blocks only
        raw_pages.append([cleaning.normalize(b[4]).strip() for b in blocks])
    repeated = cleaning.find_repeated_lines(["\n".join(p) for p in raw_pages])
    out: list[Block] = []
    section: str | None = None
    empty_pages = []
    for pno, paras in enumerate(raw_pages, start=1):
        kept = 0
        for para in paras:
            s = para.strip()
            if not s or s in repeated or cleaning._PAGE_NUM.match(s) or re.fullmatch(r"page\s+\d+", s, re.I):
                continue
            if any(line.strip() in repeated for line in s.split("\n")) and len(s.split("\n")) <= 2:
                continue
            if _HEADING.match(s.replace("\n", " ")):
                section = s.replace("\n", " ")
            text = para if _CODEISH.search(para) and "\n" in para else " ".join(l.strip() for l in para.split("\n"))
            out.append(Block(text=cleaning.collapse_whitespace(text), page=pno, section=section))
            kept += 1
        if kept == 0:
            empty_pages.append(pno)
    n = len(raw_pages)
    if empty_pages:
        warnings.append(f"No extractable text on page(s) {empty_pages} (empty or scanned; OCR not applied).")
    blocks = finalize(out)
    if not blocks:
        raise IngestionError("PDF contains no extractable text (possibly scanned; OCR is not enabled).")
    return ExtractedDoc(blocks=blocks, method="pymupdf.get_text(blocks)", page_count=n, warnings=warnings)
