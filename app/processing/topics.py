"""Section 7 stage 3's topic label, assigned via the same embedding-
similarity zero-shot technique as local classification - compare the
article's embedding to a fixed set of topic descriptions and take the
closest. Editable taxonomy: add/remove entries in TOPIC_LABELS, no other
code changes needed.
"""

from app.llm.base import EmbeddingProvider
from app.llm.similarity import cosine_similarity

TOPIC_LABELS: dict[str, str] = {
    "Politics": "This article is primarily about government, elections, or political parties.",
    "Economy & Business": "This article is about the economy, business, markets, companies, or finance.",
    "Sports": "This article is about sports, athletes, or sporting events.",
    "Entertainment": "This article is about movies, television, music, celebrities, or entertainment.",
    "Technology": "This article is about technology, gadgets, software, or the internet.",
    "International": "This article is about international relations or events outside India.",
    "Crime & Law": "This article is about crime, court cases, or law enforcement.",
    "Health": "This article is about health, medicine, or public health.",
    "Environment": "This article is about the environment, climate, or natural disasters.",
    "Education": "This article is about education, schools, or universities.",
    "Other": "This article does not clearly fit any specific news category.",
}


class TopicAssigner:
    def __init__(self, embedding_provider: EmbeddingProvider):
        self._embedding_provider = embedding_provider
        self._label_embeddings: dict[str, list[float]] | None = None

    def _get_label_embeddings(self) -> dict[str, list[float]]:
        if self._label_embeddings is None:
            names = list(TOPIC_LABELS.keys())
            vectors = self._embedding_provider.embed([TOPIC_LABELS[name] for name in names])
            self._label_embeddings = dict(zip(names, vectors))
        return self._label_embeddings

    def assign(self, article_embedding: list[float]) -> str:
        labels = self._get_label_embeddings()
        return max(labels, key=lambda name: cosine_similarity(article_embedding, labels[name]))
