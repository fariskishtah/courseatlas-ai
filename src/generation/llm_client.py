"""Local LLM runtime client (Ollama). No paid APIs; no fabricated fallback answers."""
from __future__ import annotations

import json
import time

import requests

from ..config import get_config


class LLMUnavailable(RuntimeError):
    pass


class OllamaClient:
    def __init__(self):
        c = get_config()["llm"]
        self.base = c["base_url"].rstrip("/")
        self.model = c["model"]
        self.opts = {"temperature": c["temperature"], "num_ctx": c["num_ctx"], "num_predict": c["num_predict"], "seed": 7}
        self.timeout = c["timeout_s"]

    def available(self) -> tuple[bool, str]:
        try:
            tags = requests.get(f"{self.base}/api/tags", timeout=3).json()
            names = [m["name"] for m in tags.get("models", [])]
            if self.model not in names:
                return False, f"Model '{self.model}' is not pulled (run: ollama pull {self.model})"
            return True, "ok"
        except Exception as e:  # noqa: BLE001
            return False, f"Ollama not reachable at {self.base}: {type(e).__name__}"

    def chat(self, messages: list[dict], stream: bool = False):
        """Returns (text, metrics). With stream=True returns a generator yielding partial text, then metrics dict."""
        payload = {"model": self.model, "messages": messages, "stream": stream, "options": self.opts}
        try:
            r = requests.post(f"{self.base}/api/chat", json=payload, timeout=self.timeout, stream=stream)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            raise LLMUnavailable(f"LLM call failed: {type(e).__name__}: {e}") from e
        if not stream:
            d = r.json()
            return d["message"]["content"], self._metrics(d)
        return self._iter(r)

    def _iter(self, r):
        text = ""
        for line in r.iter_lines():
            if not line:
                continue
            d = json.loads(line)
            text += d.get("message", {}).get("content", "")
            if d.get("done"):
                yield text, self._metrics(d)
                return
            yield text, None

    @staticmethod
    def _metrics(d: dict) -> dict:
        return {"llm_total_s": d.get("total_duration", 0) / 1e9, "llm_load_s": d.get("load_duration", 0) / 1e9,
                "prompt_tokens": d.get("prompt_eval_count"), "output_tokens": d.get("eval_count")}
