import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from quant_system.shariah.api.v1.router import api_router
from quant_system.shariah.core.config import settings
from quant_system.shariah.db.seed_data import seed_database
from quant_system.shariah.db.session import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager: initializes database and pre-seeds dataset on startup."""
    logger.info("Initializing Halal Investment Engine...")

    # Check if companies are seeded
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table' AND name='companies';"
        )
        table_exists = cursor.fetchone()["cnt"] > 0

        count = 0
        if table_exists:
            cursor.execute("SELECT COUNT(*) as cnt FROM companies;")
            count = cursor.fetchone()["cnt"]
        conn.close()

        if count == 0:
            logger.info("No companies found in database. Running seed data pipeline...")
            seed_count = seed_database()
            logger.info(f"Database successfully seeded with {seed_count} companies.")
        else:
            logger.info(f"Database verified with {count} pre-seeded companies.")
    except Exception as e:
        logger.warning(
            f"Database check encountered exception: {e}. Executing seed_database() to ensure integrity..."
        )
        seed_database()

    logger.info("Halal Investment Engine startup complete and ready for queries.")
    yield
    logger.info("Shutting down Halal Investment Engine.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="High-performance, dual-standard (AAOIFI & TASIS) Shariah compliance screening and wealth engine for Indian equities.",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration allowing Flutter Web, Desktop, and Mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
STATIC_INDEX_PATH = os.path.join(STATIC_DIR, "index.html")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")

if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/", summary="Web Application Client", response_class=HTMLResponse)
async def web_client() -> Response:
    """Serves the Apple-Grade Halal Investment Web Application."""
    if os.path.exists(STATIC_INDEX_PATH):
        return FileResponse(STATIC_INDEX_PATH)
    return HTMLResponse(
        "<h1>Halal Invest India API is Online</h1><p>Visit <a href='/docs'>/docs</a> for API.</p>"
    )


@app.get("/manifest.json", summary="PWA Web App Manifest")
async def manifest() -> Response:
    manifest_path = os.path.join(STATIC_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return HTMLResponse("{}", media_type="application/json")


@app.get("/sw.js", summary="PWA Service Worker")
async def service_worker() -> Response:
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    if os.path.exists(sw_path):
        return FileResponse(sw_path, media_type="application/javascript")
    return HTMLResponse("", media_type="application/javascript")


@app.get("/status", summary="Service Health Status")
async def status() -> dict[str, Any]:
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("quant_system.shariah.main:app", host="0.0.0.0", port=8000, reload=True)
