"""Fixed technical constants - not user-configurable via .env because
changing them has structural consequences (e.g. EMBEDDING_DIM is baked into
the articles.embedding column type and would need a migration to change).
"""

# Output dimension of sentence-transformers/all-MiniLM-L6-v2, the local
# embedding model (see app/llm/local_embedding.py). If LOCAL_EMBEDDING_MODEL
# is ever changed to a model with a different output dimension, this must
# change too, and a migration is needed to resize the articles.embedding
# column - it is not read from config on purpose, to make that dependency
# explicit rather than silently mismatched.
EMBEDDING_DIM = 384
