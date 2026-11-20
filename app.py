"""CourseAtlas AI - Gradio application. Every panel is driven by the real RAG backend (no mock data)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import gradio as gr
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.config import get_config, path as cfg_path  # noqa: E402
from src.generation.grounded_qa import GroundedQA  # noqa: E402
from src.generation.llm_client import LLMUnavailable  # noqa: E402
from src.retrieval.filters import InvalidQuestion, resolve_scope, validate_question  # noqa: E402
from src.ui import components as ui  # noqa: E402
from src.ui.theme import CSS, HERO, THEME  # noqa: E402
from src.utils.upload import UploadError, store_upload  # noqa: E402
from src.vectorstore.indexing import KnowledgeBase, dashboard_stats  # noqa: E402

CFG = get_config()
READ_ONLY = CFG["app"]["read_only"]
KB = KnowledgeBase()
QA = GroundedQA(KB)


def bootstrap_index() -> None:
    """Index the bundled demo courses on first start (incremental + idempotent afterwards)."""
    mp = cfg_path("data_dir") / "manifests" / "sources.json"
    manifest = {(m["course_id"], m["filename"]): m for m in json.loads(mp.read_text())} if mp.exists() else {}
    for cid in KB.courses:
        folder = cfg_path("courses_dir") / cid
        if folder.exists() and not any(d["course_id"] == cid for d in KB.store.list_docs(cid)):
            KB.ingest_course_dir(cid, folder, manifest)


bootstrap_index()
COURSE_NAMES = {cid: c["name"] for cid, c in KB.courses.items()}
CHOICES = [(f"{c.get('icon', '')} {c['name']}", cid) for cid, c in KB.courses.items()]
EVAL_DIR = ROOT / "artifacts" / "metrics"


def _json(name: str):
    p = EVAL_DIR / name
    return json.loads(p.read_text()) if p.exists() else None


# ----------------------------------------------------------------------------- Ask
def ask(question, history, course, multi, top_k, mode):
    history = list(history or [])
    try:
        scope = list(KB.courses) if multi else course
        validate_question(question)
        resolve_scope(scope, set(KB.courses), allow_multi=bool(multi))
    except InvalidQuestion as e:
        gr.Warning(str(e))
        yield history, gr.update(), gr.update(), None
        return
    ok, why = QA.llm.available()
    prefix = "\U0001F310 *Cross-course search (explicitly enabled)*\n\n" if multi else ""
    history += [{"role": "user", "content": question}, {"role": "assistant", "content": "Retrieving evidence…"}]
    yield history, gr.update(), gr.update(), None
    try:
        final = None
        for partial, res in QA.answer_stream(question, scope, top_k=int(top_k), retrieval_mode=mode, allow_multi=bool(multi)):
            if res is None:
                history[-1]["content"] = partial
                yield history, gr.update(), gr.update(), None
            else:
                final = res
        history[-1]["content"] = prefix + ui.render_answer(final)
        choices = [s["id"] for s in final["sources"]]
        yield history, ui.evidence_trail(final, COURSE_NAMES), gr.update(choices=choices, value=(final["used"][0] if final["used"] else None)), final
    except LLMUnavailable as e:
        history[-1]["content"] = f"❌ The local language model is not available ({why}). No answer was generated.  \n`{e}`"
        yield history, gr.update(), gr.update(), None
    except Exception as e:  # noqa: BLE001
        history[-1]["content"] = f"❌ Unexpected error: {type(e).__name__}"
        yield history, gr.update(), gr.update(), None


def show_source(sid, result):
    if not result or not sid:
        return "Select a citation to open its source excerpt."
    s = next((x for x in result["sources"] if x["id"] == sid), None)
    if not s:
        return "Unknown source."
    m = s["meta"]
    stored = KB.store.get_chunk(s["chunk_id"]) if not s["chunk_id"].startswith("calc:") else None
    text = stored["text"] if stored else s["text"]       # re-read from the index, not from the answer
    return (f"### {s['label']}\n**Course:** {COURSE_NAMES.get(m.get('course_id'), m.get('course_id'))} · **File:** `{m.get('filename')}` · "
            f"**Location:** {m.get('location')} · **Rank:** {s['rank']} · **Similarity:** {s['score']:.3f}\n\n```\n{text}\n```")


def inspector_run(question, course, multi, k, mode):
    try:
        q = validate_question(question)
        scope = resolve_scope(list(KB.courses) if multi else course, set(KB.courses), bool(multi))
    except InvalidQuestion as e:
        gr.Warning(str(e))
        return None, ""
    r = QA.retriever.search(q, scope, int(k), mode)
    d = r.diagnostics
    info = (f"**Courses searched:** {', '.join(d['courses'])} · **mode:** {d['mode']} · **top-k:** {d['top_k']}  \n"
            f"**Latency:** embed {d['embed_ms']:.1f} ms + search {d['search_ms']:.1f} ms = **{d['total_ms']:.1f} ms**  \n"
            f"**Embedding model:** {KB.embedder.model_id}")
    df = pd.DataFrame(ui.hits_table(r.hits), columns=["rank", "chunk_id", "cosine", "dense_rank", "bm25_rank", "document", "location", "course"])
    return df, info


# ----------------------------------------------------------------------------- Study
def study(topic, course, mode):
    try:
        validate_question(topic)
        resolve_scope(course, set(KB.courses))
    except InvalidQuestion as e:
        gr.Warning(str(e))
        return "", ""
    try:
        res = QA.answer(topic, course, mode=mode)
    except LLMUnavailable as e:
        return f"❌ LLM unavailable: {e}", ""
    note = "\n\n*Generated study material, not official exam content. Verify against the cited sources.*" if mode == "quiz" else ""
    return ui.render_answer(res) + note, ui.evidence_trail(res, COURSE_NAMES)


# ----------------------------------------------------------------------------- Documents
def refresh_docs(course_filter=None):
    docs = KB.store.list_docs(course_filter or None)
    df = pd.DataFrame(ui.docs_table(docs), columns=["doc_id", "course", "file", "type", "status", "chunks", "pages", "words", "ingest_s", "error"])
    return df, gr.update(choices=[(f"{d['filename']} ({d['course_id']})", d["doc_id"]) for d in docs])


def upload(files, course):
    if READ_ONLY:
        return "Uploads are disabled in this read-only deployment."
    if not files:
        return "Choose one or more files."
    msgs = []
    for f in files if isinstance(files, list) else [files]:
        src = Path(f if isinstance(f, str) else f.name)
        try:
            dest, name = store_upload(src, src.name, course)
            r = KB.ingest_file(dest, course, source="user upload", license="user supplied", stored_path=str(dest), filename=name)
            msgs.append(f"**{name}** → {r['status']} ({r.get('n_chunks', 0)} chunks)" + (f" — {r.get('error') or r.get('message', '')}" if r["status"] in ("failed", "duplicate") else ""))
        except UploadError as e:
            msgs.append(f"**{src.name}** → rejected: {e}")
    return "  \n".join(msgs)


def doc_action(doc_id, action):
    if READ_ONLY:
        return "Disabled in read-only mode."
    if not doc_id:
        return "Select a document."
    if action == "Remove":
        return "Removed." if KB.delete_document(doc_id) else "Not found."
    return f"Reindex: {KB.reindex_document(doc_id)['status']}"


# ----------------------------------------------------------------------------- Dashboard / coverage / evaluation
def dashboard():
    s = dashboard_stats(KB)
    info = KB.embedder.info() if KB.embedder._model is not None else {"model_id": KB.embedder.model_id}
    cards = ui.stat_cards([("courses", s["courses"]), ("indexed documents", s["documents"]), ("chunks", s["chunks"]), ("embeddings", s["vectors"]),
                           ("pages (PDF)", s["pages"]), ("words", f"{s['words']:,}"), ("avg ingest s/doc", f"{s['avg_ingest_s']:.2f}"),
                           ("failed docs", s["failed"])])
    fmt = pd.DataFrame({"format": [k.upper() for k in s["formats"]], "documents": list(s["formats"].values())})
    per = pd.DataFrame({"course": [COURSE_NAMES[c] for c in s["per_course"]], "documents": list(s["per_course"].values())})
    meta = (f"**Embedding model:** `{KB.embedder.model_id}` · **Vector DB:** ChromaDB {__import__('chromadb').__version__} (cosine, persistent) · "
            f"**LLM:** `{QA.llm.model}` via Ollama · **Chunking:** {KB.chunk_size}/{KB.chunk_overlap} chars")
    return cards, fmt, per, meta


def coverage(course):
    rows = []
    for c in KB.store.get_all([course]):
        m = c["meta"]
        rows.append((m.get("section") or m.get("location"), m.get("filename")))
    topics: dict[str, set] = {}
    for sec, f in rows:
        topics.setdefault(str(sec), set()).add(f)
    df = pd.DataFrame([{"topic / heading": t, "documents": len(f), "files": ", ".join(sorted(f))} for t, f in sorted(topics.items())])
    ev = _json("retrieval_eval.json")
    txt = "Coverage here means *documents indexed per heading*; it does **not** imply the whole curriculum is covered.\n\n"
    if ev:
        per = ev["configs"].get("chunk900_overlap120_dense", {}).get("per_question", [])
        mine = [p for p in per if p["id"].startswith(course[:2]) and p["recall@5"] < 1]
        qs = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data/eval/questions.jsonl").read_text().splitlines()}
        txt += f"**Retrieval misses at k=5 in the evaluation set for this course ({len(mine)}):**\n" + ("\n".join(f"- {qs[p['id']]['question']} ({qs[p['id']]['category']})" for p in mine) or "- none")
    return df, txt


def evaluation_view():
    r, g = _json("retrieval_eval.json"), _json("generation_eval.json")
    if not r:
        return pd.DataFrame(), "Run `python scripts/evaluate.py retrieval` first.", ""
    rows = []
    for name, c in r["configs"].items():
        o = c["overall"]
        rows.append({"configuration": name, "Recall@1": round(o["recall@1"], 3), "Recall@3": round(o["recall@3"], 3), "Recall@5": round(o["recall@5"], 3),
                     "MRR": round(o["rr"], 3), "nDCG@5": round(o["ndcg@5"], 3), "chunks": c["chunks_in_index"], "latency ms": round(c["latency_ms"]["mean"], 1)})
    iso = r["course_isolation"]
    txt = (f"**Course isolation:** {iso['cross_course_hits_with_filter']} cross-course hits out of {iso['hits_checked']} with the metadata filter "
           f"(vs {iso['cross_course_hits_without_filter']} without it). \n**Abstention threshold (dev-calibrated):** {r['threshold_calibration']['dev']['threshold']}")
    gtxt = ""
    if g:
        s = g["summary"]["rag"]
        b = g["summary"]["no_context_baseline"]
        gtxt = (f"**End-to-end ({g['summary']['n']} questions, `{g['environment']['llm']}`):** keyword-correct on answerable {s['keyword_correct_rate_answerable']:.1%} · "
                f"correct abstention {s['correct_abstention_rate_unanswerable']:.1%} · answers with valid citation {s['answers_with_valid_citation_rate']:.1%} · "
                f"mean latency {s['latency_s_mean']:.1f}s.  \n**No-context baseline:** keyword-correct {b['keyword_correct_rate_answerable']:.1%}, "
                f"abstains on unanswerable {b['abstention_rate_unanswerable']:.1%}, 0% with sources.")
    return pd.DataFrame(rows), txt, gtxt


# ----------------------------------------------------------------------------- Layout
with gr.Blocks(title="CourseAtlas AI", theme=THEME, css=CSS) as demo:
    gr.HTML(HERO)
    result_state = gr.State(None)
    with gr.Row(equal_height=True):
        course = gr.Dropdown(CHOICES, value=CHOICES[0][1], label="Selected course", scale=3, interactive=True)
        multi = gr.Checkbox(False, label="Search ALL courses (cross-course, explicit)", scale=2)
        top_k = gr.Slider(1, 10, value=CFG["retrieval"]["top_k"], step=1, label="Top-k", scale=2)
        rmode = gr.Radio(["dense", "hybrid"], value=CFG["retrieval"]["mode"], label="Retrieval", scale=2)

    with gr.Tabs():
        with gr.Tab("Course Library"):
            lib = gr.HTML()
            gr.Markdown("Pick a course above, then open **Ask**. Each course has its own documents; search never crosses course boundaries unless you tick the cross-course box.")
        with gr.Tab("Ask"):
            with gr.Row():
                with gr.Column(scale=5):
                    chat = gr.Chatbot(type="messages", height=430, label="Course Q&A", show_copy_button=True)
                    q = gr.Textbox(placeholder="Ask a question about the selected course…", show_label=False, lines=1)
                    with gr.Row():
                        send = gr.Button("Ask", variant="primary")
                        clear = gr.Button("Clear")
                    gr.Examples(["What is overfitting?", "What is the difference between population variance and sample variance?",
                                 "Why is a mutable default argument a bug?", "What is the average salary of a Python engineer in Egypt?"], inputs=q, label="Try")
                with gr.Column(scale=4):
                    gr.Markdown("#### Evidence Trail")
                    trail = gr.HTML('<div class="ca-muted">Evidence appears here after you ask a question. Expand a card to read the exact retrieved passage.</div>')
                    cite_pick = gr.Dropdown([], label="Open a citation (source viewer)", interactive=True)
                    viewer = gr.Markdown("Select a citation to open its source excerpt.")
            ask_in = [q, chat, course, multi, top_k, rmode]
            ask_out = [chat, trail, cite_pick, result_state]
            send.click(ask, ask_in, ask_out).then(lambda: "", None, q)
            q.submit(ask, ask_in, ask_out).then(lambda: "", None, q)
            clear.click(lambda: ([], '<div class="ca-muted">Cleared.</div>', gr.update(choices=[], value=None), None), None, [chat, trail, cite_pick, result_state])
            cite_pick.change(show_source, [cite_pick, result_state], viewer)
        with gr.Tab("Retrieval Inspector"):
            gr.Markdown("Run retrieval only (no LLM) and inspect ranks, scores and latency.")
            iq = gr.Textbox(label="Query")
            ibtn = gr.Button("Retrieve", variant="primary")
            iinfo = gr.Markdown()
            itab = gr.Dataframe(interactive=False, wrap=True)
            ibtn.click(inspector_run, [iq, course, multi, top_k, rmode], [itab, iinfo])
        with gr.Tab("Study Mode"):
            gr.Markdown("Grounded study helpers: they use the same retrieval + citation pipeline.")
            smode = gr.Radio(["summarize", "explain", "compare", "quiz"], value="summarize", label="Mode")
            stopic = gr.Textbox(label="Topic or request", placeholder="e.g. overfitting and how to reduce it")
            sbtn = gr.Button("Generate", variant="primary")
            sout = gr.Markdown()
            strail = gr.HTML()
            sbtn.click(study, [stopic, course, smode], [sout, strail])
        with gr.Tab("Documents"):
            gr.Markdown("Uploads are validated (type, size, content) and stored privately." + (" **Read-only deployment: uploads disabled.**" if READ_ONLY else ""))
            with gr.Row():
                up = gr.File(file_count="multiple", file_types=[".pdf", ".docx", ".csv", ".txt"], label="Upload PDF / DOCX / CSV / TXT", interactive=not READ_ONLY)
                with gr.Column():
                    up_btn = gr.Button("Ingest into selected course", variant="primary", interactive=not READ_ONLY)
                    up_msg = gr.Markdown()
            doc_df = gr.Dataframe(interactive=False, wrap=True, label="Indexed documents")
            with gr.Row():
                doc_pick = gr.Dropdown([], label="Document")
                re_btn = gr.Button("Reindex", interactive=not READ_ONLY)
                rm_btn = gr.Button("Remove", variant="stop", interactive=not READ_ONLY)
            doc_msg = gr.Markdown()
            up_btn.click(upload, [up, course], up_msg).then(refresh_docs, None, [doc_df, doc_pick])
            re_btn.click(lambda d: doc_action(d, "Reindex"), doc_pick, doc_msg).then(refresh_docs, None, [doc_df, doc_pick])
            rm_btn.click(lambda d: doc_action(d, "Remove"), doc_pick, doc_msg).then(refresh_docs, None, [doc_df, doc_pick])
        with gr.Tab("Dashboard"):
            dcards = gr.HTML()
            with gr.Row():
                dfmt = gr.BarPlot(x="format", y="documents", title="Document format distribution", height=280)
                dper = gr.BarPlot(x="course", y="documents", title="Documents per course", height=280)
            dmeta = gr.Markdown()
        with gr.Tab("Coverage"):
            cov_btn = gr.Button("Compute coverage for selected course")
            cov_note = gr.Markdown()
            cov_df = gr.Dataframe(interactive=False, wrap=True)
            cov_btn.click(coverage, course, [cov_df, cov_note])
        with gr.Tab("Evaluation"):
            ev_df = gr.Dataframe(interactive=False)
            ev_txt = gr.Markdown()
            ev_gen = gr.Markdown()
            ev_btn = gr.Button("Load results")
            ev_btn.click(evaluation_view, None, [ev_df, ev_txt, ev_gen])

    def on_load():
        d = dashboard()
        df, pick = refresh_docs()
        return (ui.course_cards(KB.course_summary()), d[0], d[1], d[2], d[3], df, pick)
    demo.load(on_load, None, [lib, dcards, dfmt, dper, dmeta, doc_df, doc_pick])

if __name__ == "__main__":
    port = int(os.getenv("PORT", "7860"))
    demo.queue(default_concurrency_limit=1).launch(server_name=os.getenv("HOST", "127.0.0.1"), server_port=port)
