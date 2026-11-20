# Security model & limitations

CourseAtlas AI is a question-answering app, **not** an agent: the LLM has no tools, no shell, no file access and no network access. Its only input is text; its only output is text.

| Threat | Mitigation | Verified by |
|---|---|---|
| Prompt injection inside documents | Retrieved text is wrapped in `<<<SOURCE …>>>` delimiters, declared untrusted in the system prompt; the model cannot act on it anyway (no tools). The demo corpus *contains* deliberate injection lines ("IGNORE ALL PREVIOUS INSTRUCTIONS…"). | `test_prompt_injection_stays_inside_untrusted_delimiters`, integration test G |
| Course leakage | Course scope is a **metadata filter in the vector query**, not a prompt instruction; multi-course search must be switched on explicitly. | `test_course_filter_isolation`; evaluation: 0 cross-course hits in 300 checked hits |
| Fake citations | Citation ids (`S1…`) are generated from retrieval metadata; any tag not in the retrieved set is stripped; the source viewer re-reads the chunk from the index. | `test_validator_removes_invented_ids`, integration test J |
| Malicious uploads | Extension allow-list, magic-byte check (PDF header, DOCX zip structure), 10 MB limit, zip-expansion guard, macro (`vbaProject`) rejection, NUL-byte rejection for text, filename sanitisation (basename only, safe charset), destination must resolve inside `data/uploads/<course>/`. Documents are only *parsed* (PyMuPDF / python-docx / pandas); nothing inside them is executed. | `tests/test_citations_filters_upload.py` |
| Resource exhaustion | Size limits, question length limit (1000 chars), bounded context (5000 chars), one concurrent generation. | tests |
| Public data exposure | `COURSEATLAS_READ_ONLY=1` disables upload/delete/reindex. Uploaded files are stored in `data/uploads/` (git-ignored) and never published. Server paths are not shown in the UI. | manual |
| Secrets | None needed. No API keys exist in the repo or history (scanned before publication). | `docs/RELEASE_AUDIT.md` |

## Known limitations
- Small local models (3B) can still paraphrase imperfectly or cite a nearby-but-not-ideal source; citation *validity* (the id exists) is enforced, citation *sufficiency* is not provable automatically.
- There is no user authentication or per-user session storage: **do not deploy the writable mode on the public internet.**
- Scanned PDFs are reported as having no text; OCR is deliberately not applied.
- Uploaded documents are treated as untrusted *data*, but a poisoned document can still cause a wrong (cited) answer. Citations let a human verify.
