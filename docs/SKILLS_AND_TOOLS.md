# Skills / tooling review

Before implementation the Claude Code environment was inspected. Available skills include generic engineering/testing/debugging skills, document skills (`pdf`, `docx`, `xlsx`, `pptx`), design/visualisation skills and the `superpowers` workflow skills.

- **No third-party skill was installed** and no external scripts were executed. The official `anthropics/skills` repository was the only vetted source considered; nothing in it was needed for this project.
- All implementation uses well-known, maintained libraries with their official documentation: PyMuPDF, python-docx, pandas, sentence-transformers, ChromaDB, rank-bm25, Gradio, Ollama, pytest, reportlab (to generate the demo PDFs).
- The task brief (PPTX, slide 28 *Standard Course Q&A RAG System*) was read directly; Corrective/Agentic RAG (slides 29-30) are intentionally **not** implemented.
