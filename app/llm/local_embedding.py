"""Local, free embedding provider via fastembed (ONNX runtime, no PyTorch).

Why fastembed and not sentence-transformers directly: sentence-transformers
pulls in PyTorch, which alone is a few hundred MB installed and needs
several hundred MB of RAM at runtime even for a small model - tight to
impossible inside Render's free-tier 512MB web service. fastembed runs the
same all-MiniLM-L6-v2 weights through onnxruntime instead (~66MB installed,
no PyTorch), which comfortably fits alongside the rest of this app in a
512MB container. Same model, same output vectors - the only difference is
the runtime that executes it.

Not verified end-to-end in this build environment: the model weights
download from Hugging Face Hub on first use, and this sandbox has no
outbound access to huggingface.co (confirmed via direct test - a 403 from
the network's egress proxy). Verify with:

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
