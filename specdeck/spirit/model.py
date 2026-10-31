"""Open models through a local Ollama: Gemma writes, EmbeddingGemma finds. Nothing leaves the machine."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

OLLAMA = os.environ.get("OLLAMA", "http://127.0.0.1:11434")
GEMMA = os.environ.get("SPECDECK_SPIRIT_MODEL", "gemma4:12b-it-qat")
EMBED = os.environ.get("SPECDECK_SPIRIT_EMBED", "embeddinggemma:latest")
DIMS = 256                                  # EmbeddingGemma's vectors keep their meaning when cut short


class ModelError(RuntimeError):
    pass


def _post(path: str, body: dict, timeout: int = 900) -> dict:
    req = urllib.request.Request(f"{OLLAMA}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, TimeoutError) as e:
        raise ModelError(f"no model at {OLLAMA} ({e}); start Ollama, then `ollama pull {GEMMA}` and `ollama pull {EMBED}`")


class Ollama:
    """The two things the layer asks of a model. Tests pass their own object with the same methods."""
    name = GEMMA

    def ask_json(self, prompt: str, num_predict: int = 500) -> dict:
        out = _post("/api/chat", {"model": GEMMA, "messages": [{"role": "user", "content": prompt}], "stream": False,
                                  "think": False, "format": "json",
                                  "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": num_predict}})
        text = out["message"]["content"]
        try:
            return json.loads(text)
        except ValueError:
            m = re.search(r"\{.*\}", text, re.S)
            try:
                return json.loads(m.group()) if m else {}
            except ValueError:
                return {}

    def embed(self, texts: list, query: bool = False) -> list:
        """vectors cut to DIMS and scaled to length 1, with the prefixes EmbeddingGemma was trained on"""
        pre = "task: search result | query: " if query else "title: none | text: "
        out = _post("/api/embed", {"model": EMBED, "input": [pre + t[:1500] for t in texts]})["embeddings"]
        vecs = []
        for v in out:
            v = v[:DIMS]
            n = sum(x * x for x in v) ** 0.5 or 1.0
            vecs.append([x / n for x in v])
        return vecs
