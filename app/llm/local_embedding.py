"""Local, free embedding provider via fastembed (ONNX runtime, no PyTorch).

Why fastembed and not sentence-transformers directly: sentence-transformers
pulls in PyTorch, which alone is a few hundred MB installed and needs
several hundred MB of RAM at runtime even for a small model - tight to
impossible inside Render's free-tier 512MB web service. fastembed runs
model weights through onnxruntime instead (no PyTorch needed), which
comfortably fit alongside the rest of this app in a 512MB container for
the original model.

MODEL CHOICE - swapped from all-MiniLM-L6-v2 (English-only, ~0.09GB
quantized ONNX weights) to paraphrase-multilingual-MiniLM-L12-v2
(~50 languages including Hindi, ~0.22GB quantized ONNX weights - both
sizes per fastembed's own TextEmbedding.list_supported_models(), not
independently verified). Per direct instruction: local outlets added to
config/outlets.yaml (e.g. City News Rajasthan) publish in Hindi, and the
English-only model was giving every Hindi article a near-random pro/anti
classification (comparing its embedding against the English reference
phrases in app/llm/local_classification.py) rather than a real one - the
embedding model itself couldn't represent Hindi text meaningfully, wholly
separate from the reference phrases' language.

Deliberately kept the reference phrases in local_classification.py
English rather than translating them per language: "paraphrase-
multilingual" models are specifically trained (via parallel-sentence
distillation from an English teacher model) so that semantically
equivalent sentences in *different* languages land close together in
the same vector space - that cross-lingual alignment is the entire point
of this model family, so an English reference phrase should still compare
sensibly against a Hindi article's embedding. This is the documented
design intent of the model, not verified against this app's actual
Hindi content in this build environment (see below).

Same output dimension as the old model (384 - see app.constants.
EMBEDDING_DIM), so no migration is needed to resize articles.embedding.

MEMORY - NOT VERIFIED, THIS IS THE OPEN QUESTION THIS SWAP EXISTS TO
ANSWER: going from ~0.09GB to ~0.22GB of ONNX weights (per fastembed's
own reported size, not confirmed by actually loading it) may or may not
still fit Render's 512MB free-tier web service alongside the rest of the
app - there was headroom at the smaller size, but nobody has measured
how much. This has to be checked on the actual deployment (or any
machine with normal internet access - this sandbox's egress proxy blocks
huggingface.co, so the model weights can't even be downloaded here,
let alone memory-profiled). If it doesn't fit, per direct instruction
the fallback is routing to OpenAI/Gemini (already-supported providers,
see app/llm/factory.py) instead of trying to shrink this further.

Not verified end-to-end in this build environment for the ORIGINAL
reason either: the model weights download from Hugging Face Hub on
first use, and this sandbox has no outbound access to huggingface.co
(confirmed via direct test - a 403 from the network's egress proxy).
Verify with:

    python -m app.cli verify-local-models

from a machine with normal internet access (or via the Render deployment)
before relying on this in production - and specifically watch Render's
memory graph after deploying this change, since that's the actual
question at hand.
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
