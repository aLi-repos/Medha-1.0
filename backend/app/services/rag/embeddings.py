"""TF-IDF embedding model — stdlib only, no external dependencies."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class TFIDFModel:
    """Lightweight TF-IDF model built on the Python standard library."""

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._fitted = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, documents: list[str]) -> None:
        n_docs = len(documents)
        doc_freq: Counter[str] = Counter()
        all_terms: set[str] = set()

        for doc in documents:
            unique_terms = set(_tokenize(doc))
            all_terms.update(unique_terms)
            for term in unique_terms:
                doc_freq[term] += 1

        self._vocab = {term: idx for idx, term in enumerate(sorted(all_terms))}
        self._idf = {}
        for term, freq in doc_freq.items():
            self._idf[term] = math.log((n_docs + 1) / (freq + 1)) + 1
        self._fitted = True

    def _vectorize(self, text: str) -> dict[int, float]:
        tokens = _tokenize(text)
        if not tokens:
            return {}
        tf = Counter(tokens)
        vector: dict[int, float] = {}
        for token, count in tf.items():
            if token in self._vocab:
                idx = self._vocab[token]
                vector[idx] = count * self._idf.get(token, 1.0)
        return vector

    def transform(self, text: str) -> list[float]:
        if not self._fitted:
            raise RuntimeError("Model must be fitted before transform")
        vec = self._vectorize(text)
        dim = len(self._vocab)
        result = [0.0] * dim
        for idx, val in vec.items():
            result[idx] = val
        return result

    def transform_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.transform(t) for t in texts]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
