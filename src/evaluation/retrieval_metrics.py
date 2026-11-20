"""Retrieval metrics computed from hand-written gold labels (file + substring match)."""
from __future__ import annotations

import math


def is_relevant(hit_meta: dict, hit_text: str, gold: list[dict]) -> int | None:
    """Index of the first gold group the chunk satisfies, else None."""
    t = hit_text.lower()
    for gi, g in enumerate(gold):
        if hit_meta.get("filename") == g["file"] and all(s.lower() in t for s in g["contains"]):
            return gi
    return None


def evaluate_ranking(rel_groups: list[int | None], n_gold: int, need: str, n_relevant: int = 1, ks=(1, 3, 5, 10)) -> dict:
    """rel_groups[i] = gold-group index satisfied by the hit at rank i+1 (or None)."""
    out = {}
    for k in ks:
        top = rel_groups[:k]
        covered = {g for g in top if g is not None}
        out[f"recall@{k}"] = float(len(covered) == n_gold) if need == "all" else float(bool(covered))
        out[f"coverage@{k}"] = len(covered) / n_gold if n_gold else 0.0
    first = next((i + 1 for i, g in enumerate(rel_groups) if g is not None), None)
    out["rr"] = 1.0 / first if first else 0.0
    dcg = sum(1.0 / math.log2(i + 2) for i, g in enumerate(rel_groups[:5]) if g is not None)
    # binary nDCG: ideal ranking puts every relevant chunk that exists in the index (n_relevant) at the top
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(5, max(1, n_relevant))))
    out["ndcg@5"] = dcg / ideal if ideal else 0.0
    return out


def mean(vals):
    vals = list(vals)
    return sum(vals) / len(vals) if vals else float("nan")


def percentile(vals, p):
    v = sorted(vals)
    if not v:
        return float("nan")
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def calibrate_threshold(ans_scores: list[float], unans_scores: list[float]) -> dict:
    """Pick the top-1 similarity cutoff that maximises balanced accuracy (answerable kept, unanswerable rejected)."""
    cands = sorted(set(ans_scores + unans_scores))
    best = {"threshold": 0.0, "balanced_accuracy": 0.0}
    for t in cands:
        tpr = mean(s >= t for s in ans_scores)
        tnr = mean(s < t for s in unans_scores)
        ba = (tpr + tnr) / 2
        if ba > best["balanced_accuracy"] + 1e-9:
            best = {"threshold": round(t, 4), "balanced_accuracy": round(ba, 4), "answerable_kept": round(tpr, 4),
                    "unanswerable_rejected": round(tnr, 4)}
    return best
