"""HTML renderers for the UI. Everything is built from real retrieval output / registry data."""
from __future__ import annotations

import datetime
import html
import re


def esc(x) -> str:
    return html.escape(str(x))


def course_cards(summary: list[dict]) -> str:
    cards = []
    for c in summary:
        upd = datetime.datetime.fromtimestamp(c["last_update"]).strftime("%Y-%m-%d %H:%M") if c["last_update"] else "-"
        badge = '<span class="ca-badge ok">indexed</span>' if c["status"] == "indexed" else '<span class="ca-badge warn">empty</span>'
        types = "".join(f'<span class="ca-badge">{esc(t.upper())}</span>' for t in c["types"])
        cards.append(f'<div class="ca-card"><h3>{esc(c.get("icon",""))} {esc(c["name"])}</h3><div class="ca-muted">{esc(c["description"])}</div>'
                     f'<p style="margin:12px 0 4px"><b>{c["documents"]}</b> documents · <b>{c["chunks"]}</b> chunks</p>{types}'
                     f'<div class="ca-muted" style="margin-top:8px">{badge} last update {upd}</div></div>')
    return f'<div class="ca-grid">{"".join(cards)}</div>'


def stat_cards(items: list[tuple[str, str]]) -> str:
    return '<div class="ca-grid">' + "".join(f'<div class="ca-card ca-stat"><b>{esc(v)}</b><span class="ca-muted">{esc(k)}</span></div>' for k, v in items) + "</div>"


def evidence_trail(result: dict, course_names: dict[str, str]) -> str:
    if not result or not result.get("sources"):
        return '<div class="ca-muted">No evidence retrieved for this question.</div>'
    used = set(result.get("used", []))
    out = ['<div class="ca-trail">']
    for s in result["sources"]:
        m = s["meta"]
        cited = s["id"] in used
        path = " &rarr; ".join(esc(x) for x in [course_names.get(m.get("course_id"), m.get("course_id", "")), m.get("doc_title", ""), m.get("location", "")] if x)
        badge = '<span class="ca-badge ok">cited</span>' if cited else '<span class="ca-badge">retrieved</span>'
        out.append(f'<details class="{"ca-cited" if cited else ""}"{" open" if cited and s["id"] == result["used"][0] else ""}><summary>{esc(s["id"])} · {esc(s["label"])} {badge}'
                   f'<span class="ca-muted"> rank {s["rank"]} · similarity {s["score"]:.3f}</span></summary>'
                   f'<div class="ca-path">{path} · {esc(m.get("file_type","").upper())} · chunk {esc(s["chunk_id"])}</div><pre>{esc(s["text"])}</pre></details>')
    out.append("</div>")
    return "".join(out)


def render_answer(result: dict) -> str:
    text = result["answer_clean"]
    text = re.sub(r"\[(S\d+|C1)\]", lambda m: f" **[{m.group(1)}]**", text)
    used = [s for s in result["sources"] if s["id"] in result["used"]]
    tail = ""
    if used:
        tail = "\n\n---\n" + "\n".join(f"- **{s['id']}** {s['label']}" for s in used)
    if result["abstained"]:
        text = "⚠️ " + text
        tail = f"\n\n*Why: {result['reason']}. Closest passages are shown in the Evidence Trail for transparency.*"
    elif result["reason"] == "no_valid_citation":
        tail += "\n\n*⚠️ The model did not attach a verifiable citation to this answer; treat it with caution and check the Evidence Trail.*"
    if result.get("invalid"):
        tail += f"\n\n*Removed unverifiable citation tags: {', '.join(result['invalid'])}.*"
    return text + tail


def hits_table(hits) -> list[list]:
    return [[h.rank, h.chunk_id, round(h.score, 4), h.dense_rank or "-", h.bm25_rank or "-", h.meta.get("doc_title"), h.meta.get("location"),
             h.meta.get("course_id")] for h in hits]


def docs_table(docs: list[dict]) -> list[list]:
    return [[d["doc_id"], d["course_id"], d["filename"], d["file_type"].upper(), d["status"], d["n_chunks"], d["pages"] or "-", d["words"] or 0,
             round(((d["extract_s"] or 0) + (d["embed_s"] or 0) + (d["index_s"] or 0)), 2), (d["error"] or "")[:80]] for d in docs]
