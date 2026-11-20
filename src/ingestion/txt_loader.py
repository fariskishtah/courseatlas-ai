"""TXT extraction with encoding validation, paragraph segmentation and line-number references."""
from __future__ import annotations

import re
from pathlib import Path

from ..models import Block, ExtractedDoc
from . import cleaning
from .common import IngestionError, finalize

_RULE = re.compile(r"^[=\-_*#~\s]{3,}$")


def _is_heading(line: str) -> bool:
    s = line.strip()
    return 4 <= len(s) <= 80 and s.upper() == s and bool(re.search(r"[A-Z]{3}", s)) and not s.endswith(".") and not _RULE.match(s)


def decode(raw: bytes) -> tuple[str, str]:
    if b"\x00" in raw:
        raise IngestionError("File contains NUL bytes (binary data)")
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise IngestionError("Cannot decode text")


def load_txt(path: Path) -> ExtractedDoc:
    text, enc = decode(path.read_bytes())
    text = cleaning.normalize(text)
    lines = text.split("\n")
    blocks: list[Block] = []
    section: str | None = None
    for i, line in enumerate(lines):
        if not line.strip() or _RULE.match(line):
            continue
        if _is_heading(line):
            section = line.strip()
        body = cleaning.collapse_whitespace(line)
        if body:   # one block per line keeps exact line-number provenance; the chunker packs them back together
            blocks.append(Block(text=body, section=section, line_start=i + 1, line_end=i + 1))
    blocks = finalize(blocks)
    if not blocks:
        raise IngestionError("TXT file is empty")
    warn = [] if enc.startswith("utf-8") else [f"Decoded with fallback encoding {enc}"]
    return ExtractedDoc(blocks=blocks, method=f"text ({enc}), paragraph segmentation", page_count=None, warnings=warn)
