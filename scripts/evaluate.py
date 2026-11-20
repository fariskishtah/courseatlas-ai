"""Evaluation harness. Writes JSON to artifacts/metrics/.

  python scripts/evaluate.py retrieval     # chunk-size / top-k / hybrid experiments, course isolation, threshold calibration
  python scripts/evaluate.py generation    # end-to-end answers with the local LLM + no-context baseline
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import get_config  # noqa: E402
from src.evaluation import answer_metrics as AM  # noqa: E402
from src.evaluation import retrieval_metrics as RM  # noqa: E402
from src.retrieval.retriever import Retriever  # noqa: E402
from src.vectorstore.indexing import KnowledgeBase  # noqa: E402

OUT = ROOT / "artifacts" / "metrics"
OUT.mkdir(parents=True, exist_ok=True)


def load_questions() -> list[dict]:
    return [json.loads(l) for l in (ROOT / "data" / "eval" / "questions.jsonl").read_text().splitlines() if l.strip()]


def kb_for(size: int, overlap: int) -> KnowledgeBase:
    d = ROOT / "data" / "index_exp" / f"c{size}_o{overlap}"
    kb = KnowledgeBase(index_dir=d, chunk_size=size, chunk_overlap=overlap)
    manifest = {(m["course_id"], m["filename"]): m for m in json.loads((ROOT / "data/manifests/sources.json").read_text())}
    for cid in kb.courses:
        kb.ingest_course_dir(cid, ROOT / "data" / "sample_courses" / cid, manifest)
    return kb


def run_config(kb: KnowledgeBase, qs: list[dict], mode: str, k: int = 10) -> dict:
    ret = Retriever(kb)
    per, lat, top1 = [], [], {}
    for q in qs:
        r = ret.search(q["question"], [q["course_id"]], k=k, mode=mode)
        lat.append(r.diagnostics["total_ms"])
        top1[q["id"]] = r.hits[0].score if r.hits else 0.0
        if q["answerable"] and q["gold"]:
            rel = [RM.is_relevant(h.meta, h.text, q["gold"]) for h in r.hits]
            n_rel = sum(RM.is_relevant(c["meta"], c["text"], q["gold"]) is not None for c in kb.store.get_all([q["course_id"]]))
            n_groups = len(q["gold"]) if q["need"] == "all" else 1
            m = RM.evaluate_ranking(rel, n_groups, q["need"], n_relevant=n_rel)
            per.append({"id": q["id"], "category": q["category"], "split": q["split"], **m})
    keys = [k_ for k_ in per[0] if k_ not in ("id", "category", "split")]
    agg = {k_: RM.mean(p[k_] for p in per) for k_ in keys}
    by_cat = defaultdict(list)
    for p in per:
        by_cat[p["category"]].append(p)
    return {"n_questions": len(per), "overall": agg,
            "by_category": {c: {"n": len(v), "recall@5": RM.mean(x["recall@5"] for x in v), "mrr": RM.mean(x["rr"] for x in v)} for c, v in by_cat.items()},
            "latency_ms": {"mean": RM.mean(lat), "p95": RM.percentile(lat, 95)}, "top1": top1, "per_question": per}


def retrieval() -> None:
    qs = load_questions()
    res = {"environment": env_info(), "configs": {}}
    base_kb = None
    for size, ov in [(500, 80), (900, 120), (1500, 200)]:
        t = time.perf_counter()
        kb = kb_for(size, ov)
        build = time.perf_counter() - t
        if (size, ov) == (900, 120):
            base_kb = kb
        for mode in ("dense", "hybrid") if (size, ov) == (900, 120) else ("dense",):
            name = f"chunk{size}_overlap{ov}_{mode}"
            r = run_config(kb, qs, mode)
            r["chunks_in_index"] = kb.store.count()
            r["index_build_s_incl_cached"] = build
            res["configs"][name] = r
            o = r["overall"]
            print(f"{name:<28} R@1={o['recall@1']:.3f} R@3={o['recall@3']:.3f} R@5={o['recall@5']:.3f} R@10={o['recall@10']:.3f} "
                  f"MRR={o['rr']:.3f} nDCG@5={o['ndcg@5']:.3f} lat={r['latency_ms']['mean']:.0f}ms chunks={r['chunks_in_index']}")
    # ---- threshold calibration on DEV, reported on TEST (baseline config)
    top1 = res["configs"]["chunk900_overlap120_dense"]["top1"]
    dev = [q for q in qs if q["split"] == "dev"]
    test = [q for q in qs if q["split"] == "test"]
    cal = RM.calibrate_threshold([top1[q["id"]] for q in dev if q["answerable"]], [top1[q["id"]] for q in dev if not q["answerable"]])
    t = cal["threshold"]
    rep = {"calibrated_on": "dev", "dev": cal,
           "test": {"answerable_kept": RM.mean(top1[q["id"]] >= t for q in test if q["answerable"]),
                    "unanswerable_rejected": RM.mean(top1[q["id"]] < t for q in test if not q["answerable"])},
           "score_stats": {"answerable_mean": RM.mean(top1[q["id"]] for q in qs if q["answerable"]),
                           "unanswerable_mean": RM.mean(top1[q["id"]] for q in qs if not q["answerable"])}}
    res["threshold_calibration"] = rep
    print("threshold:", rep)
    # ---- course isolation
    ret = Retriever(base_kb)
    leaks, leaks_unfiltered, total = 0, 0, 0
    for q in qs:
        scoped = ret.search(q["question"], [q["course_id"]], k=5)
        leaks += sum(h.meta["course_id"] != q["course_id"] for h in scoped.hits)
        allc = ret.search(q["question"], list(base_kb.courses), k=5)
        leaks_unfiltered += sum(h.meta["course_id"] != q["course_id"] for h in allc.hits)
        total += len(scoped.hits)
    res["course_isolation"] = {"questions": len(qs), "hits_checked": total, "cross_course_hits_with_filter": leaks,
                               "cross_course_hits_without_filter": leaks_unfiltered}
    print("isolation:", res["course_isolation"])
    for c in res["configs"].values():
        c.pop("top1", None)
    (OUT / "retrieval_eval.json").write_text(json.dumps(res, indent=2))
    # persist the calibrated threshold into the retrieval config
    p = ROOT / "configs" / "retrieval.yaml"
    cfg = yaml.safe_load(p.read_text())
    cfg["retrieval"]["min_score"] = round(t, 4)
    p.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print("wrote min_score", t)


def env_info() -> dict:
    import platform
    import chromadb, sentence_transformers, torch
    import requests
    llm = get_config()["llm"]["model"]
    ver = requests.get(get_config()["llm"]["base_url"] + "/api/version", timeout=3).json().get("version")
    return {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(),
            "chromadb": chromadb.__version__, "sentence_transformers": sentence_transformers.__version__, "torch": torch.__version__,
            "ollama": ver, "llm": llm, "embedding": get_config()["embedding"]["model_id"]}


def generation() -> None:
    from src.generation.grounded_qa import GroundedQA, no_context_answer
    qs = load_questions()
    kb = KnowledgeBase()
    qa = GroundedQA(kb)
    rows = []
    for i, q in enumerate(qs, 1):
        r = qa.answer(q["question"], q["course_id"])
        base_text, bm = no_context_answer(qa.llm, q["question"])
        rows.append({"id": q["id"], "category": q["category"], "answerable": q["answerable"], "split": q["split"], "question": q["question"],
                     "answer": r["answer_clean"], "used": r["used"], "invalid": r["invalid"], "abstained": r["abstained"] or AM.looks_like_abstention(r["answer_clean"]),
                     "reason": r["reason"], "top_score": r["retrieval"].get("top_score"),
                     "kw_correct": AM.keyword_correct(r["answer_clean"], q["criteria"]) if q["answerable"] else None,
                     "cite_relevant": AM.citation_relevant(r, q["gold"]) if q["answerable"] and r["used"] else None,
                     "latency_s": r["timings"].get("end_to_end_s"), "retrieval_ms": r["timings"].get("retrieval_ms"),
                     "llm_s": r["timings"].get("llm_total_s"), "tokens": r["timings"].get("output_tokens"),
                     "baseline_answer": base_text, "baseline_abstained": AM.looks_like_abstention(base_text),
                     "baseline_kw_correct": AM.keyword_correct(base_text, q["criteria"]) if q["answerable"] else None,
                     "baseline_s": bm["llm_total_s"], "retrieved_labels": [s["label"] for s in r["sources"]]})
        print(f"[{i}/{len(qs)}] {q['id']} abst={rows[-1]['abstained']} kw={rows[-1]['kw_correct']} {rows[-1]['latency_s']:.1f}s", flush=True)
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    non_abs = [r for r in rows if not r["abstained"]]
    summ = {
        "n": len(rows), "answerable": len(ans), "unanswerable": len(unans),
        "rag": {"keyword_correct_rate_answerable": RM.mean(r["kw_correct"] for r in ans),
                "false_abstention_rate_answerable": RM.mean(r["abstained"] for r in ans),
                "correct_abstention_rate_unanswerable": RM.mean(r["abstained"] for r in unans),
                "answers_with_valid_citation_rate": RM.mean(bool(r["used"]) for r in non_abs),
                "invalid_citation_tags_total": sum(len(r["invalid"]) for r in rows),
                "citation_relevance_rate": RM.mean(r["cite_relevant"] for r in ans if r["cite_relevant"] is not None),
                "latency_s_mean": RM.mean(r["latency_s"] for r in rows), "latency_s_p95": RM.percentile([r["latency_s"] for r in rows], 95)},
        "no_context_baseline": {"keyword_correct_rate_answerable": RM.mean(r["baseline_kw_correct"] for r in ans),
                                "abstention_rate_unanswerable": RM.mean(r["baseline_abstained"] for r in unans),
                                "answers_with_sources": 0.0, "latency_s_mean": RM.mean(r["baseline_s"] for r in rows)},
        "by_split": {s: {"keyword_correct": RM.mean(r["kw_correct"] for r in ans if r["split"] == s),
                         "correct_abstention": RM.mean(r["abstained"] for r in unans if r["split"] == s)} for s in ("dev", "test")},
    }
    (OUT / "generation_eval.json").write_text(json.dumps({"environment": env_info(), "summary": summ, "rows": rows}, indent=2))
    print(json.dumps(summ, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["retrieval", "generation"])
    a = ap.parse_args()
    {"retrieval": retrieval, "generation": generation}[a.stage]()
