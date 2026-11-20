"""Question validation and course-scope resolution (course isolation is enforced here AND by a metadata filter)."""
from __future__ import annotations

import re

MAX_QUESTION_CHARS = 1000
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InvalidQuestion(ValueError):
    pass


def validate_question(q: str | None) -> str:
    if q is None or not q.strip():
        raise InvalidQuestion("Please type a question.")
    q = _CTRL.sub("", q).strip()
    if len(q) > MAX_QUESTION_CHARS:
        raise InvalidQuestion(f"Question is too long (max {MAX_QUESTION_CHARS} characters).")
    return q


def resolve_scope(selected: str | list[str] | None, known: set[str], allow_multi: bool = False) -> list[str]:
    """Returns the explicit list of course ids to search. Never silently widens the scope."""
    if selected is None or selected == "" or selected == []:
        raise InvalidQuestion("Select a course first.")
    ids = [selected] if isinstance(selected, str) else list(selected)
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise InvalidQuestion(f"Unknown course: {unknown[0]}")
    if len(ids) > 1 and not allow_multi:
        raise InvalidQuestion("Multi-course search must be enabled explicitly.")
    return ids
