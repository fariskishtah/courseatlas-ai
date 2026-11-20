import shutil

import numpy as np

from src.retrieval.retriever import Retriever
from src.vectorstore.indexing import KnowledgeBase, make_doc_id


def test_ingest_all_formats_and_persistence(kb, sample_files, fake_embedder):
    for f in sample_files.iterdir():
        r = kb.ingest_file(f, "python")
        assert r["status"] == "indexed", r
    n = kb.store.count()
    assert n > 4 and kb.store.count("python") == n
    kb2 = KnowledgeBase(index_dir=kb.index_dir, embedder=fake_embedder, chunk_size=400, chunk_overlap=60)   # "restart"
    assert kb2.store.count() == n and len(kb2.store.list_docs()) == 4


def test_course_filter_isolation(kb, sample_files):
    kb.ingest_file(sample_files / "notes.txt", "python")
    kb.ingest_file(sample_files / "guide.docx", "statistics")
    ret = Retriever(kb)
    for q in ["loops while for", "bayes conditional probability", "function return"]:
        for course in ("python", "statistics"):
            hits = ret.search(q, [course], k=5, mode="dense").hits
            assert hits and all(h.meta["course_id"] == course for h in hits)
        hits = ret.search(q, ["python"], k=5, mode="hybrid").hits
        assert all(h.meta["course_id"] == "python" for h in hits)


def test_idempotent_ingestion(kb, sample_files):
    kb.ingest_file(sample_files / "notes.txt", "python")
    n = kb.store.count()
    r = kb.ingest_file(sample_files / "notes.txt", "python")
    assert r["status"] == "skipped_unchanged" and kb.store.count() == n


def test_update_replaces_without_stale_chunks(kb, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("ALPHA\nThe zebra is striped. " * 5)
    kb.ingest_file(f, "python")
    f.write_text("BETA\nThe giraffe is tall.")
    r = kb.ingest_file(f, "python")
    assert r["status"] == "updated"
    texts = " ".join(c["text"] for c in kb.store.get_all(["python"]))
    assert "giraffe" in texts and "zebra" not in texts
    assert len(kb.store.list_docs()) == 1


def test_duplicate_content_detected(kb, tmp_path):
    (tmp_path / "a.txt").write_text("same content here for dedup")
    (tmp_path / "b.txt").write_text("same content here for dedup")
    kb.ingest_file(tmp_path / "a.txt", "python")
    r = kb.ingest_file(tmp_path / "b.txt", "python")
    assert r["status"] == "duplicate" and kb.store.count() == 1
    assert kb.ingest_file(tmp_path / "b.txt", "statistics")["status"] == "indexed"   # other course is independent


def test_delete_document_and_failed_update_keeps_old_index(kb, tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("GOOD\nvalid content about gradient descent")
    kb.ingest_file(f, "python")
    before = kb.store.count()
    f.write_bytes(b"bad\x00binary")                       # now corrupt
    r = kb.ingest_file(f, "python")
    assert r["status"] == "failed" and kb.store.count() == before and kb.store.get_doc(make_doc_id("python", "a.txt"))["status"] == "indexed"
    assert kb.delete_document(make_doc_id("python", "a.txt")) and kb.store.count() == 0 and not kb.store.list_docs()


def test_failed_first_ingest_is_recorded(kb, tmp_path):
    (tmp_path / "e.txt").write_text("")
    r = kb.ingest_file(tmp_path / "e.txt", "python")
    assert r["status"] == "failed" and kb.store.list_docs()[0]["status"] == "failed"


def test_rebuild_all_and_reindex(kb, sample_files):
    for f in sample_files.iterdir():
        kb.ingest_file(f, "ml")
    n = kb.store.count()
    kb.rebuild_all()
    assert kb.store.count() == n
    assert kb.reindex_document(make_doc_id("ml", "notes.txt"))["status"] in ("updated", "indexed")
    assert kb.store.count() == n


def test_embedding_dimension_and_normalization(fake_embedder):
    v = fake_embedder.embed(["hello world", "second text"])
    assert v.shape == (2, fake_embedder.dimension)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0)


def test_hybrid_returns_lexical_matches(kb, sample_files):
    kb.ingest_file(sample_files / "runs.csv", "ml")
    hits = Retriever(kb).search("forest 0.95", ["ml"], k=3, mode="hybrid").hits
    assert any("forest" in h.text for h in hits[:2])
