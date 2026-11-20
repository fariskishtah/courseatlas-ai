"""Knowledge-base lifecycle: idempotent ingestion, update, delete, rebuild."""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from ..config import get_config, path as cfg_path
from ..embeddings.embedding_service import EmbeddingService, get_embedder
from ..ingestion import IngestionError, extract
from ..ingestion.chunking import chunk_blocks
from .store import VectorStore


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def make_doc_id(course_id: str, filename: str) -> str:
    return hashlib.sha1(f"{course_id}:{filename}".encode()).hexdigest()[:12]


def title_from_filename(name: str) -> str:
    words = re.sub(r"[_\-]+", " ", Path(name).stem).strip().split()
    special = {"ml": "ML", "csv": "CSV", "pdf": "PDF", "txt": "TXT", "docx": "DOCX"}
    return " ".join(special.get(w.lower(), w.capitalize()) for w in words)


class KnowledgeBase:
    def __init__(self, index_dir: Path | None = None, embedder: EmbeddingService | None = None,
                 chunk_size: int | None = None, chunk_overlap: int | None = None, collection: str = "chunks"):
        cfg = get_config()
        self.index_dir = index_dir or cfg_path("index_dir")
        self.embedder = embedder or get_embedder()
        self.chunk_size = chunk_size or cfg["chunking"]["chunk_size"]
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else cfg["chunking"]["chunk_overlap"]
        self.store = VectorStore(self.index_dir, collection)
        mp = cfg_path("data_dir") / "manifests" / "courses.json"
        self.courses = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}

    # ------------------------------------------------------------------
    def ingest_file(self, file: Path, course_id: str, *, source: str = "", license: str = "", force: bool = False,
                    stored_path: str | None = None, filename: str | None = None) -> dict:
        file = Path(file)
        filename = filename or file.name
        ext = file.suffix.lower().lstrip(".")
        doc_id = make_doc_id(course_id, filename)
        digest = sha256_file(file)
        prev = self.store.get_doc(doc_id)
        base = dict(doc_id=doc_id, course_id=course_id, filename=filename, doc_title=title_from_filename(filename),
                    file_type=ext, sha256=digest, bytes=file.stat().st_size, source=source or (prev or {}).get("source", "user upload"),
                    license=license or (prev or {}).get("license", "unspecified"), chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap, stored_path=stored_path or str(file))
        if prev and prev["status"] == "indexed" and prev["sha256"] == digest and not force \
                and prev["chunk_size"] == self.chunk_size and prev["chunk_overlap"] == self.chunk_overlap:
            return {"doc_id": doc_id, "status": "skipped_unchanged", "filename": filename, "n_chunks": prev["n_chunks"]}
        for d in self.store.list_docs(course_id):   # same content under another name in the same course
            if d["sha256"] == digest and d["doc_id"] != doc_id and d["status"] == "indexed":
                return {"doc_id": d["doc_id"], "status": "duplicate", "filename": filename,
                        "message": f"Identical to already indexed file '{d['filename']}'", "n_chunks": 0}
        try:
            t0 = time.perf_counter()
            ex = extract(file)
            t1 = time.perf_counter()
            chunks = chunk_blocks(ex.blocks, course_id=course_id, doc_id=doc_id, doc_title=base["doc_title"], filename=filename,
                                  file_type=ext, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
            vecs = self.embedder.embed([c.text for c in chunks])      # embed first: a failure leaves the old index intact
            t2 = time.perf_counter()
            self.store.delete_doc(doc_id)
            self.store.add_chunks(chunks, vecs)
            t3 = time.perf_counter()
        except Exception as e:  # noqa: BLE001 - report every failure without corrupting the index
            msg = f"{type(e).__name__}: {e}"
            if not prev or prev["status"] != "indexed":
                self.store.upsert_doc({**base, "n_chunks": 0, "status": "failed", "error": msg})
            return {"doc_id": doc_id, "status": "failed", "filename": filename, "error": msg, "n_chunks": 0}
        text = " ".join(b.text for b in ex.blocks)
        self.store.upsert_doc({**base, "pages": ex.page_count, "words": len(text.split()), "chars": len(text),
                               "extraction_method": ex.method, "n_chunks": len(chunks), "status": "indexed", "error": "",
                               "warnings": ex.warnings, "extract_s": t1 - t0, "embed_s": t2 - t1, "index_s": t3 - t2})
        return {"doc_id": doc_id, "status": "updated" if prev else "indexed", "filename": filename, "n_chunks": len(chunks),
                "warnings": ex.warnings, "extract_s": t1 - t0, "embed_s": t2 - t1, "index_s": t3 - t2}

    def ingest_course_dir(self, course_id: str, folder: Path, manifest: dict | None = None, force: bool = False) -> list[dict]:
        out = []
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower().lstrip(".") in ("pdf", "docx", "csv", "txt"):
                m = (manifest or {}).get((course_id, f.name), {})
                out.append(self.ingest_file(f, course_id, source=m.get("source", ""), license=m.get("license", ""), force=force))
        return out

    def delete_document(self, doc_id: str) -> bool:
        if not self.store.get_doc(doc_id):
            return False
        self.store.delete_doc(doc_id)
        self.store.remove_doc_record(doc_id)
        return True

    def reindex_document(self, doc_id: str) -> dict:
        d = self.store.get_doc(doc_id)
        if not d or not Path(d["stored_path"]).exists():
            return {"status": "failed", "error": "Original file not available"}
        return self.ingest_file(Path(d["stored_path"]), d["course_id"], force=True, filename=d["filename"], stored_path=d["stored_path"])

    def rebuild_all(self) -> list[dict]:
        docs = self.store.list_docs()
        self.store.reset()
        return [self.ingest_file(Path(d["stored_path"]), d["course_id"], force=True, filename=d["filename"],
                                 source=d["source"], license=d["license"], stored_path=d["stored_path"])
                for d in docs if Path(d["stored_path"]).exists()]

    # ------------------------------------------------------------------
    def course_summary(self) -> list[dict]:
        out = []
        for cid, meta in self.courses.items():
            docs = [d for d in self.store.list_docs(cid) if d["status"] == "indexed"]
            out.append({**meta, "course_id": cid, "documents": len(docs),
                        "chunks": sum(d["n_chunks"] for d in docs), "types": sorted({d["file_type"] for d in docs}),
                        "last_update": max([d["updated_at"] for d in docs], default=None),
                        "status": "indexed" if docs else "empty"})
        return out


def dashboard_stats(kb: KnowledgeBase) -> dict:
    docs = kb.store.list_docs()
    ok = [d for d in docs if d["status"] == "indexed"]
    fmt: dict[str, int] = {}
    for d in ok:
        fmt[d["file_type"]] = fmt.get(d["file_type"], 0) + 1
    times = [(d["extract_s"] or 0) + (d["embed_s"] or 0) + (d["index_s"] or 0) for d in ok]
    return {"courses": len(kb.courses), "documents": len(ok), "failed": len(docs) - len(ok), "chunks": sum(d["n_chunks"] for d in ok),
            "vectors": kb.store.count(), "formats": fmt, "avg_ingest_s": sum(times) / len(times) if times else 0.0,
            "words": sum(d["words"] or 0 for d in ok), "pages": sum(d["pages"] or 0 for d in ok),
            "per_course": {c: sum(1 for d in ok if d["course_id"] == c) for c in kb.courses}}
