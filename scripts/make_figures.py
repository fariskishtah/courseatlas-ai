"""Technical figures from REAL measured data (artifacts/metrics/*.json)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
M, F = ROOT / "artifacts" / "metrics", ROOT / "artifacts" / "figures"
F.mkdir(parents=True, exist_ok=True)
NAVY, BLUE, VIOLET, GRAY = "#0b1437", "#3b5bff", "#7c5cff", "#94a3b8"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})


def architecture():
    fig, ax = plt.subplots(figsize=(13, 4.6))
    ax.axis("off")
    steps = [("Question", "validate\n≤1000 chars"), ("Course scope", "explicit\nfilter"), ("Embed query", "MiniLM\n384-d"), ("ChromaDB", "cosine top-k\nWHERE course_id"),
             ("Similarity gate", "dev-calibrated\nthreshold"), ("Bounded context", "S1…Sn ids\n≤5000 chars"), ("Local LLM", "Ollama\nqwen2.5:3b"), ("Citation check", "strip invalid\ntags"), ("Answer +\nEvidence Trail", "")]
    w, gap = 1.25, 0.18
    for i, (t, s) in enumerate(steps):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 1.2), w, 1.5, boxstyle="round,pad=0.03,rounding_size=0.12", fc=NAVY if i in (0, 8) else BLUE if i in (3, 6) else VIOLET if i in (4, 7) else "#1b2a73", ec="none"))
        ax.text(x + w / 2, 2.15, t, ha="center", va="center", color="white", fontsize=9.5, fontweight="bold")
        ax.text(x + w / 2, 1.6, s, ha="center", va="center", color="#c9d3ff", fontsize=7.5)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.02, 1.95), (x + w + gap - 0.02, 1.95), arrowstyle="-|>", mutation_scale=10, color=GRAY))
    ax.text(0, 3.4, "CourseAtlas AI — Standard RAG pipeline", fontsize=14, fontweight="bold", color=NAVY)
    ax.text(0, 0.6, "Ingestion (offline): PDF · DOCX · CSV · TXT → extract → clean → structure-aware chunks (provenance) → embeddings → ChromaDB + SQLite registry",
            fontsize=9, color="#475569")
    ax.set_xlim(-0.1, len(steps) * (w + gap)); ax.set_ylim(0.3, 3.8)
    fig.savefig(F / "architecture.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def retrieval_bars():
    r = json.loads((M / "retrieval_eval.json").read_text())
    names = list(r["configs"])
    metrics = [("recall@1", "Recall@1"), ("recall@3", "Recall@3"), ("recall@5", "Recall@5"), ("rr", "MRR"), ("ndcg@5", "nDCG@5")]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    n = len(names); bw = 0.8 / n
    cols = [GRAY, BLUE, VIOLET, NAVY]
    for i, nm in enumerate(names):
        vals = [r["configs"][nm]["overall"][k] for k, _ in metrics]
        xs = [j + i * bw for j in range(len(metrics))]
        ax.bar(xs, vals, bw * 0.92, label=nm.replace("_", " "), color=cols[i % 4])
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.01, f"{v:.2f}", ha="center", fontsize=6.5)
    ax.set_xticks([j + 0.4 - bw / 2 for j in range(len(metrics))]); ax.set_xticklabels([m for _, m in metrics])
    ax.set_ylim(0, 1.08); ax.set_title("Retrieval quality on 46 answerable questions (hand-labelled gold)", loc="left", fontweight="bold", color=NAVY)
    ax.legend(fontsize=8, frameon=False, ncol=2)
    fig.savefig(F / "retrieval_metrics.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def chunk_hist():
    s = json.loads((M / "kb_stats.json").read_text())["chunk_sizes"]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.hist(s, bins=20, color=BLUE)
    ax.set_title(f"Chunk length distribution ({len(s)} chunks)", loc="left", fontweight="bold", color=NAVY)
    ax.set_xlabel("characters"); ax.set_ylabel("chunks")
    fig.savefig(F / "chunk_distribution.png", dpi=170, bbox_inches="tight"); plt.close(fig)


def rag_vs_baseline():
    p = M / "generation_eval.json"
    if not p.exists():
        return
    s = json.loads(p.read_text())["summary"]
    labels = ["Keyword-correct\n(answerable)", "Abstains on\nunanswerable", "Answers with\nsource citations"]
    rag = [s["rag"]["keyword_correct_rate_answerable"], s["rag"]["correct_abstention_rate_unanswerable"], s["rag"]["answers_with_valid_citation_rate"]]
    base = [s["no_context_baseline"]["keyword_correct_rate_answerable"], s["no_context_baseline"]["abstention_rate_unanswerable"], 0.0]
    fig, ax = plt.subplots(figsize=(8, 4))
    x = range(3)
    ax.bar([i - 0.2 for i in x], rag, 0.38, color=BLUE, label="RAG (CourseAtlas)")
    ax.bar([i + 0.2 for i in x], base, 0.38, color=GRAY, label="Same LLM, no context")
    for i, (a, b) in enumerate(zip(rag, base)):
        ax.text(i - 0.2, a + 0.02, f"{a:.0%}", ha="center", fontsize=8); ax.text(i + 0.2, b + 0.02, f"{b:.0%}", ha="center", fontsize=8)
    ax.set_xticks(list(x)); ax.set_xticklabels(labels); ax.set_ylim(0, 1.1); ax.legend(frameon=False)
    ax.set_title("RAG vs. no-context baseline (60 questions)", loc="left", fontweight="bold", color=NAVY)
    fig.savefig(F / "rag_vs_baseline.png", dpi=170, bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    architecture(); retrieval_bars(); chunk_hist(); rag_vs_baseline()
    print("figures written")
