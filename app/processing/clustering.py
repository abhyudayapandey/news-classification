"""Section 7 stage 3: group same-story articles across outlets.

Incremental nearest-neighbor clustering, not HDBSCAN or similar batch
algorithms: articles arrive continuously via ingestion, not as one static
batch to cluster all at once, so an incremental "does this new article
belong to an existing cluster?" check fits the actual data flow better -
HDBSCAN would mean re-clustering everything from scratch on every run to
stay correct. At POC scale (tens of articles per run), the extra
per-article query cost this trades for is negligible, and it avoids adding
scikit-learn/scipy as dependencies. pgvector's `<=>` cosine-distance
operator does the similarity search directly in SQL, unindexed - fine at
this scale, and avoids needing an ivfflat/hnsw index (which also requires
picking a fixed list size/fit data upfront, more tuning than a POC needs).
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Article, StoryCluster


def find_or_create_cluster(db: Session, article: Article) -> tuple[int, bool]:
    """Returns (cluster_id, is_new_cluster). is_new_cluster matters to the
    caller for Section 4.3's re-evaluation trigger: joining an *existing*
    cluster with an establishment-relevant classification flags the whole
    cluster, but starting a brand new cluster does not (there's nothing
    else in it yet to re-flag).
    """
    if article.embedding is None:
        raise ValueError(f"Article {article.id} has no embedding yet - cannot cluster.")

    window = timedelta(hours=settings.clustering_time_window_hours)
    window_start = article.published_at - window
    window_end = article.published_at + window

    stmt = (
        select(Article.cluster_id, Article.embedding.cosine_distance(article.embedding).label("distance"))
        .where(
            Article.id != article.id,
            Article.cluster_id.is_not(None),
            Article.embedding.is_not(None),
            Article.duplicate_of_id.is_(None),
            Article.published_at.between(window_start, window_end),
        )
        .order_by("distance")
        .limit(1)
    )
    nearest = db.execute(stmt).first()

    if nearest is not None:
        cluster_id, distance = nearest
        similarity = 1 - distance
        if similarity >= settings.clustering_similarity_threshold:
            return cluster_id, False

    cluster = StoryCluster()
    db.add(cluster)
    db.flush()  # assigns cluster.id
    return cluster.id, True
