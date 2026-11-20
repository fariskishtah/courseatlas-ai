# Architecture

```
 USER QUESTION ─► validate ─► course scope (explicit) ─► query embedding (MiniLM, 384-d, L2-normalised)
      ─► ChromaDB cosine search  WHERE course_id ∈ scope  ─► top-k chunks (+ optional BM25/RRF)
      ─► similarity gate (dev-calibrated) ─► bounded context with ids S1..Sn
      ─► local LLM (Ollama) with grounded system prompt ─► citation validator ─► answer + Evidence Trail
```

Deterministic side path: narrow CSV aggregates (mean/sum/min/max/count of one numeric column, only when the question names the CSV/column) are computed with pandas and cited as `[C1]`; the LLM never does arithmetic.

## Decisions
| Decision | Choice | Why |
|---|---|---|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0, 384-d, ~90 MB, CPU) | Small, fast on an 8 GB M2, good retrieval for English technical text. |
| Vector DB | ChromaDB (persistent, cosine HNSW) | Native metadata filtering (`course_id`), local persistence, zero cost. A SQLite registry stores document lifecycle metadata. |
| LLM | Ollama `qwen2.5:3b-instruct` (Q4) | Fits 8 GB, follows citation/abstention instructions well. See LICENSES.md for the model licence caveat. |
| Chunking | Structure-aware packing, 900/120 chars | Beat 500/80 and 1500/200 in our evaluation; never crosses page/section boundaries; CSV rows atomic. |
| Retrieval | Dense only | Hybrid (BM25 + RRF) gave no measurable gain on our set, so the simpler Standard-RAG design is kept. |
| Abstention | Similarity gate calibrated on dev questions + model refusal phrase | Gate saves an LLM call; model handles the grey zone. |
| History | Display only | Each question retrieves independently, so earlier turns cannot leak evidence. |

## Module map
`src/ingestion` (loaders, cleaning, chunking) · `src/embeddings` · `src/vectorstore` (Chroma store, registry, lifecycle) · `src/retrieval` (filters, dense/hybrid retriever, CSV calc) · `src/generation` (Ollama client, prompts, grounded QA) · `src/citations` (provenance, validator) · `src/evaluation` (metrics) · `src/ui` (theme, renderers) · `app.py` (Gradio).
