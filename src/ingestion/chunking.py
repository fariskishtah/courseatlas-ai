"""Provenance-preserving, structure-aware chunking.

Blocks (paragraphs, table rows, CSV rows) are packed greedily up to `chunk_size` characters.
Packing never crosses a page or section boundary, CSV rows and table rows are never split,
and oversized paragraphs are split on sentence boundaries. Overlap carries trailing blocks forward.
"""
from __future__ import annotations

import hashlib
import re

from ..models import Block, Chunk

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(])")


def _split_oversized(b: Block, size: int) -> list[Block]:
    if len(b.text) <= size or b.kind == "row" or "\n    " in b.text:  # keep rows and code intact
        return [b]
    pieces, cur = [], ""
    for s in _SENT.split(b.text):
        if cur and len(cur) + len(s) + 1 > size:
            pieces.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        pieces.append(cur)
    out, pos = [], b.start
    for p in pieces:
        nb = Block(text=p, kind=b.kind, page=b.page, section=b.section, row=b.row,
                   line_start=b.line_start, line_end=b.line_end, start=pos, end=pos + len(p))
        pos += len(p) + 1
        out.append(nb)
    return out


def _location(blocks: list[Block], file_type: str) -> tuple[str, dict]:
    b0 = blocks[0]
    page = b0.page
    section = b0.section
    if file_type == "csv":
        rows = [b.row for b in blocks if b.row is not None]
        label = "Header/schema" if rows == [0] else (f"Row {rows[0]}" if len(rows) == 1 else f"Rows {min(rows)}-{max(rows)}")
        return label, dict(page=None, section=section, row=rows[0] if rows else None, line_start=None, line_end=None)
    if file_type == "pdf":
        pages = sorted({b.page for b in blocks if b.page})
        label = f"Page {pages[0]}" if len(pages) == 1 else f"Pages {pages[0]}-{pages[-1]}"
        if section:
            label += f" ({section})"
        return label, dict(page=page, section=section, row=None, line_start=None, line_end=None)
    if file_type == "txt":
        ls = min(b.line_start for b in blocks if b.line_start)
        le = max(b.line_end for b in blocks if b.line_end)
        label = f"Lines {ls}-{le}" + (f" ({section})" if section else "")
        return label, dict(page=None, section=section, row=None, line_start=ls, line_end=le)
    label = f"Section: {section}" if section else "Document body"
    return label, dict(page=None, section=section, row=None, line_start=None, line_end=None)


def chunk_blocks(blocks: list[Block], *, course_id: str, doc_id: str, doc_title: str, filename: str,
                 file_type: str, chunk_size: int = 900, chunk_overlap: int = 120) -> list[Chunk]:
    units: list[Block] = []
    for b in blocks:
        units.extend(_split_oversized(b, chunk_size))

    groups: list[list[Block]] = []
    cur: list[Block] = []
    cur_len = 0

    def boundary(a: Block, b: Block) -> bool:
        return a.kind == "row" or b.kind == "row" or a.page != b.page or a.section != b.section

    for u in units:
        if cur and (boundary(cur[-1], u) or cur_len + len(u.text) + 2 > chunk_size):
            groups.append(cur)
            carry: list[Block] = []
            if not boundary(cur[-1], u):               # overlap only inside the same page/section
                tot = 0
                for prev in reversed(cur):
                    if tot + len(prev.text) > chunk_overlap:
                        break
                    carry.insert(0, prev)
                    tot += len(prev.text)
            cur, cur_len = carry, sum(len(x.text) + 2 for x in carry)
        cur.append(u)
        cur_len += len(u.text) + 2
    if cur:
        groups.append(cur)

    chunks: list[Chunk] = []
    for idx, g in enumerate(groups):
        text = ("\n" if file_type == "txt" else "\n\n").join(x.text for x in g)
        label, loc = _location(g, file_type)
        h = hashlib.sha256(text.encode()).hexdigest()[:16]
        chunks.append(Chunk(
            chunk_id=f"{doc_id}-{idx:04d}", course_id=course_id, doc_id=doc_id, doc_title=doc_title,
            filename=filename, file_type=file_type, location=label, chunk_index=idx,
            char_start=g[0].start, char_end=g[-1].end, content_hash=h, text=text, **loc))
    return chunks
