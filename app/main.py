from fastapi import FastAPI

from app.routers import articles, clusters, health, ingestion, processing

app = FastAPI(
    title="News Framing Platform API",
    description="Phase 1: ingestion foundation. Phase 2: clustering + classification. "
    "Admin/end-user views land in Phase 3.",
    version="0.2.0",
)

app.include_router(health.router)
app.include_router(articles.router)
app.include_router(ingestion.router)
app.include_router(processing.router)
app.include_router(clusters.router)
