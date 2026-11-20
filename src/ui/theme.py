import gradio as gr

THEME = gr.themes.Base(primary_hue=gr.themes.colors.indigo, secondary_hue=gr.themes.colors.violet,
                       neutral_hue=gr.themes.colors.slate, radius_size=gr.themes.sizes.radius_lg,
                       font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"])

CSS = """
:root { --ca-navy:#0b1437; --ca-blue:#3b5bff; --ca-violet:#7c5cff; --ca-muted:#64748b; }
.gradio-container { max-width: 1240px !important; margin: auto; }
.ca-hero { background: linear-gradient(120deg,#0b1437 0%,#1b2a73 55%,#5b3df5 100%); border-radius: 20px; padding: 30px 34px; color:#fff; margin-bottom:14px; }
.ca-hero h1 { font-size: 2.1rem; margin:0; letter-spacing:-0.02em; color:#fff; }
.ca-hero p { margin:6px 0 0; color:#c9d3ff; font-size:1.02rem; }
.ca-pill { display:inline-block; background:rgba(255,255,255,.14); border-radius:999px; padding:3px 12px; font-size:.78rem; margin:12px 6px 0 0; color:#e6ebff; }
.ca-grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(260px,1fr)); gap:16px; }
.ca-card { border:1px solid #e2e8f0; border-radius:16px; padding:18px 20px; background:var(--background-fill-primary,#fff); box-shadow:0 1px 2px rgba(15,23,42,.05); transition: transform .15s, box-shadow .15s; }
.ca-card:hover { transform: translateY(-2px); box-shadow:0 8px 20px rgba(59,91,255,.12); }
.ca-card h3 { margin:0 0 4px; font-size:1.1rem; }
.ca-muted { color:var(--ca-muted); font-size:.86rem; }
.ca-badge { display:inline-block; border-radius:8px; padding:2px 9px; font-size:.74rem; margin:2px 4px 2px 0; background:#eef2ff; color:#3730a3; font-weight:600; }
.ca-badge.ok { background:#dcfce7; color:#166534; } .ca-badge.warn { background:#fef3c7; color:#92400e; } .ca-badge.bad { background:#fee2e2; color:#991b1b; }
.ca-stat { text-align:center; } .ca-stat b { display:block; font-size:1.9rem; color:var(--ca-blue); letter-spacing:-0.02em; } 
.ca-trail details { border:1px solid #e2e8f0; border-radius:12px; padding:10px 14px; margin:8px 0; background:var(--background-fill-primary,#fff); }
.ca-trail details[open] { border-color:var(--ca-blue); box-shadow:0 0 0 3px rgba(59,91,255,.10); }
.ca-trail summary { cursor:pointer; font-weight:600; }
.ca-trail pre { white-space:pre-wrap; font-family:inherit; background:#f8fafc; border-radius:8px; padding:10px; margin:8px 0 0; font-size:.88rem; color:#0f172a; }
.ca-path { color:var(--ca-muted); font-size:.8rem; margin-top:2px; }
.ca-cited { border-left:4px solid var(--ca-violet); }
footer { visibility:hidden; }
"""

HERO = """<div class="ca-hero"><h1>CourseAtlas AI</h1>
<p>Evidence-Grounded Academic Knowledge &amp; Retrieval Platform</p>
<span class="ca-pill">Standard RAG</span><span class="ca-pill">ChromaDB</span><span class="ca-pill">MiniLM embeddings</span>
<span class="ca-pill">Local LLM (Ollama)</span><span class="ca-pill">Verified citations</span><span class="ca-pill">PDF · DOCX · CSV · TXT</span></div>"""
