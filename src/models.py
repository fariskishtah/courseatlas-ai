"""Shared dataclasses."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Block:
    """A piece of extracted text with provenance, before chunking."""
    text: str
    kind: str = "text"            # text | row (atomic, never merged or split)
    page: int | None = None
    section: str | None = None
    row: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    start: int = 0                # char offset in the document's cleaned text
    end: int = 0


@dataclass
class ExtractedDoc:
    blocks: list[Block]
    method: str
    page_count: int | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Chunk:
    chunk_id: str
    course_id: str
    doc_id: str
    doc_title: str
    filename: str
    file_type: str
    location: str                 # human label: "Page 3", "Section: X", "Row 7", "Lines 4-9"
    page: int | None
    section: str | None
    row: int | None
    line_start: int | None
    line_end: int | None
    char_start: int
    char_end: int
    chunk_index: int
    content_hash: str
    text: str

    def metadata(self) -> dict:
        d = asdict(self)
        d.pop("text")
        return {k: ("" if v is None else v) for k, v in d.items()}
