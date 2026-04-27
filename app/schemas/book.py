import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field


class NoteStatusEnum(str, Enum):
    yes = "yes"
    no = "no"
    no_notes_needed = "no_notes_needed"


# ── Book Schemas ──


class BookCreate(BaseModel):
    title: str
    notes_on_outline_before: Optional[str] = None


class BookOut(BaseModel):
    id: uuid.UUID
    title: str
    notes_on_outline_before: Optional[str] = None
    outline: Optional[str] = None
    notes_on_outline_after: Optional[str] = None
    status_outline_notes: Optional[NoteStatusEnum] = None
    final_review_notes: Optional[str] = None
    final_review_notes_status: Optional[NoteStatusEnum] = None
    book_output_status: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BookWithChapters(BookOut):
    chapters: List["ChapterOut"] = []

    model_config = {"from_attributes": True}


class OutlineNotesUpdate(BaseModel):
    notes_on_outline_after: Optional[str] = None
    status_outline_notes: NoteStatusEnum


class FinalReviewNotesUpdate(BaseModel):
    final_review_notes: Optional[str] = None
    final_review_notes_status: NoteStatusEnum


# ── Chapter Schemas ──


class ChapterOut(BaseModel):
    id: int
    book_id: uuid.UUID
    chapter_number: int
    chapter_title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    chapter_notes: Optional[str] = None
    chapter_notes_status: Optional[NoteStatusEnum] = None

    model_config = {"from_attributes": True}


class ChapterNotesUpdate(BaseModel):
    chapter_notes: Optional[str] = None
    chapter_notes_status: NoteStatusEnum


# ── Workflow Response ──


class WorkflowResponse(BaseModel):
    status: str
    message: str
    book_id: Optional[uuid.UUID] = None
    detail: Optional[str] = None


# ── Upload Response ──


class UploadResponse(BaseModel):
    status: str
    books_created: int
    book_ids: List[uuid.UUID]
