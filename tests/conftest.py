import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeEmbedder:
    """Deterministic hashed bag-of-words embedder for fast unit tests (NOT used in integration tests)."""
    model_id = "fake-hash-embedder"
    dim = 256
    _model = object()

    @property
    def dimension(self):
        return self.dim

    def info(self):
        return {"model_id": self.model_id, "dimension": self.dim}

    def embed(self, texts, batch_size=32):
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                out[i, int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def kb(tmp_path, fake_embedder):
    from src.vectorstore.indexing import KnowledgeBase
    return KnowledgeBase(index_dir=tmp_path / "idx", embedder=fake_embedder, chunk_size=400, chunk_overlap=60)


@pytest.fixture
def sample_files(tmp_path):
    """Small real files in all four formats."""
    import docx
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    d = tmp_path / "files"
    d.mkdir()
    (d / "notes.txt").write_text("INTRO TO LOOPS\n====\nA for loop repeats a block.\nA while loop repeats until false.\n\nFUNCTIONS\nA function returns a value with return.\n", encoding="utf-8")
    (d / "runs.csv").write_text("id,model,score\n1,tree,0.91\n2,forest,0.95\n3,knn,\n", encoding="utf-8")
    doc = docx.Document()
    doc.add_heading("Probability", 1)
    doc.add_paragraph("Bayes theorem reverses conditional probability.")
    t = doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Dist", "Mean"
    t.rows[1].cells[0].text, t.rows[1].cells[1].text = "Binomial", "n*p"
    doc.save(d / "guide.docx")
    c = canvas.Canvas(str(d / "lecture.pdf"), pagesize=A4)
    for p in range(1, 5):
        c.drawString(72, 800, "REPEATED HEADER")
        c.drawString(72, 700, f"1. Topic {p}" if p == 1 else f"Body text for page {p} about gradient descent and learning rates.")
        c.drawString(72, 680, "Overfitting means memorizing noise." if p == 2 else "Filler sentence number one.")
        c.drawString(72, 40, f"Page {p}")
        c.showPage()
    c.save()
    return d
