"""Shared cosine-similarity / softmax math for embedding-based zero-shot
techniques (local classification, topic labeling). Not tied to any
particular provider.
"""

import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def softmax_confidence(scores: list[float], temperature: float = 10.0) -> list[float]:
    """Temperature-scaled softmax over raw similarity scores.

    Sentence embeddings for semantically related-but-distinct phrases tend
    to sit fairly close together (often 0.3-0.7 cosine similarity even for
    "opposite" labels), so a plain softmax looks artificially close to
    uniform. Temperature scaling sharpens that into a more decisive-looking
    confidence - but the temperature value here is a starting-point default,
    not a tuned constant (this build environment can't download the
    embedding model to calibrate it against real articles).
    """
    arr = np.array(scores) * temperature
    exp = np.exp(arr - np.max(arr))
    probs = exp / exp.sum()
    return probs.tolist()
