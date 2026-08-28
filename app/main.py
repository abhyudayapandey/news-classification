from fastapi import FastAPI

from app.routers import articles, health, ingestion

app = FastAPI(
    title="News Framing Platform API",
    description="Phase 1: ingestion foundation. Clustering, classification, "
    "and the admin/end-user views land in later phases.",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(articles.router)
app.include_router(ingestion.router)
