"""Real pretrained sentence embeddings (sentence-transformers), L2-normalised for cosine retrieval."""
from __future__ import annotations

import threading
from pathlib import Path
import time

import numpy as np

from ..config import get_config

_lock = threading.Lock()


class EmbeddingService:
    def __init__(self, model_id: str | None = None):
        cfg = get_config()["embedding"]
        self.model_id = model_id or cfg["model_id"]
        self.normalize = cfg.get("normalize", True)
        self._model = None
        self.load_seconds: float | None = None

    @property
    def model(self):
        if self._model is None:
            with _lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    t = time.perf_counter()
                    self._model = SentenceTransformer(self.model_id, device="cpu")
                    self.load_seconds = time.perf_counter() - t
        return self._model

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def revision(self) -> str:
        try:
            from huggingface_hub import snapshot_download
            return Path(snapshot_download(self.model_id, local_files_only=True)).name
        except Exception:
            return "unknown"

    def embed(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dimension), dtype="float32")
        return self.model.encode(texts, batch_size=batch_size, normalize_embeddings=self.normalize,
                                 show_progress_bar=False, convert_to_numpy=True).astype("float32")

    def info(self) -> dict:
        return {"model_id": self.model_id, "revision": self.revision(), "dimension": self.dimension,
                "normalized": self.normalize, "device": "cpu"}


_default: EmbeddingService | None = None


def get_embedder() -> EmbeddingService:
    global _default
    if _default is None:
        _default = EmbeddingService()
    return _default
