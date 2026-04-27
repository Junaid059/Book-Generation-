import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.book import Chapter
from app.schemas.book import ChapterOut, ChapterNotesUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chapters", tags=["Chapters"])


@router.get("/{chapter_id}", response_model=ChapterOut)
async def get_chapter(chapter_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single chapter by ID."""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@router.patch("/{chapter_id}/notes", response_model=ChapterOut)
async def update_chapter_notes(
    chapter_id: int,
    notes: ChapterNotesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update chapter notes and status for human-in-the-loop review."""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    chapter.chapter_notes = notes.chapter_notes
    chapter.chapter_notes_status = notes.chapter_notes_status
    await db.flush()

    logger.info(f"Updated notes for chapter {chapter_id}: status={notes.chapter_notes_status}")
    return chapter


@router.get("/book/{book_id}", response_model=list[ChapterOut])
async def get_chapters_by_book(book_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all chapters for a specific book."""
    result = await db.execute(
        select(Chapter)
        .where(Chapter.book_id == book_id)
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()
    return chapters
