from __future__ import annotations

from ..models import Block


class IngestionError(Exception):
    """Raised when a document cannot be extracted (corrupt, empty, unreadable)."""


def finalize(blocks: list[Block]) -> list[Block]:
    """Drop empty blocks and assign document-level character offsets."""
    out, pos = [], 0
    for b in blocks:
        if not b.text.strip():
            continue
        b.start, b.end = pos, pos + len(b.text)
        pos = b.end + 2
        out.append(b)
    return out
