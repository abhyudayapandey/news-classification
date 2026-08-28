from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.processing.pipeline import process_articles
from app.schemas.article import ProcessRunResult

router = APIRouter(prefix="/process", tags=["processing"])


@router.post("/run", response_model=ProcessRunResult)
def trigger_processing(db: Session = Depends(get_db)) -> ProcessRunResult:
    """Synchronous manual trigger for Section 7 stages 3-5 (cluster +
    classify) over every unprocessed article. Fine at POC scale; would need
    a background task/queue if article volume grows, same caveat as
    /ingest/run.
    """
    result = process_articles(db)
    return ProcessRunResult(**result.__dict__)
