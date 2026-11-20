# Release audit (performed before publication)

| Check | Result |
|---|---|
| Secrets scan of working tree (API-key / token / private-key / password patterns) | none found |
| Local absolute paths in tracked files | none found |
| `.env` files | only `.env.example` (no secrets); `.env*` git-ignored |
| Git history | fresh repository, single initial history; scanned before push |
| Course material redistribution | all demo files are original content by the project owner (CC BY 4.0); no third-party text |
| Model licences | models are not redistributed; MiniLM Apache-2.0; Qwen2.5-3B is non-commercial (documented), PyMuPDF AGPL (documented) — see LICENSES.md |
| User uploads / indexes / caches | `data/uploads`, `data/index`, `data/index_exp` git-ignored; not published |
| Dependency licence review | Gradio, ChromaDB, sentence-transformers, pandas, python-docx, rank-bm25, reportlab: permissive; PyMuPDF AGPL flagged |
| Upload & injection hardening | covered by automated tests (see SECURITY.md) |

Not audited: no external penetration test; no authentication layer exists, so the writable mode must not be exposed publicly.
