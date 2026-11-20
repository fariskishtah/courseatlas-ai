"""Build (or incrementally update) the persistent index from data/sample_courses.

Usage: python scripts/build_index.py [--rebuild] [--chunk-size N --chunk-overlap N --index-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import path  # noqa: E402
from src.vectorstore.indexing import KnowledgeBase  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--chunk-size", type=int)
    ap.add_argument("--chunk-overlap", type=int)
    ap.add_argument("--index-dir", type=Path)
    a = ap.parse_args()
    kb = KnowledgeBase(index_dir=a.index_dir, chunk_size=a.chunk_size, chunk_overlap=a.chunk_overlap)
    if a.rebuild:
        kb.store.reset()
    manifest = {(m["course_id"], m["filename"]): m for m in json.loads((path("data_dir") / "manifests" / "sources.json").read_text())}
    t = time.perf_counter()
    results = []
    for cid in kb.courses:
        results += kb.ingest_course_dir(cid, path("courses_dir") / cid, manifest)
    for r in results:
        print(f"{r['status']:<18} {r['filename']:<38} chunks={r.get('n_chunks')}")
    print(f"vectors in index: {kb.store.count()}  |  {time.perf_counter() - t:.1f}s  |  embedder: {kb.embedder.info()}")


if __name__ == "__main__":
    main()
