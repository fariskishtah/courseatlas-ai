"""Validate that every citation in an answer maps to a chunk that was really retrieved."""
from __future__ import annotations

import re

_CITE = re.compile(r"\[\s*((?:S\d+)(?:\s*[,;]\s*S\d+)*)\s*\]", re.I)
_BARE = re.compile(r"\bS(\d+)\b")


def validate_citations(answer: str, valid_ids: set[str]) -> dict:
    """Returns cleaned text (invalid citations removed) and the list of valid / invalid ids found."""
    used, invalid = [], []

    def repl(m: re.Match) -> str:
        ids = [x.upper() for x in re.split(r"\s*[,;]\s*", m.group(1))]
        good = [i for i in ids if i in valid_ids]
        invalid.extend(i for i in ids if i not in valid_ids)
        for g in good:
            if g not in used:
                used.append(g)
        return "".join(f"[{g}]" for g in good)

    cleaned = _CITE.sub(repl, answer)
    return {"text": re.sub(r"[ \t]+([.,;:])", r"\1", re.sub(r"[ \t]{2,}", " ", cleaned)).strip(),
            "used": used, "invalid": invalid, "has_valid": bool(used)}
