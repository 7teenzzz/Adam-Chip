"""Episode search index для памяти Адама.

BM25Index — поиск по темам и ключевым репликам без внешних зависимостей.
FaissEpisodeIndex — векторный поиск (Wave 1: TF-IDF векторы + faiss-cpu).
  Wave 2 (roadmap): заменить TF-IDF на llama.cpp /embeddings.

Оба класса предоставляют единый интерфейс: build(episodes) + search(query, k).
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .episodic import Episode

log = logging.getLogger(__name__)

_TOKENIZE_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    return _TOKENIZE_RE.findall(text.lower())


def _episode_tokens(episode: Episode) -> list[str]:
    parts: list[str] = list(episode.themes)
    for h in episode.highlights:
        parts.append(h.text)
    if episode.visitor.introduced_name:
        parts.append(episode.visitor.introduced_name)
    return _tokenize(" ".join(parts))


# ---------- BM25 ----------


class BM25Index:
    """BM25 Okapi поиск по эпизодам. Чистый Python, без зависимостей.

    Документы = темы + ключевые реплики + имя посетителя каждого эпизода.
    """

    _K1 = 1.5
    _B = 0.75

    def __init__(self) -> None:
        self._episodes: list[Episode] = []
        self._corpus: list[list[str]] = []
        self._idf: dict[str, float] = {}
        self._avg_dl: float = 0.0

    def build(self, episodes: list[Episode]) -> None:
        self._episodes = list(episodes)
        self._corpus = [_episode_tokens(ep) for ep in episodes]
        n = len(self._corpus)
        if n == 0:
            self._idf = {}
            self._avg_dl = 0.0
            return
        self._avg_dl = sum(len(doc) for doc in self._corpus) / n
        df: Counter[str] = Counter()
        for doc in self._corpus:
            for term in set(doc):
                df[term] += 1
        self._idf = {
            term: math.log((n - count + 0.5) / (count + 0.5) + 1.0)
            for term, count in df.items()
        }

    def search(self, query: str, limit: int = 3) -> list[Episode]:
        if not self._episodes:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scores: list[tuple[float, int]] = []
        for i, doc in enumerate(self._corpus):
            score = self._bm25_score(q_tokens, doc)
            if score > 0:
                scores.append((score, i))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [self._episodes[i] for _, i in scores[:limit]]

    def _bm25_score(self, q_tokens: list[str], doc: list[str]) -> float:
        dl = len(doc)
        tf_map = Counter(doc)
        score = 0.0
        for term in q_tokens:
            idf = self._idf.get(term, 0.0)
            tf = tf_map.get(term, 0)
            denom = tf + self._K1 * (1 - self._B + self._B * dl / max(1, self._avg_dl))
            score += idf * (tf * (self._K1 + 1)) / denom
        return score


# ---------- FAISS CPU (Wave 1 — TF-IDF векторы) ----------


class FaissEpisodeIndex:
    """Векторный поиск по эпизодам через FAISS CPU + TF-IDF векторизация.

    Требует: pip install faiss-cpu numpy  (нет конфликта с Jetson PyTorch — pure C++).
    Wave 2 (см. Roadmap): заменить TF-IDF на llama.cpp /embeddings.
    """

    def __init__(self, meta_path: Path, index_path: Path) -> None:
        self._meta_path = meta_path
        self._index_path = index_path
        self._episodes: list[Episode] = []
        self._vocab: dict[str, int] = {}
        self._idf: list[float] = []
        self._index = None  # faiss.Index | None
        self._available = self._check_deps()

    @staticmethod
    def _check_deps() -> bool:
        try:
            import faiss  # noqa: F401
            import numpy  # noqa: F401
            return True
        except ImportError:
            log.warning("memory_search: faiss-cpu or numpy not installed — FaissEpisodeIndex disabled")
            return False

    def build(self, episodes: list[Episode]) -> None:
        if not self._available or not episodes:
            return
        import numpy as np
        import faiss

        self._episodes = list(episodes)
        corpus = [_episode_tokens(ep) for ep in episodes]
        n = len(corpus)
        # build vocabulary + IDF
        df: Counter[str] = Counter()
        for doc in corpus:
            for term in set(doc):
                df[term] += 1
        self._vocab = {term: i for i, term in enumerate(sorted(df))}
        self._idf = [
            math.log((n + 1) / (df[term] + 1)) + 1.0
            for term in sorted(df)
        ]
        dim = len(self._vocab)
        if dim == 0:
            return

        vecs = np.zeros((n, dim), dtype=np.float32)
        for i, doc in enumerate(corpus):
            tf = Counter(doc)
            for term, count in tf.items():
                j = self._vocab.get(term)
                if j is not None:
                    vecs[i, j] = count / max(1, len(doc)) * self._idf[j]
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vecs /= norms

        self._index = faiss.IndexFlatIP(dim)
        self._index.add(vecs)
        log.info("memory_search: built FAISS index with %d episodes, dim=%d", n, dim)

    def save(self) -> None:
        if not self._available or self._index is None:
            return
        import faiss
        faiss.write_index(self._index, str(self._index_path))
        meta = {
            "vocab": self._vocab,
            "idf": self._idf,
            "episode_ids": [ep.id for ep in self._episodes],
        }
        self._meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        log.info("memory_search: saved FAISS index to %s", self._index_path)

    def load(self, episodes_by_id: dict[str, Episode]) -> bool:
        if not self._available:
            return False
        if not self._index_path.exists() or not self._meta_path.exists():
            return False
        try:
            import faiss
            self._index = faiss.read_index(str(self._index_path))
            meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
            self._vocab = meta["vocab"]
            self._idf = meta["idf"]
            self._episodes = [
                episodes_by_id[eid] for eid in meta["episode_ids"]
                if eid in episodes_by_id
            ]
            log.info("memory_search: loaded FAISS index (%d episodes)", len(self._episodes))
            return True
        except Exception as exc:
            log.warning("memory_search: failed to load FAISS index: %s", exc)
            return False

    def search(self, query: str, k: int = 3) -> list[Episode]:
        if not self._available or self._index is None or not self._episodes:
            return []
        import numpy as np
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        dim = len(self._vocab)
        qv = np.zeros((1, dim), dtype=np.float32)
        tf = Counter(q_tokens)
        for term, count in tf.items():
            j = self._vocab.get(term)
            if j is not None:
                qv[0, j] = count / max(1, len(q_tokens)) * self._idf[j]
        norm = np.linalg.norm(qv)
        if norm > 0:
            qv /= norm
        k = min(k, len(self._episodes))
        distances, indices = self._index.search(qv, k)
        return [self._episodes[i] for i in indices[0] if 0 <= i < len(self._episodes)]
