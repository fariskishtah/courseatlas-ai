"""Configuration loading (YAML files in configs/, env overrides)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return yaml.safe_load((ROOT / "configs" / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_config() -> dict:
    cfg = {"app": _load("app.yaml")["app"], **_load("retrieval.yaml"), **_load("models.yaml")}
    if os.getenv("COURSEATLAS_READ_ONLY") == "1":
        cfg["app"]["read_only"] = True
    if os.getenv("COURSEATLAS_LLM_MODEL"):
        cfg["llm"]["model"] = os.environ["COURSEATLAS_LLM_MODEL"]
    if os.getenv("COURSEATLAS_INDEX_DIR"):
        cfg["app"]["index_dir"] = os.environ["COURSEATLAS_INDEX_DIR"]
    return cfg


def path(key: str) -> Path:
    p = Path(get_config()["app"][key])
    return p if p.is_absolute() else ROOT / p
