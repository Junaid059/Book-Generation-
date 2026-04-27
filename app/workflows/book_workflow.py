import logging
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.book import Book, Chapter, NoteStatus
from app.services import llm_service
from app.services.notification_service import (
    notify_outline_ready,
    notify_chapter_notes_needed,
    notify_final_draft_compiled,
    notify_workflow_paused,
)
from app.utils.file_handler import (
    parse_outline_to_chapters,
    export_book_txt,
    export_book_docx,
)

logger = logging.getLogger(__name__)


async def _get_book(db: AsyncSession, book_id: uuid.UUID) -> Book:
    """Fetch book with chapters or raise."""
    result = await db.execute(
        select(Book).options(selectinload(Book.chapters)).where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise ValueError(f"Book not found: {book_id}")
    return book


# ═══════════════════════════════════════════════════════════════
# STAGE 1: OUTLINE GENERATION
# ═══════════════════════════════════════════════════════════════

async def run_outline_stage(db: AsyncSession, book_id: uuid.UUID) -> dict:
    """
    Generate book outline.
    Precondition: notes_on_outline_before must exist.
    Post: sets outline, notifies for review.
    """
    book = await _get_book(db, book_id)

    # Gate check: need notes before generating outline
    if not book.notes_on_outline_before:
        reason = "Cannot generate outline: 'notes_on_outline_before' is empty."
        notify_workflow_paused(book.title, str(book.id), reason)
        return {"status": "paused", "message": reason}

    # Already has an outline? Regenerate only if notes_on_outline_after exist
    if book.outline and book.notes_on_outline_after:
        logger.info(f"Regenerating outline with post-notes for book {book_id}")
        combined_notes = (
            f"Original notes:\n{book.notes_on_outline_before}\n\n"
            f"Revision notes:\n{book.notes_on_outline_after}"
        )
        outline = await llm_service.generate_outline(book.title, combined_notes)
    elif book.outline:
        return {
            "status": "already_generated",
            "message": "Outline already generated. Add notes_on_outline_after to regenerate.",
        }
    else:
        outline = await llm_service.generate_outline(book.title, book.notes_on_outline_before)

    book.outline = outline
    book.book_output_status = "outline_generated"
    await db.flush()

    notify_outline_ready(book.title, str(book.id))

    return {"status": "completed", "message": "Outline generated successfully."}


def check_outline_gate(book: Book) -> dict | None:
    """
    Check if we can proceed past the outline stage.
    Returns None if we can proceed, or a status dict if blocked.
    """
    if not book.outline:
        return {"status": "blocked", "message": "Outline not yet generated."}

    status = book.status_outline_notes

    if status == NoteStatus.no_notes_needed:
        return None  # Proceed

    if status == NoteStatus.yes:
        if book.notes_on_outline_after:
            return None  # Notes provided, can proceed
        return {"status": "waiting", "message": "Waiting for outline review notes."}

    if status == NoteStatus.no or status is None:
        return {
            "status": "paused",
            "message": "Workflow paused. Set status_outline_notes to 'yes' or 'no_notes_needed' to proceed.",
        }

    return {"status": "paused", "message": "Unknown outline note status."}


# ═══════════════════════════════════════════════════════════════
# STAGE 2: CHAPTER GENERATION
# ═══════════════════════════════════════════════════════════════

async def run_chapter_stage(db: AsyncSession, book_id: uuid.UUID) -> dict:
    """
    Generate all chapters sequentially, maintaining context continuity.
    """
    book = await _get_book(db, book_id)

    # Gate check: outline must be approved
    gate_result = check_outline_gate(book)
    if gate_result:
        if gate_result["status"] == "paused":
            notify_workflow_paused(book.title, str(book.id), gate_result["message"])
        return gate_result

    # Parse outline into chapters
    chapter_defs = parse_outline_to_chapters(book.outline)
    if not chapter_defs:
        return {"status": "error", "message": "Could not parse any chapters from the outline."}

    # Find which chapters are already generated
    existing_chapters = {ch.chapter_number: ch for ch in book.chapters}

    for ch_def in chapter_defs:
        ch_num = ch_def["chapter_number"]
        ch_title = ch_def["chapter_title"]

        # Skip if already generated and no pending notes
        existing = existing_chapters.get(ch_num)
        if existing and existing.content:
            # Check if chapter has pending notes that need regeneration
            if existing.chapter_notes_status == NoteStatus.yes and existing.chapter_notes:
                logger.info(f"Regenerating chapter {ch_num} with notes")
            elif existing.chapter_notes_status == NoteStatus.yes and not existing.chapter_notes:
                notify_chapter_notes_needed(book.title, str(book.id), ch_num)
                return {
                    "status": "waiting",
                    "message": f"Waiting for notes on chapter {ch_num}.",
                }
            else:
                continue  # Already generated, skip

        # Build context from previous chapter summaries
        summaries = []
        for prev_ch in sorted(book.chapters, key=lambda c: c.chapter_number):
            if prev_ch.chapter_number < ch_num and prev_ch.summary:
                summaries.append(
                    f"Chapter {prev_ch.chapter_number} ({prev_ch.chapter_title or ''}):\n"
                    f"{prev_ch.summary}"
                )
        previous_summaries = "\n\n".join(summaries)

        # Get chapter-specific notes
        chapter_notes = existing.chapter_notes if existing else None

        # Generate chapter content
        content = await llm_service.generate_chapter(
            title=book.title,
            outline=book.outline,
            chapter_number=ch_num,
            chapter_title=ch_title,
            previous_summaries=previous_summaries,
            chapter_notes=chapter_notes,
        )

        # Generate summary for context continuity
        summary = await llm_service.summarize_chapter(content)

        if existing:
            existing.content = content
            existing.summary = summary
            existing.chapter_title = ch_title
            if existing.chapter_notes_status == NoteStatus.yes:
                existing.chapter_notes_status = NoteStatus.no_notes_needed
        else:
            chapter = Chapter(
                book_id=book.id,
                chapter_number=ch_num,
                chapter_title=ch_title,
                content=content,
                summary=summary,
            )
            db.add(chapter)
            book.chapters.append(chapter)

        await db.flush()
        logger.info(f"Chapter {ch_num} generated for book {book_id}")

    book.book_output_status = "chapters_generated"
    await db.flush()

    return {
        "status": "completed",
        "message": f"All {len(chapter_defs)} chapters generated successfully.",
    }


# ═══════════════════════════════════════════════════════════════
# STAGE 3: FINAL COMPILATION
# ═══════════════════════════════════════════════════════════════

async def run_compilation_stage(db: AsyncSession, book_id: uuid.UUID) -> dict:
    """
    Compile all chapters into final .txt and .docx output.
    """
    book = await _get_book(db, book_id)

    if not book.chapters:
        return {"status": "error", "message": "No chapters found. Generate chapters first."}

    # Gate check: final review
    review_status = book.final_review_notes_status

    if review_status == NoteStatus.no or review_status is None:
        notify_workflow_paused(
            book.title, str(book.id),
            "Final review notes status not set. Set to 'no_notes_needed' to compile.",
        )
        return {
            "status": "paused",
            "message": "Set final_review_notes_status to 'no_notes_needed' or 'yes' (with notes) to compile.",
        }

    if review_status == NoteStatus.yes and not book.final_review_notes:
        return {
            "status": "waiting",
            "message": "Waiting for final review notes.",
        }

    # Prepare chapter data for export
    chapters_data = [
        {
            "chapter_number": ch.chapter_number,
            "chapter_title": ch.chapter_title or f"Chapter {ch.chapter_number}",
            "content": ch.content or "",
        }
        for ch in sorted(book.chapters, key=lambda c: c.chapter_number)
    ]

    # Export files
    txt_path = export_book_txt(str(book.id), book.title, chapters_data)
    docx_path = export_book_docx(str(book.id), book.title, chapters_data)

    book.book_output_status = "compiled"
    await db.flush()

    notify_final_draft_compiled(book.title, str(book.id))

    return {
        "status": "completed",
        "message": "Book compiled successfully.",
        "files": {"txt": txt_path, "docx": docx_path},
    }
