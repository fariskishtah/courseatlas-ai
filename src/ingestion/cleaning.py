"""Controlled text cleaning. Conservative on purpose: never strips code, math, tables or headings."""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

_CONTROL = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​‌‍﻿]")
_PAGE_NUM = re.compile(r"^\s*(page\s+)?\d+(\s*(/|of)\s*\d+)?\s*$", re.I)
# common mojibake produced by UTF-8 decoded as latin-1
_MOJIBAKE = {"â€™": "'", "â€œ": '"', "â€\x9d": '"', "â€“": "-", "â€”": "-", "Â ": " ", "Â": ""}


def normalize(text: str) -> str:
    for bad, good in _MOJIBAKE.items():
        text = text.replace(bad, good)
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL.sub("", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def find_repeated_lines(pages: list[str], min_ratio: float = 0.6) -> set[str]:
    """Lines (header/footer candidates) repeated on most pages. Only used for docs with >= 3 pages."""
    if len(pages) < 3:
        return set()
    counts: Counter[str] = Counter()
    for p in pages:
        lines = [l.strip() for l in p.split("\n") if l.strip()]
        edge = set(lines[:3] + lines[-3:])
        counts.update(edge)
    return {l for l, c in counts.items() if c / len(pages) >= min_ratio and len(l) < 120}


def strip_page_furniture(page_text: str, repeated: set[str]) -> str:
    out = []
    for line in page_text.split("\n"):
        s = line.strip()
        # page-number lines and footers that begin with "Page N" etc.
        if s in repeated or _PAGE_NUM.match(s) or re.fullmatch(r"page\s+\d+", s, re.I):
            continue
        out.append(line)
    return "\n".join(out)


def unwrap_lines(text: str) -> str:
    """Join hard-wrapped lines inside paragraphs but keep code, lists and headings on their own lines."""
    paras = re.split(r"\n\s*\n", text)
    fixed = []
    for p in paras:
        lines = p.split("\n")
        keep = any(re.match(r"^\s{2,}\S", l) or re.match(r"^\s*([-*•]|\d+[.)])\s", l) or l.rstrip().endswith(":")
                   or re.match(r"^[A-Z0-9][A-Z0-9 &:/-]{5,}$", l.strip()) for l in lines)
        if keep or len(lines) == 1:
            fixed.append("\n".join(l.rstrip() for l in lines))
        else:
            joined = " ".join(l.strip() for l in lines)
            fixed.append(joined)
    return "\n\n".join(fixed)


def collapse_whitespace(text: str) -> str:
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)  # inner runs of spaces; keeps leading code indentation
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str, unwrap: bool = True) -> str:
    text = normalize(text)
    if unwrap:
        text = unwrap_lines(text)
    return collapse_whitespace(text)


def drop_duplicate_paragraphs(paragraphs: list[str]) -> list[str]:
    seen, out = set(), []
    for p in paragraphs:
        key = re.sub(r"\s+", " ", p.strip().lower())
        if len(key) > 40 and key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out
