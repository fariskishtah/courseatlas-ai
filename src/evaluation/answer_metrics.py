"""Answer-level metrics: keyword-proxy correctness, abstention, citation validity/relevance."""
from __future__ import annotations

import re

from .retrieval_metrics import is_relevant

ABSTAIN_RE = re.compile(r"do(es)? not contain enough information|not enough (information|evidence)|cannot be answered|"
                        r"i (do not|don't|cannot|can't) (know|find|answer)|no information|not (covered|mentioned|provided)|"
                        r"unable to (answer|find)|please (clarify|specify|provide more)", re.I)


def keyword_correct(answer: str, criteria: list[str]) -> bool:
    return any(re.search(c, answer, re.I | re.S) for c in criteria) if criteria else False


def citation_relevant(result: dict, gold: list[dict]) -> bool:
    """True if at least one cited source is a gold-relevant chunk."""
    by_id = {s["id"]: s for s in result["sources"]}
    return any(is_relevant(by_id[u]["meta"], by_id[u]["text"], gold) is not None for u in result["used"] if u in by_id)


def looks_like_abstention(text: str) -> bool:
    return bool(ABSTAIN_RE.search(text))
