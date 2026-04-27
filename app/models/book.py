import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, ForeignKey, DateTime, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class NoteStatus(str, enum.Enum):
    yes = "yes"
    no = "no"
    no_notes_needed = "no_notes_needed"


class Book(Base):
    __tablename__ = "books"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    notes_on_outline_before = Column(Text, nullable=True)
    outline = Column(Text, nullable=True)
    notes_on_outline_after = Column(Text, nullable=True)
    status_outline_notes = Column(
        SAEnum(NoteStatus, name="note_status_enum", create_constraint=False),
        nullable=True,
    )
    final_review_notes = Column(Text, nullable=True)
    final_review_notes_status = Column(
        SAEnum(NoteStatus, name="note_status_enum", create_constraint=False),
        nullable=True,
    )
    book_output_status = Column(String(50), nullable=True, default="pending")
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    chapters = relationship(
        "Chapter", back_populates="book", cascade="all, delete-orphan",
        order_by="Chapter.chapter_number",
    )

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}')>"


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number = Column(Integer, nullable=False)
    chapter_title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    chapter_notes = Column(Text, nullable=True)
    chapter_notes_status = Column(
        SAEnum(NoteStatus, name="note_status_enum", create_constraint=False),
        nullable=True,
    )

    book = relationship("Book", back_populates="chapters")

    def __repr__(self):
        return f"<Chapter(id={self.id}, book_id={self.book_id}, chapter_number={self.chapter_number})>"
