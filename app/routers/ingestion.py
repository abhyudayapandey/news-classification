from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.ingestion.pipeline import run_ingestion
from app.schemas.article import IngestOutletResult

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/run", response_model=list[IngestOutletResult])
def trigger_ingestion(db: Session = Depends(get_db)) -> list[IngestOutletResult]:
    """Synchronous manual trigger. Fine at POC scale (a handful of feeds);
    would need to move to a background task/queue if outlet count grows.
    """
    results = run_ingestion(db)
    return [IngestOutletResult(**r.__dict__) for r in results]
