"""Local, free subject-sentiment classification via embedding-similarity
zero-shot - the same technique and the same reasoning as
app/llm/local_classification.py (reuses the already-loaded MiniLM model,
zero additional RAM), just against per-entity reference phrases instead of
fixed establishment-framing ones.

Cost note, flagged plainly since it bears directly on the "does this
overload the review screen" question raised for many-entity articles: this
runs one embedding call *per entity found in the article*, not once per
article. A cabinet-reshuffle story mentioning fifteen ministers costs
fifteen embedding calls here (in addition to the one for establishment
classification). For the local provider this is free but not instant -
CPU time, not RAM, is the constraint (see README's Phase 2 resource
writeup) - and for a paid provider (OpenAI/Gemini) it is fifteen billed
calls for that one article. This is the same "many entities" cost driver
flagged in app/processing/entities.py's module docstring and reported back
to the user directly, not silently absorbed.
"""

from app.llm.base import EntitySentimentBatchItem, EntitySentimentProvider, EntitySentimentResult
from app.llm.local_embedding import LocalEmbeddingProvider
from app.llm.similarity import cosine_similarity, softmax_confidence
from app.models.enums import SubjectSentiment


class EmbeddingSimilarityEntitySentimentClassifier(EntitySentimentProvider):
    name = "local"

    def __init__(self, embedding_provider: LocalEmbeddingProvider | None = None):
        self._embedding_provider = embedding_provider or LocalEmbeddingProvider()

    def classify_subject_sentiment(self, headline: str, body_text: str, entity_name: str) -> EntitySentimentResult:
        text = f"{headline}\n{body_text}"
        # Reference phrases are built fresh per entity (they interpolate
        # the name), unlike local_classification.py's fixed, cacheable
        # establishment-axis references - there is no way to precompute
        # these once for all entities.
        favorable_ref = (
            f"This article portrays {entity_name} favorably, praising their actions, statements, or achievements."
        )
        unfavorable_ref = (
            f"This article is critical of {entity_name}, highlighting their failures, wrongdoing, or controversy."
        )
        neutral_ref = f"This article mentions {entity_name} in a factual way, without praising or criticizing them."

        article_vec, favorable_vec, unfavorable_vec, neutral_vec = self._embedding_provider.embed(
            [text, favorable_ref, unfavorable_ref, neutral_ref]
        )
        sentiments = [SubjectSentiment.FAVORABLE, SubjectSentiment.UNFAVORABLE, SubjectSentiment.NEUTRAL]
        similarities = [
            cosine_similarity(article_vec, favorable_vec),
            cosine_similarity(article_vec, unfavorable_vec),
            cosine_similarity(article_vec, neutral_vec),
        ]
        confidences = softmax_confidence(similarities)
        best_index = max(range(3), key=lambda i: similarities[i])
        return EntitySentimentResult(sentiment=sentiments[best_index], confidence_score=confidences[best_index])

    def classify_subject_sentiment_batch(
        self, items: list[EntitySentimentBatchItem]
    ) -> dict[int, EntitySentimentResult]:
        """Same zero-shot technique as classify_subject_sentiment above,
        batched into one embed() call for the whole list instead of one
        call per item - four embeddings per item (its text + three
        reference phrases) all go into a single request to the embedding
        model, which is one model invocation either way. This doesn't
        change what this provider is capable of getting right (see this
        module's own docstring on the technique's limits) - it only
        removes the redundant per-item call overhead, same as the paid
        providers' batch overrides do for their own reason (avoiding
        per-item billing).
        """
        if not items:
            return {}
        sentiments = [SubjectSentiment.FAVORABLE, SubjectSentiment.UNFAVORABLE, SubjectSentiment.NEUTRAL]
        texts: list[str] = []
        for item in items:
            text = f"{item.headline}\n{item.body_text}"
            texts.extend(
                [
                    text,
                    f"This article portrays {item.entity_name} favorably, praising their actions, statements, or achievements.",
                    f"This article is critical of {item.entity_name}, highlighting their failures, wrongdoing, or controversy.",
                    f"This article mentions {item.entity_name} in a factual way, without praising or criticizing them.",
                ]
            )
        vectors = self._embedding_provider.embed(texts)

        results: dict[int, EntitySentimentResult] = {}
        for i, item in enumerate(items):
            article_vec, favorable_vec, unfavorable_vec, neutral_vec = vectors[i * 4 : i * 4 + 4]
            similarities = [
                cosine_similarity(article_vec, favorable_vec),
                cosine_similarity(article_vec, unfavorable_vec),
                cosine_similarity(article_vec, neutral_vec),
            ]
            confidences = softmax_confidence(similarities)
            best_index = max(range(3), key=lambda i: similarities[i])
            results[item.index] = EntitySentimentResult(
                sentiment=sentiments[best_index], confidence_score=confidences[best_index]
            )
        return results
