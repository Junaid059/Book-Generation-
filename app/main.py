import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import books, chapters
from app.utils.file_handler import ensure_directories

settings = get_settings()

# ── Logging ──

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting Book Generation System...")
    ensure_directories()
    await init_db()
    logger.info("Database initialized.")
    yield
    logger.info("Shutting down Book Generation System.")


# ── App ──

app = FastAPI(
    title="Automated Book Generation System",
    description=(
        "A workflow-driven pipeline for generating books using LLMs. "
        "Supports outline generation, chapter-by-chapter writing with context continuity, "
        "human-in-the-loop review, and final compilation to .txt/.docx."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──

app.include_router(books.router, prefix="/api/v1")
app.include_router(chapters.router, prefix="/api/v1")


# ── Health Check ──

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "Book Generation System"}


# ── Download Endpoint ──

@app.get("/api/v1/download/{filename}", tags=["Downloads"])
async def download_file(filename: str):
    """Download a generated book file."""
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(settings.OUTPUT_DIR, safe_filename)

    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type="application/octet-stream",
    )
