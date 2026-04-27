import logging
import os
import uuid
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import get_settings
from app.models.book import Book, Chapter, NoteStatus
from app.schemas.book import (
    BookCreate,
    BookOut,
    BookWithChapters,
    ChapterOut,
    ChapterNotesUpdate,
    OutlineNotesUpdate,
    FinalReviewNotesUpdate,
    UploadResponse,
    WorkflowResponse,
)
from app.utils.file_handler import parse_input_file, ensure_directories
from app.workflows.book_workflow import (
    run_outline_stage,
    run_chapter_stage,
    run_compilation_stage,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/books", tags=["Books"])


# ─── UPLOAD CSV/Excel ─────────────────────────────────────────


@router.post("/", response_model=UploadResponse)
async def create_books_from_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Create books from a CSV or Excel file upload."""
    ensure_directories()

    # Validate file type
    allowed_extensions = {".csv", ".xlsx", ".xls"}
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file_ext}'. Use: {', '.join(allowed_extensions)}",
        )

    # Save uploaded file temporarily
    temp_path = os.path.join(settings.UPLOAD_DIR, f"upload_{uuid.uuid4()}{file_ext}")
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Parse file
        book_entries = parse_input_file(temp_path)

        if not book_entries:
            raise HTTPException(status_code=400, detail="No valid book entries found in file.")

        # Create books
        created_ids = []
        for entry in book_entries:
            book = Book(
                title=entry["title"],
                notes_on_outline_before=entry.get("notes_on_outline_before"),
            )
            db.add(book)
            await db.flush()
            created_ids.append(book.id)

        logger.info(f"Created {len(created_ids)} books from upload")
        return UploadResponse(
            status="success",
            books_created=len(created_ids),
            book_ids=created_ids,
        )
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/single", response_model=BookOut)
async def create_single_book(
    book_data: BookCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a single book manually."""
    book = Book(
        title=book_data.title,
        notes_on_outline_before=book_data.notes_on_outline_before,
    )
    db.add(book)
    await db.flush()
    logger.info(f"Created book: {book.id} - {book.title}")
    return book


# ─── GET BOOK ──────────────────────────────────────────────────


@router.get("/{book_id}", response_model=BookWithChapters)
async def get_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get book details with all chapters."""
    result = await db.execute(
        select(Book).options(selectinload(Book.chapters)).where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.get("/", response_model=list[BookOut])
async def list_books(db: AsyncSession = Depends(get_db)):
    """List all books."""
    result = await db.execute(select(Book).order_by(Book.created_at.desc()))
    books = result.scalars().all()
    return books


# ─── WORKFLOW TRIGGERS ─────────────────────────────────────────


@router.post("/{book_id}/generate-outline", response_model=WorkflowResponse)
async def generate_outline(
    book_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger outline generation for a book."""
    try:
        result = await run_outline_stage(db, book_id)
        return WorkflowResponse(
            status=result["status"],
            message=result["message"],
            book_id=book_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Outline generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Outline generation failed: {str(e)}")


@router.post("/{book_id}/generate-chapters", response_model=WorkflowResponse)
async def generate_chapters(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger chapter generation for a book."""
    try:
        result = await run_chapter_stage(db, book_id)
        return WorkflowResponse(
            status=result["status"],
            message=result["message"],
            book_id=book_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Chapter generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chapter generation failed: {str(e)}")


@router.post("/{book_id}/compile", response_model=WorkflowResponse)
async def compile_book(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger final compilation of the book."""
    try:
        result = await run_compilation_stage(db, book_id)
        return WorkflowResponse(
            status=result["status"],
            message=result["message"],
            book_id=book_id,
            detail=str(result.get("files", "")),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Compilation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Compilation failed: {str(e)}")


# ─── NOTES UPDATE ENDPOINTS ───────────────────────────────────


@router.patch("/{book_id}/outline-notes", response_model=BookOut)
async def update_outline_notes(
    book_id: uuid.UUID,
    notes: OutlineNotesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update outline review notes and status."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book.notes_on_outline_after = notes.notes_on_outline_after
    book.status_outline_notes = notes.status_outline_notes
    await db.flush()

    logger.info(f"Updated outline notes for book {book_id}: status={notes.status_outline_notes}")
    return book


@router.patch("/{book_id}/final-review-notes", response_model=BookOut)
async def update_final_review_notes(
    book_id: uuid.UUID,
    notes: FinalReviewNotesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update final review notes and status."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    book.final_review_notes = notes.final_review_notes
    book.final_review_notes_status = notes.final_review_notes_status
    await db.flush()

    logger.info(f"Updated final review notes for book {book_id}")
    return book
