"""Local, free classification via embedding-similarity zero-shot.

Why this and not a separate local LLM/NLI model: this reuses the exact
MiniLM embedding model already loaded for clustering (app/llm/
local_embedding.py), so it costs zero additional RAM - a real concern on
Render's 512MB free tier, where a *second* ML model for classification
would very plausibly not fit alongside the first. See README's Phase 2
section for the full resource writeup.

Quality expectations, stated plainly: comparing an article's embedding to
a handful of reference-phrase embeddings is a real zero-shot technique, but
it's fundamentally a topical/semantic-similarity signal, not a reasoning
one. It's usable for the establishment-relevance split (political vs. not
is close to a topic distinction) but meaningfully weaker at pro vs. anti
framing, which is a subtler stance judgment than embeddings are naturally
good at. Treat this as a free, always-available baseline - not a stand-in
for what OpenAI/Gemini will produce once you enable them.
"""

from app.llm.base import ClassificationProvider, ClassificationResult, EmbeddingProvider
from app.llm.local_embedding import LocalEmbeddingProvider
from app.llm.similarity import cosine_similarity, softmax_confidence
from app.models.enums import ClassificationTag
from app.processing.jurisdiction import guess_jurisdiction_keyword

_POLITICAL_REF = (
    "This news article is about government policy, elections, political "
    "parties, ministers, or public administration."
)
_APOLITICAL_REF = (
    "This news article is about sports, entertainment, weather, technology "
    "products, or everyday life, with no connection to government or politics."
)
_PRO_REF = (
    "This article portrays the government or ruling party favorably, "
    "praising its actions, policies, or achievements."
)
_ANTI_REF = (
    "This article is critical of the government or ruling party, "
    "highlighting failures, scandals, or wrongdoing."
)


class EmbeddingSimilarityClassifier(ClassificationProvider):
    name = "local"

    def __init__(self, embedding_provider: EmbeddingProvider | None = None):
        self._embedding_provider = embedding_provider or LocalEmbeddingProvider()
        self._ref_embeddings: dict[str, list[float]] | None = None

    def _get_ref_embeddings(self) -> dict[str, list[float]]:
        if self._ref_embeddings is None:
            political, apolitical, pro, anti = self._embedding_provider.embed(
                [_POLITICAL_REF, _APOLITICAL_REF, _PRO_REF, _ANTI_REF]
            )
            self._ref_embeddings = {"political": political, "apolitical": apolitical, "pro": pro, "anti": anti}
        return self._ref_embeddings

    def _pro_vs_anti(self, text: str, article_vec: list[float], refs: dict[str, list[float]]) -> ClassificationResult:
        pro_sim = cosine_similarity(article_vec, refs["pro"])
        anti_sim = cosine_similarity(article_vec, refs["anti"])
        if pro_sim >= anti_sim:
            classification = ClassificationTag.PRO_ESTABLISHMENT
            confidence = softmax_confidence([pro_sim, anti_sim])[0]
        else:
            classification = ClassificationTag.ANTI_ESTABLISHMENT
            confidence = softmax_confidence([anti_sim, pro_sim])[0]
        return ClassificationResult(
            classification=classification,
            jurisdiction=guess_jurisdiction_keyword(text),
            confidence_score=confidence,
        )

    def classify(self, headline: str, body_text: str) -> ClassificationResult:
        text = f"{headline}\n{body_text}"
        (article_vec,) = self._embedding_provider.embed([text])
        refs = self._get_ref_embeddings()

        political_sim = cosine_similarity(article_vec, refs["political"])
        apolitical_sim = cosine_similarity(article_vec, refs["apolitical"])

        if political_sim >= apolitical_sim:
            return self._pro_vs_anti(text, article_vec, refs)

        confidence = softmax_confidence([apolitical_sim, political_sim])[0]
        return ClassificationResult(classification=ClassificationTag.APOLITICAL, jurisdiction=None, confidence_score=confidence)

    def classify_forcing_establishment_relevant(self, headline: str, body_text: str) -> ClassificationResult:
        text = f"{headline}\n{body_text}"
        (article_vec,) = self._embedding_provider.embed([text])
        refs = self._get_ref_embeddings()
        return self._pro_vs_anti(text, article_vec, refs)
