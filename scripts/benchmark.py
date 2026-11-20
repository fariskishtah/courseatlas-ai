"""Measure real performance on this machine -> artifacts/metrics/benchmark.json"""
import json, platform, statistics, subprocess, sys, time
from pathlib import Path
import psutil
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src.embeddings.embedding_service import EmbeddingService
from src.ingestion import extract
from src.ingestion.chunking import chunk_blocks
from src.generation.grounded_qa import GroundedQA
from src.vectorstore.indexing import KnowledgeBase

proc = psutil.Process()
res = {"machine": platform.platform(), "cpu": subprocess.getoutput("sysctl -n machdep.cpu.brand_string"), "ram_gb": psutil.virtual_memory().total / 2**30}
ext = {}
for t in ("pdf", "docx", "csv", "txt"):
    fs = sorted((ROOT / "data/sample_courses").rglob(f"*.{t}"))
    times = []
    for f in fs:
        t0 = time.perf_counter(); extract(f); times.append(time.perf_counter() - t0)
    ext[t] = {"files": len(fs), "mean_ms": statistics.mean(times) * 1000}
res["extraction"] = ext
e = EmbeddingService(); t0 = time.perf_counter(); e.embed(["warmup"]); res["embedding_model_cold_load_s"] = time.perf_counter() - t0
texts = [c["text"] for c in KnowledgeBase(embedder=e).store.get_all()]
t0 = time.perf_counter(); e.embed(texts); dt = time.perf_counter() - t0
res["embedding"] = {"chunks": len(texts), "total_s": dt, "chunks_per_s": len(texts) / dt}
kb = KnowledgeBase(embedder=e); qa = GroundedQA(kb)
qs = ["What is overfitting?", "Why is a mutable default argument a bug?", "What is the empirical rule?", "Which fraud model has the highest F1?", "What is Bayes theorem?"]
cold = qa.answer(qs[0], "ml")
warm_all = [qa.answer(q, c) for q, c in zip(qs, ["ml", "python", "statistics", "ml", "statistics"])]
res["warm_reasons"] = [r["reason"] for r in warm_all]
warm = [r for r in warm_all if "llm_total_s" in r["timings"]]
res["retrieval_ms_warm_mean"] = statistics.mean(r["timings"]["retrieval_ms"] for r in warm)
res["llm_s_warm_mean"] = statistics.mean(r["timings"]["llm_total_s"] for r in warm)
res["end_to_end_s_warm_mean"] = statistics.mean(r["timings"]["end_to_end_s"] for r in warm)
res["end_to_end_s_first_query_after_model_load"] = cold["timings"]["end_to_end_s"]
res["python_process_rss_mb"] = proc.memory_info().rss / 2**20
res["ollama_loaded"] = subprocess.getoutput("ollama ps")
(ROOT / "artifacts/metrics/benchmark.json").write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))
