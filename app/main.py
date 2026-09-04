from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from app.auth.session import Forbidden, NotAuthenticated
from app.config import settings
from app.routers import admin_data, admin_ui, articles, clusters, health, ingestion, processing, queue

app = FastAPI(
    title="News Framing Platform API",
    description="Phase 1: ingestion foundation. Phase 2: clustering + classification. "
    "Phase 3: admin/super-admin review UI.",
    version="0.3.0",
)

# https_only=False in development only, so local http://localhost testing
# isn't locked out - Render (and any real deployment) serves over HTTPS,
# where this should be True so the session cookie is never sent in the
# clear. same_site="lax" is the practical, no-extra-dependency CSRF
# mitigation for this POC - see README's Phase 3 section for why full CSRF
# tokens weren't built for an internal 2-3-user tool.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=settings.app_env == "production",
    same_site="lax",
)

app.include_router(health.router)
app.include_router(articles.router)
app.include_router(ingestion.router)
app.include_router(processing.router)
app.include_router(clusters.router)
app.include_router(admin_data.router)
app.include_router(queue.router)
app.include_router(admin_ui.router)


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated) -> RedirectResponse:
    return RedirectResponse("/admin/login", status_code=303)


@app.exception_handler(Forbidden)
async def forbidden_handler(request: Request, exc: Forbidden) -> HTMLResponse:
    return HTMLResponse("<h1>403 Forbidden</h1><p>Super admin access required.</p>", status_code=403)
