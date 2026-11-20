"""Citation identifiers are built from retrieval metadata, never by the LLM."""
from __future__ import annotations

from dataclasses import dataclass


def citation_label(meta: dict) -> str:
    """e.g. [Python Lecture Notes - Page 3 (3. Functions)] / [ML Model Evaluation Runs - Row 7]."""
    return f"[{meta.get('doc_title', 'Unknown')} — {meta.get('location', '?')}]"


@dataclass
class Source:
    sid: str                    # S1, S2, ... (per answer)
    chunk_id: str
    label: str
    text: str
    meta: dict
    rank: int
    score: float


def build_sources(hits, max_chars: int) -> list[Source]:
    """Select retrieved hits that fit the bounded context window and give each a stable per-answer id."""
    out, used = [], 0
    for h in hits:
        if out and used + len(h.text) > max_chars:
            continue
        out.append(Source(f"S{len(out) + 1}", h.chunk_id, citation_label(h.meta), h.text, h.meta, h.rank, h.score))
        used += len(h.text)
    return out
