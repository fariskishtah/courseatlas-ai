"""Standard RAG: question -> course-filtered retrieval -> bounded context -> grounded LLM answer -> validated citations."""
from __future__ import annotations

import re
import time

from ..citations.provenance import Source, build_sources, citation_label
from ..citations.validator import validate_citations
from ..config import get_config
from ..retrieval import csv_calc
from ..retrieval.filters import InvalidQuestion, resolve_scope, validate_question
from ..retrieval.retriever import Retriever
from ..vectorstore.indexing import KnowledgeBase
from .llm_client import LLMUnavailable, OllamaClient
from .prompts import ABSTAIN, build_messages

_ABSTAIN_RE = re.compile(r"do(es)? not contain enough information|not enough (information|evidence)|cannot be answered from", re.I)


def _src_dict(s: Source) -> dict:
    return {"id": s.sid, "chunk_id": s.chunk_id, "label": s.label, "text": s.text, "meta": s.meta, "rank": s.rank, "score": s.score}


class GroundedQA:
    def __init__(self, kb: KnowledgeBase, llm: OllamaClient | None = None):
        self.kb = kb
        self.retriever = Retriever(kb)
        self.llm = llm or OllamaClient()

    # ------------------------------------------------------------------
    def prepare(self, question: str, course, *, mode: str = "qa", top_k: int | None = None, retrieval_mode: str | None = None,
                allow_multi: bool = False) -> dict:
        """Validation + retrieval + gating. Returns a dict with either a final result or messages for the LLM."""
        cfg = get_config()["retrieval"]
        q = validate_question(question)
        scope = resolve_scope(course, set(self.kb.courses), allow_multi)
        # narrow deterministic CSV calculations (qa mode only)
        if mode == "qa":
            csvs = [d for c in scope for d in self.kb.store.list_docs(c) if d["file_type"] == "csv" and d["status"] == "indexed"]
            calc = csv_calc.try_answer(q, csvs)
            if calc:
                d = calc["doc"]
                label = f"[{d['doc_title']} — computed over {calc['rows']} rows]"
                src = {"id": "C1", "chunk_id": f"calc:{d['doc_id']}", "label": label, "rank": 0, "score": 1.0,
                       "text": f"Method: {calc['method']}. Columns: {', '.join(calc['columns'])}. Values: {calc['values']}",
                       "meta": {"doc_title": d["doc_title"], "filename": d["filename"], "file_type": "csv", "location": "computed",
                                "course_id": d["course_id"]}}
                return {"final": {"question": q, "courses": scope, "answer": calc["answer_text"] + " [C1]", "answer_clean": calc["answer_text"],
                                  "sources": [src], "used": ["C1"], "invalid": [], "abstained": False, "reason": "deterministic_csv_calculation",
                                  "retrieval": {"query": q, "courses": scope, "top_k": 0, "mode": "csv_calc", "total_ms": 0, "chunk_ids": []},
                                  "timings": {}, "mode": mode}}
        ret = self.retriever.search(q, scope, top_k, retrieval_mode)
        base = {"question": q, "courses": scope, "retrieval": ret.diagnostics, "mode": mode}
        if not ret.hits:
            return {"final": {**base, "answer": ABSTAIN, "answer_clean": ABSTAIN, "sources": [], "used": [], "invalid": [],
                              "abstained": True, "reason": "no_documents_in_scope", "timings": {}}}
        top = ret.hits[0].score
        base["retrieval"]["top_score"] = top
        if top < cfg["min_score"]:
            srcs = [_src_dict(s) for s in build_sources(ret.hits, cfg["max_context_chars"])]
            return {"final": {**base, "answer": ABSTAIN, "answer_clean": ABSTAIN, "sources": srcs, "used": [], "invalid": [],
                              "abstained": True, "reason": f"top_similarity_{top:.3f}_below_threshold_{cfg['min_score']}", "timings": {}}}
        sources = build_sources(ret.hits, cfg["max_context_chars"])
        return {"messages": build_messages(q, sources, mode), "sources": sources, "base": base}

    def finish(self, prep: dict, raw: str, metrics: dict | None, t_start: float) -> dict:
        sources: list[Source] = prep["sources"]
        v = validate_citations(raw, {s.sid for s in sources})
        abstained = bool(_ABSTAIN_RE.search(raw))
        reason = "model_abstained" if abstained else ("ok" if v["has_valid"] else "no_valid_citation")
        return {**prep["base"], "answer": raw, "answer_clean": v["text"], "sources": [_src_dict(s) for s in sources],
                "used": v["used"], "invalid": v["invalid"], "abstained": abstained, "reason": reason,
                "timings": {**(metrics or {}), "retrieval_ms": prep["base"]["retrieval"]["total_ms"],
                            "end_to_end_s": time.perf_counter() - t_start}}

    def answer(self, question: str, course, **kw) -> dict:
        t0 = time.perf_counter()
        prep = self.prepare(question, course, **kw)
        if "final" in prep:
            prep["final"]["timings"]["end_to_end_s"] = time.perf_counter() - t0
            return prep["final"]
        raw, metrics = self.llm.chat(prep["messages"])
        return self.finish(prep, raw, metrics, t0)

    def answer_stream(self, question: str, course, **kw):
        """Yields (partial_text, final_result_or_None)."""
        t0 = time.perf_counter()
        prep = self.prepare(question, course, **kw)
        if "final" in prep:
            prep["final"]["timings"]["end_to_end_s"] = time.perf_counter() - t0
            yield prep["final"]["answer"], prep["final"]
            return
        for text, metrics in self.llm.chat(prep["messages"], stream=True):
            if metrics is not None:
                yield text, self.finish(prep, text, metrics, t0)
            else:
                yield text, None


def no_context_answer(llm: OllamaClient, question: str) -> tuple[str, dict]:
    """Baseline for the RAG-vs-no-context experiment (never shown as authoritative)."""
    return llm.chat([{"role": "system", "content": "Answer briefly."}, {"role": "user", "content": question}])
