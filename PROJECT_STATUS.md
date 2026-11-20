# PROJECT STATUS — CourseAtlas AI

**Assignment (Standard Course Q&A RAG System): COMPLETE.**  **Public release: PARTIAL** (GitHub published; no live online demo).

## Done
- 3 courses × (PDF, DOCX, CSV, TXT) = 12 files, 128 chunks, 128 embeddings (see docs/DATA_SOURCE_AUDIT.md).
- Ingestion, cleaning, structure-aware chunking with provenance; MiniLM-L6-v2 (384-d) → ChromaDB 1.5.9 (cosine, persistent); course-filtered dense retrieval (hybrid implemented, not default).
- Local LLM `qwen2.5:3b-instruct` via Ollama 0.40.14; grounded prompt, validated citations, abstention, deterministic CSV aggregates.
- Gradio app with 8 tabs, verified in a real browser (desktop + mobile screenshots in `artifacts/screenshots`).
- Evaluation: 60 hand-labelled questions, retrieval experiments (chunk size, top-k, hybrid), course isolation, threshold calibration, RAG vs no-context, benchmarks → `docs/EVALUATION.md`.
- Tests: **52 passed, 0 failed, 0 skipped** (`pytest`), including real-model acceptance tests A–J.

## Not done / blockers (honest)
- **No live public demo.** A free hosted CPU Space cannot run the Ollama LLM this project is built on, and a static page would not be real RAG. Not attempted; no Hugging Face Space was created.
- Not covered: human grading beyond 13 reviewed answers; OCR; authentication; per-user upload sessions (so uploads must stay local / read-only demos only).
- Known weaknesses: 5/46 false abstentions (gate threshold), a misleading answer on a vague question (`st-040`), cross-document misses at small k.
- LinkedIn 1080×1350 crops were not produced; screenshots are full-page PNGs.

## Resume
```bash
source .venv/bin/activate && ollama serve   # if not running
python scripts/build_index.py && python app.py
pytest
```
