from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, SQLAlchemyError

from app.api.v1.routes import (
    ai_import,
    alerts,
    auth,
    contractors,
    dashboard,
    dispatch,
    fabric_designs,
    fabric_inventory,
    fabric_orders,
    fabric_receipts,
    fabric_shortages,
    packing,
    notifications,
    fabric_meter_receipts,
    pdf_reports,
    pieces_receipts,
    product_fabric_lines,
    products,
    purchase_orders,
    reminders,
    stage_allocations,
    stage_progress,
    vehicles,
    voice,
    voice_ws,
)
from app.core.config import settings
from app.core.database import create_all_tables
from app.services.exceptions import DomainError
from app.services.scheduler import shutdown_scheduler, start_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Provision schema on first boot (idempotent — no-op once the file exists).
    await create_all_tables()
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    if isinstance(exc, OperationalError):
        return JSONResponse(
            status_code=503,
            content={"detail": "Database is unavailable. Check DATABASE_URL and PostgreSQL credentials."},
        )
    if isinstance(exc, (DataError, IntegrityError)):
        return JSONResponse(
            status_code=400,
            content={"detail": "Database rejected the request. Check payload values and run pending migrations."},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Unexpected database error."},
    )


app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
app.include_router(products.router, prefix=f"{settings.api_v1_prefix}/products", tags=["products"])
app.include_router(product_fabric_lines.router, prefix=f"{settings.api_v1_prefix}/product-fabric-lines", tags=["product-fabric-lines"])
app.include_router(pieces_receipts.router, prefix=f"{settings.api_v1_prefix}/pieces-receipts", tags=["pieces-receipts"])
app.include_router(fabric_meter_receipts.router, prefix=f"{settings.api_v1_prefix}/fabric-meter-receipts", tags=["fabric-meter-receipts"])
app.include_router(ai_import.router, prefix=f"{settings.api_v1_prefix}/ai-import", tags=["ai-import"])
app.include_router(fabric_designs.router, prefix=f"{settings.api_v1_prefix}/fabric-designs", tags=["fabric-designs"])
app.include_router(purchase_orders.router, prefix=f"{settings.api_v1_prefix}/purchase-orders", tags=["purchase-orders"])
app.include_router(fabric_inventory.router, prefix=f"{settings.api_v1_prefix}/fabric-inventory", tags=["fabric-inventory"])
app.include_router(fabric_receipts.router, prefix=f"{settings.api_v1_prefix}/fabric-receipts", tags=["fabric-receipts"])
app.include_router(fabric_shortages.router, prefix=f"{settings.api_v1_prefix}/fabric-shortages", tags=["fabric-shortages"])
app.include_router(fabric_orders.router, prefix=f"{settings.api_v1_prefix}/fabric-operations", tags=["fabric-operations"])
app.include_router(contractors.router, prefix=f"{settings.api_v1_prefix}/contractors", tags=["contractors"])
app.include_router(stage_allocations.router, prefix=f"{settings.api_v1_prefix}/stage-allocations", tags=["stage-allocations"])
app.include_router(stage_progress.router, prefix=f"{settings.api_v1_prefix}/stage-progress", tags=["stage-progress"])
app.include_router(packing.router, prefix=f"{settings.api_v1_prefix}/packing", tags=["packing"])
app.include_router(dispatch.router, prefix=f"{settings.api_v1_prefix}/dispatch", tags=["dispatch"])
app.include_router(vehicles.router, prefix=f"{settings.api_v1_prefix}/vehicles", tags=["vehicles"])
app.include_router(notifications.router, prefix=f"{settings.api_v1_prefix}/notifications", tags=["notifications"])
app.include_router(alerts.router, prefix=f"{settings.api_v1_prefix}/alerts", tags=["alerts"])
app.include_router(reminders.router, prefix=f"{settings.api_v1_prefix}/reminders", tags=["reminders"])
app.include_router(pdf_reports.router, prefix=f"{settings.api_v1_prefix}/reports/pdf", tags=["pdf-reports"])
app.include_router(dashboard.router, prefix=f"{settings.api_v1_prefix}/dashboard", tags=["dashboard"])
app.include_router(voice.router, prefix=f"{settings.api_v1_prefix}/voice", tags=["voice"])
app.include_router(voice_ws.router, prefix=f"{settings.api_v1_prefix}/voice", tags=["voice"])


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"app": "ok"}


# ---------------------------------------------------------------------------
# Frontend static serving (production).
#
# In production the React build (`vite build` → `dist/`) is copied to /app/static
# inside the container. We mount it so the whole app — UI + API — lives at a
# single URL.
#
# - `/api/v1/*` → already handled by the routers above.
# - `/health`   → JSON, for the load-balancer health check.
# - Anything else → either a static file, or fall through to index.html so
#                   client-side React Router can take over.
# ---------------------------------------------------------------------------

import pathlib
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_FRONTEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "static"

if _FRONTEND_DIR.exists():
    # Assets / icons live under fixed subpaths — mount them as proper
    # StaticFiles so caching headers + range requests behave correctly.
    for sub in ("assets", "icons"):
        if (_FRONTEND_DIR / sub).is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=_FRONTEND_DIR / sub), name=sub)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_catch_all(full_path: str) -> FileResponse:
        """Serve a top-level static file if it exists, else the SPA shell.

        React Router handles client-side navigation for paths like /inventory
        and /pos/create — those paths don't exist on disk, so we hand back
        index.html and let React render.
        """
        # Never let this swallow the API.
        if full_path.startswith("api/") or full_path == "health":
            raise HTTPException(status_code=404)
        candidate = _FRONTEND_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIR / "index.html")
