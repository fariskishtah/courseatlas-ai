"""Semantic retrieval (dense) with optional BM25 hybrid fusion. Always filtered by course metadata."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

from ..config import get_config
from ..vectorstore.indexing import KnowledgeBase

_TOK = re.compile(r"[A-Za-z0-9_]+")


def tokenize(t: str) -> list[str]:
    return [w.lower() for w in _TOK.findall(t)]


@dataclass
class Hit:
    rank: int
    chunk_id: str
    score: float                  # cosine similarity of the dense retriever (0 when only lexical)
    text: str
    meta: dict
    dense_rank: int | None = None
    bm25_rank: int | None = None
    fused_score: float | None = None


@dataclass
class Retrieval:
    hits: list[Hit]
    diagnostics: dict = field(default_factory=dict)


class Retriever:
    def __init__(self, kb: KnowledgeBase):
        self.kb = kb
        self._bm25: dict = {}

    def _bm25_index(self, course_ids: list[str]):
        key = (tuple(sorted(course_ids)), self.kb.store.count())
        if key not in self._bm25:
            docs = self.kb.store.get_all(course_ids)
            self._bm25 = {key: (BM25Okapi([tokenize(d["text"]) for d in docs]) if docs else None, docs)}
        return self._bm25[key]

    def search(self, question: str, course_ids: list[str], k: int | None = None, mode: str | None = None) -> Retrieval:
        cfg = get_config()["retrieval"]
        k = k or cfg["top_k"]
        mode = mode or cfg["mode"]
        t0 = time.perf_counter()
        qv = self.kb.embedder.embed([question])[0]
        t1 = time.perf_counter()
        pool = max(k, 20) if mode == "hybrid" else k
        dense = self.kb.store.query(qv, pool, course_ids)
        t2 = time.perf_counter()
        hits: list[Hit] = []
        if mode == "hybrid":
            bm, docs = self._bm25_index(course_ids)
            lex = []
            if bm is not None:
                scores = bm.get_scores(tokenize(question))
                order = sorted(range(len(docs)), key=lambda i: -scores[i])[:pool]
                lex = [(docs[i], scores[i]) for i in order if scores[i] > 0]
            fused: dict[str, dict] = {}
            for r, d in enumerate(dense, 1):
                e = fused.setdefault(d["chunk_id"], {"d": d, "dense": None, "bm25": None, "rrf": 0.0})
                e["dense"] = r
                e["rrf"] += 1 / (60 + r)
            for r, (d, _) in enumerate(lex, 1):
                e = fused.setdefault(d["chunk_id"], {"d": {**d, "score": 0.0}, "dense": None, "bm25": None, "rrf": 0.0})
                e["bm25"] = r
                e["rrf"] += 1 / (60 + r)
            for rank, e in enumerate(sorted(fused.values(), key=lambda x: -x["rrf"])[:k], 1):
                d = e["d"]
                score = d["score"] if e["dense"] else self._dense_score(qv, d["chunk_id"])
                hits.append(Hit(rank, d["chunk_id"], score, d["text"], d["meta"], e["dense"], e["bm25"], e["rrf"]))
        else:
            for r, d in enumerate(dense, 1):
                hits.append(Hit(r, d["chunk_id"], d["score"], d["text"], d["meta"], dense_rank=r))
        t3 = time.perf_counter()
        return Retrieval(hits, {"query": question, "courses": course_ids, "top_k": k, "mode": mode,
                                "embed_ms": (t1 - t0) * 1000, "search_ms": (t2 - t1) * 1000,
                                "total_ms": (t3 - t0) * 1000, "chunk_ids": [h.chunk_id for h in hits]})

    def _dense_score(self, qv, chunk_id: str) -> float:
        got = self.kb.store.col.get(ids=[chunk_id], include=["embeddings"])
        try:
            return float(qv @ got["embeddings"][0])
        except Exception:
            return 0.0
