"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL to avoid SQLAlchemy enum auto-creation conflicts
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE note_status_enum AS ENUM ('yes', 'no', 'no_notes_needed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id UUID PRIMARY KEY,
            title TEXT NOT NULL,
            notes_on_outline_before TEXT,
            outline TEXT,
            notes_on_outline_after TEXT,
            status_outline_notes note_status_enum,
            final_review_notes TEXT,
            final_review_notes_status note_status_enum,
            book_output_status VARCHAR(50) DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS chapters (
            id SERIAL PRIMARY KEY,
            book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            chapter_number INTEGER NOT NULL,
            chapter_title TEXT,
            content TEXT,
            summary TEXT,
            chapter_notes TEXT,
            chapter_notes_status note_status_enum
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chapters;")
    op.execute("DROP TABLE IF EXISTS books;")
    op.execute("DROP TYPE IF EXISTS note_status_enum;")
