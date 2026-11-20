"""ChromaDB persistent vector store with metadata filtering, plus a SQLite document registry."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import chromadb
import numpy as np

from ..models import Chunk

REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  doc_id TEXT PRIMARY KEY, course_id TEXT, filename TEXT, doc_title TEXT, file_type TEXT,
  sha256 TEXT, bytes INTEGER, pages INTEGER, words INTEGER, chars INTEGER, extraction_method TEXT,
  n_chunks INTEGER, status TEXT, error TEXT, warnings TEXT, source TEXT, license TEXT,
  chunk_size INTEGER, chunk_overlap INTEGER, stored_path TEXT,
  extract_s REAL, embed_s REAL, index_s REAL, updated_at REAL)
"""


class VectorStore:
    def __init__(self, index_dir: Path, collection: str = "chunks"):
        index_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir = index_dir
        self.client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
        self.col = self.client.get_or_create_collection(collection, metadata={"hnsw:space": "cosine"})
        self.db = sqlite3.connect(str(index_dir / "registry.sqlite"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(REGISTRY_SCHEMA)
        self.db.commit()

    # ---- vectors -------------------------------------------------------
    def add_chunks(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        for i in range(0, len(chunks), 256):
            part = chunks[i:i + 256]
            self.col.add(ids=[c.chunk_id for c in part], embeddings=embeddings[i:i + 256].tolist(),
                         documents=[c.text for c in part], metadatas=[c.metadata() for c in part])

    def delete_doc(self, doc_id: str) -> None:
        self.col.delete(where={"doc_id": doc_id})

    def count(self, course_id: str | None = None) -> int:
        if course_id is None:
            return self.col.count()
        return len(self.col.get(where={"course_id": course_id}, include=[])["ids"])

    @staticmethod
    def _where(course_ids: list[str] | None):
        if not course_ids:
            return None
        return {"course_id": course_ids[0]} if len(course_ids) == 1 else {"course_id": {"$in": list(course_ids)}}

    def query(self, embedding: np.ndarray, k: int, course_ids: list[str] | None) -> list[dict]:
        n = self.count() if not course_ids else sum(self.count(c) for c in course_ids)
        if n == 0:
            return []
        res = self.col.query(query_embeddings=[embedding.tolist()], n_results=min(k, n), where=self._where(course_ids),
                             include=["documents", "metadatas", "distances"])
        out = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            out.append({"chunk_id": cid, "text": doc, "meta": meta, "score": 1.0 - float(dist)})  # cosine similarity
        return out

    def get_all(self, course_ids: list[str] | None = None) -> list[dict]:
        res = self.col.get(where=self._where(course_ids), include=["documents", "metadatas"])
        return [{"chunk_id": i, "text": d, "meta": m} for i, d, m in zip(res["ids"], res["documents"], res["metadatas"])]

    def get_chunk(self, chunk_id: str) -> dict | None:
        res = self.col.get(ids=[chunk_id], include=["documents", "metadatas"])
        if not res["ids"]:
            return None
        return {"chunk_id": res["ids"][0], "text": res["documents"][0], "meta": res["metadatas"][0]}

    # ---- registry ------------------------------------------------------
    def upsert_doc(self, rec: dict) -> None:
        rec = {**rec, "updated_at": time.time()}
        if "warnings" in rec and not isinstance(rec["warnings"], str):
            rec["warnings"] = json.dumps(rec["warnings"])
        cols = ",".join(rec)
        self.db.execute(f"INSERT OR REPLACE INTO documents ({cols}) VALUES ({','.join('?' * len(rec))})", list(rec.values()))
        self.db.commit()

    def get_doc(self, doc_id: str) -> dict | None:
        r = self.db.execute("SELECT * FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
        return dict(r) if r else None

    def list_docs(self, course_id: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM documents", ()
        if course_id:
            q, a = q + " WHERE course_id=?", (course_id,)
        return [dict(r) for r in self.db.execute(q + " ORDER BY course_id, filename", a)]

    def remove_doc_record(self, doc_id: str) -> None:
        self.db.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
        self.db.commit()

    def reset(self) -> None:
        self.client.delete_collection(self.col.name)
        self.col = self.client.get_or_create_collection(self.col.name, metadata={"hnsw:space": "cosine"})
        self.db.execute("DELETE FROM documents")
        self.db.commit()
