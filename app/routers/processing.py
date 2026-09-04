from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.processing.pipeline import process_articles
from app.schemas.article import ProcessRunResult

router = APIRouter(prefix="/process", tags=["processing"])


@router.post("/run", response_model=ProcessRunResult)
def trigger_processing(
    limit: int = Query(default=20, le=200, description="Max unprocessed articles to handle in this call"),
    db: Session = Depends(get_db),
) -> ProcessRunResult:
    """Synchronous manual trigger for Section 7 stages 3-5 (cluster +
    classify). Capped at `limit` articles per call (default 20, max 200) -
    each article costs two model calls plus a DB round-trip, which is slow
    on a CPU-constrained free-tier instance; processing an unbounded
    backlog in one HTTP request is technically possible (Render's request
    timeout is 100 minutes) but a bad way to find that out interactively.
    Check `remaining_unprocessed` on the response and call again if it's
    still above 0.
    """
    result = process_articles(db, limit=limit)
    return ProcessRunResult(**result.__dict__)
