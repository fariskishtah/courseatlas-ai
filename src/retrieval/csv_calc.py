"""Narrow, deterministic CSV aggregation (mean/sum/min/max/count of ONE numeric column).

The LLM never does arithmetic: when a question explicitly asks for an aggregate over a CSV column,
the number is computed with pandas from the real file and the method and rows are reported.
Anything else (filters, group-by, joins) is deliberately unsupported.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..ingestion.csv_loader import read_csv

AGG = {"average": "mean", "mean": "mean", "sum": "sum", "total": "sum", "max": "max", "maximum": "max",
       "highest": "max", "min": "min", "minimum": "min", "lowest": "min", "count": "count"}
CONTEXT_WORDS = ("csv", "column", "table", "dataset", "all runs", "across", "all rows", "all exercises", "all examples")


def _words(q: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", q.lower())


def _col_match(col: str, words: list[str]) -> float:
    toks = [t for t in re.split(r"[_\W]+", col.lower()) if t]
    hit = sum(any(w == t or (len(t) >= 3 and w.startswith(t)) for w in words) for t in toks)
    return hit / len(toks) if toks else 0.0


def try_answer(question: str, csv_docs: list[dict]) -> dict | None:
    q = question.lower()
    words = _words(q)
    agg_word = next((w for w in words if w in AGG), None)
    if not agg_word or not any(c in q for c in CONTEXT_WORDS):
        return None
    for d in csv_docs:
        p = Path(d["stored_path"])
        if not p.exists():
            continue
        df, _ = read_csv(p)
        cands = []
        for col in df.columns:
            s = pd.to_numeric(df[col].replace("", pd.NA), errors="coerce")
            if s.notna().sum() == 0 or s.notna().sum() < len(df) * 0.5:
                continue
            m = _col_match(col, words)
            if m == 1.0:
                cands.append((col, s))
        if not cands:
            continue
        func = AGG[agg_word]
        lines, vals = [], {}
        for col, s in cands:
            v = getattr(s.dropna(), func)()
            vals[col] = float(v)
            lines.append(f"{func} of '{col}' over {int(s.notna().sum())} rows = {round(float(v), 4)}")
        n = len(df)
        return {"answer_text": "Computed deterministically from the CSV (not by the language model): " + "; ".join(lines) + ".",
                "doc": d, "columns": list(vals), "values": vals, "func": func, "rows": n,
                "method": f"pandas Series.{func}() over non-empty numeric cells"}
    return None
