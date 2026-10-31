"""Candidate passages for a why. BM25 finds the text's own words, embeddings find the meaning. An index of the whole text
(`specdeck spirit index`) is optional: without one, embeddings only rerank what BM25 found."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

WORD = re.compile(r"[a-z']+")
STOP = set("a an and are as at be but by for from had has have he her his i in is it its of on or our shall she so "
           "that the their them they this to unto was we were which who will with ye you your thee thou thy".split())


def words(text: str) -> list:
    return [w for w in WORD.findall(text.lower()) if w not in STOP and len(w) > 1]


class BM25:
    def __init__(self, passages: list, k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(words(p["text"])) for p in passages]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = sum(self.len) / max(len(self.len), 1)
        self.post: dict = {}
        for i, c in enumerate(self.tf):
            for w in c:
                self.post.setdefault(w, []).append(i)

    def top(self, query: str, n: int) -> list:
        """[(passage index, score)] best first"""
        scores: Counter = Counter()
        total = len(self.tf)
        for w in set(words(query)):
            docs = self.post.get(w, [])
            idf = math.log(1 + (total - len(docs) + 0.5) / (len(docs) + 0.5))
            for i in docs:
                f = self.tf[i][w]
                scores[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return scores.most_common(n)


def dot(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))


class Index:
    """Every passage's vector, saved next to the fetched text as NAME.vec.npy"""
    def __init__(self, vectors):
        self.vectors = vectors

    @staticmethod
    def path(text_path: Path) -> Path:
        return text_path.with_suffix(".vec.npy")

    @classmethod
    def load(cls, text_path: Path):
        p = cls.path(text_path)
        if not p.exists():
            return None
        import numpy as np
        return cls(np.load(p))

    def scores(self, query_vec: list):
        import numpy as np
        return self.vectors @ np.asarray(query_vec, dtype=np.float32)


def build_index(passages: list, text_path: Path, model, batch: int = 32, log=print) -> Path:
    """Saved as it goes, so a stopped build carries on where it stopped."""
    import numpy as np
    done = text_path.with_suffix(".vec.partial.jsonl")
    vecs = [json.loads(line) for line in done.read_text().splitlines()] if done.exists() else []
    with done.open("a") as f:
        for i in range(len(vecs), len(passages), batch):
            got = model.embed([p["text"] for p in passages[i:i + batch]])
            vecs += got
            f.write("".join(json.dumps([round(x, 5) for x in v]) + "\n" for v in got))
            f.flush()
            if (i // batch) % 20 == 0:
                log(f"  {len(vecs):,} of {len(passages):,}")
    p = Index.path(text_path)
    np.save(p, np.asarray(vecs, dtype=np.float32))
    done.unlink()
    return p


def candidates(passages: list, bm25: BM25, index, query: str, model, n: int = 10, pool: int = 40) -> list:
    """the n best passages for a query, [(passage index, cosine)]; the pool comes from both searches"""
    qv = model.embed([query], query=True)[0]
    hits = {i for i, _ in bm25.top(query, pool)}
    if index is not None:
        import numpy as np
        scores = index.scores(qv)
        hits |= {int(i) for i in np.argsort(-scores)[:pool]}
        scored = [(i, float(scores[i])) for i in hits]
    else:
        order = sorted(hits)
        vecs = model.embed([passages[i]["text"] for i in order]) if order else []
        scored = [(i, dot(v, qv)) for i, v in zip(order, vecs)]
    scored.sort(key=lambda s: -s[1])
    return scored[:n]
