"""Local, free embedding provider via fastembed (ONNX runtime, no PyTorch).

Why fastembed and not sentence-transformers directly: sentence-transformers
pulls in PyTorch, which alone is a few hundred MB installed and needs
several hundred MB of RAM at runtime even for a small model - tight to
impossible inside Render's free-tier 512MB web service. fastembed runs
model weights through onnxruntime instead (no PyTorch needed), which
comfortably fit alongside the rest of this app in a 512MB container for
the original model.

MODEL CHOICE - HISTORY, READ BEFORE CHANGING THIS AGAIN: this was
all-MiniLM-L6-v2 (English-only, ~0.09GB quantized ONNX weights), then
briefly paraphrase-multilingual-MiniLM-L12-v2 (~50 languages including
Hindi, ~0.22GB), then reverted back to all-MiniLM-L6-v2. The multilingual
swap was to fix Hindi local outlets (config/outlets.yaml, e.g. City News
Rajasthan) getting near-random pro/anti classification - the English-only
model couldn't represent Hindi text meaningfully at all, wholly separate
from local_classification.py's (also English) reference phrases. That
swap was then CONFIRMED to exceed Render's 512MB free-tier memory during
ingestion (real production OOM, not the theoretical risk described
below when this swap was made) and was reverted here for that reason.

Hindi (and any other non-English) classification is now handled at a
different layer instead: LLM_PROVIDER=openai/gemini (see
app/llm/factory.py, app/llm/openai_provider.py). A real LLM API call
sends raw article text directly to the model, with no embedding-model
dependency at all - so classification quality for any language no longer
depends on which model this file loads. This file's model only affects
clustering/dedup quality now (finding the same story across outlets),
which stays on the smaller English-only model rather than paying its
memory cost for a problem this file no longer needs to solve. Real,
smaller, separate residual gap: cross-outlet duplicate-detection for
Hindi articles is weaker than for English ones (exact wire-copy is
lexically similar enough to likely still cluster fine; more paraphrased
duplicates might not) - not fixed by this revert, not blocking either.

Same output dimension either way (384 - see app.constants.EMBEDDING_DIM),
so neither swap needed a migration to resize articles.embedding.

Not verified end-to-end in this build environment: the model weights
download from Hugging Face Hub on first use, and this sandbox has no
outbound access to huggingface.co (confirmed via direct test - a 403
from the network's egress proxy). Verify with:

    python -m app.cli verify-local-models

from a machine with normal internet access (or via the Render deployment)
before relying on this in production.
"""

import logging

from app.config import settings
from app.constants import EMBEDDING_DIM
from app.llm.base import EmbeddingProvider

logger = logging.getLogger(__name__)


class LocalEmbeddingProvider(EmbeddingProvider):
    name = f"local:{settings.local_embedding_model}"

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.local_embedding_model
        self._model = None  # lazy-loaded: downloading/loading is expensive

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            logger.info("Loading local embedding model %s (first use downloads it if not cached)", self.model_name)
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = [v.tolist() for v in model.embed(texts)]
        for v in vectors:
            if len(v) != EMBEDDING_DIM:
                raise ValueError(
                    f"Embedding model {self.model_name} returned dim {len(v)}, "
                    f"expected {EMBEDDING_DIM} (app.constants.EMBEDDING_DIM). "
                    "If you changed LOCAL_EMBEDDING_MODEL to a model with a "
                    "different output size, update EMBEDDING_DIM and add a "
                    "migration to resize articles.embedding."
                )
        return vectors
