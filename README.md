# Automated Book Generation System

A production-quality, workflow-driven backend system that automates the entire process of generating books using **OpenAI's GPT-4o**, built with **FastAPI**, **PostgreSQL**, and **SQLAlchemy (async)**. The system implements a multi-stage pipeline: outline generation → human review gate → chapter-by-chapter writing → final compilation into downloadable `.docx` and `.txt` files.

---

## Table of Contents

- [Tech Stack & Why These Choices](#tech-stack--why-these-choices)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Endpoints](#api-endpoints)
- [Workflow (Step-by-Step)](#workflow-step-by-step)
- [Database Schema](#database-schema)
- [Database Screenshots](#database-screenshots)
- [Key Design Decisions](#key-design-decisions)
- [Docker Support](#docker-support)
- [Sample CSV Format](#sample-csv-format)

---

## Tech Stack & Why These Choices

| Technology | Purpose | Why I Chose It |
|---|---|---|
| **FastAPI** | Web framework | Async-native, automatic OpenAPI docs, Pydantic validation, built for high-performance APIs |
| **PostgreSQL** | Database | Production-grade relational DB with native UUID support, ENUM types, ACID compliance — essential for tracking complex workflow states reliably |
| **SQLAlchemy 2.0 (async)** | ORM | Industry-standard Python ORM with full async support via `asyncpg`, type-safe queries, and Alembic migration support |
| **asyncpg** | DB driver | The fastest PostgreSQL driver for Python async — significantly outperforms `psycopg2` in async workloads |
| **OpenAI GPT-4o** | LLM | 128K token context window, high-quality text generation, ideal for long-form book content |
| **Alembic** | DB migrations | Version-controlled schema changes, reproducible across environments |
| **Pydantic v2** | Validation | Request/response validation with automatic serialization, settings management via `.env` |
| **Tenacity** | Retry logic | Robust retry handling for OpenAI API calls (rate limits, timeouts) with exponential backoff |
| **python-docx** | File export | Generates professional `.docx` Word documents from generated book content |
| **Docker** | Containerization | Reproducible deployments, easy setup with `docker-compose` |

### Why PostgreSQL over SQLite or MongoDB?

1. **Workflow state integrity**: Book generation is a multi-stage workflow (outline → review → chapters → compile). PostgreSQL's ACID transactions ensure state transitions are never corrupted — if a chapter generation fails mid-way, the book stays in a consistent state and can be resumed.
2. **Native UUID support**: Every book and chapter uses UUIDs as primary keys, which PostgreSQL handles natively and efficiently.
3. **ENUM types**: PostgreSQL supports native ENUM types for workflow states (`no_notes_needed`, `notes_added`, etc.), enforcing valid state values at the database level.
4. **Concurrency**: PostgreSQL handles concurrent reads/writes properly — multiple books can be generated simultaneously without data corruption.
5. **Production readiness**: This is the same database used in production by companies like Instagram, Spotify, and Discord. Choosing it from the start means zero migration cost when deploying.

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Client     │────▶│   FastAPI    │────▶│   PostgreSQL    │
│  (Postman)   │◀────│   Server     │◀────│   Database      │
└─────────────┘     └──────┬───────┘     └─────────────────┘
                           │
                    ┌──────▼───────┐
                    │  OpenAI API  │
                    │   (GPT-4o)   │
                    └──────────────┘
```

**Flow**: Client sends requests → FastAPI validates & orchestrates → Workflow engine manages state → LLM service calls OpenAI → Results stored in PostgreSQL → Files exported to disk

---

## Project Structure

```
├── app/
│   ├── main.py                    # FastAPI app, lifespan events, CORS, router registration
│   ├── config.py                  # Pydantic Settings (reads .env), cached with @lru_cache
│   ├── database.py                # Async SQLAlchemy engine, session factory, get_db dependency
│   ├── models/
│   │   └── book.py                # SQLAlchemy ORM models (Book, Chapter, NoteStatus enum)
│   ├── schemas/
│   │   └── book.py                # Pydantic request/response schemas
│   ├── routers/
│   │   ├── books.py               # Book CRUD + workflow trigger endpoints
│   │   └── chapters.py            # Chapter CRUD + notes endpoints
│   ├── services/
│   │   ├── llm_service.py         # OpenAI API wrapper with retry logic (outline, chapter, summary)
│   │   └── notification_service.py # SMTP email notifications (optional)
│   ├── workflows/
│   │   └── book_workflow.py       # State-driven 3-stage workflow engine
│   └── utils/
│       └── file_handler.py        # CSV/Excel parser, outline parser, .txt/.docx export
├── alembic/                       # Database migration scripts
│   └── versions/
│       └── 001_initial_schema.py  # Initial tables (books, chapters, enums)
├── output/                        # Generated book files (.txt, .docx)
├── uploads/                       # Uploaded CSV/Excel files
├── screenshots/                   # Database screenshots
├── docker-compose.yml             # Docker Compose for PostgreSQL + API
├── Dockerfile                     # Multi-stage Docker build
├── requirements.txt               # Python dependencies
├── run.py                         # Server entry point
├── sample_books.csv               # Example input file
└── .env                           # Environment variables (API keys, DB config)
```

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **PostgreSQL 14+** (running locally or via Docker)
- **OpenAI API key**

### Option 1: Local Development

```bash
# 1. Clone the repository
git clone https://github.com/Junaid059/Book-Generation-.git
cd Book-Generation-

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create PostgreSQL database
# Open psql or pgAdmin and run:
CREATE DATABASE book_generator;

# 5. Configure environment variables
# Edit .env and set your OpenAI API key:
OPENAI_API_KEY=sk-your-key-here
DATABASE_URL=postgresql+asyncpg://postgres:your_password@localhost:5432/book_generator

# 6. Run database migrations
alembic upgrade head

# 7. Start the server
python run.py
```

The API will be available at **http://localhost:8000**
Interactive Swagger docs at **http://localhost:8000/docs**

### Option 2: Docker

```bash
# Set your OpenAI key in .env first
docker-compose up --build
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/books/` | Upload CSV/Excel to create multiple books |
| `POST` | `/api/v1/books/single` | Create a single book manually |
| `GET` | `/api/v1/books/` | List all books |
| `GET` | `/api/v1/books/{book_id}` | Get book details with chapters |
| `POST` | `/api/v1/books/{book_id}/generate-outline` | Trigger AI outline generation |
| `PATCH` | `/api/v1/books/{book_id}/outline-notes` | Review & approve/revise outline |
| `POST` | `/api/v1/books/{book_id}/generate-chapters` | Trigger AI chapter generation |
| `PATCH` | `/api/v1/books/{book_id}/final-review-notes` | Submit final review notes |
| `POST` | `/api/v1/books/{book_id}/compile` | Compile book into .txt & .docx |
| `GET` | `/api/v1/chapters/{chapter_id}` | Get a specific chapter |
| `PATCH` | `/api/v1/chapters/{chapter_id}/notes` | Update chapter notes |
| `GET` | `/api/v1/chapters/book/{book_id}` | Get all chapters for a book |
| `GET` | `/api/v1/download/{filename}` | Download generated files |
| `GET` | `/health` | Health check |

---

## Workflow (Step-by-Step)

The system follows a **3-stage workflow** with human review gates:

```
Stage 1: OUTLINE GENERATION
  └─▶ POST /api/v1/books/single          (Create book with title & guidance notes)
  └─▶ POST /api/v1/books/{id}/generate-outline   (AI generates chapter outline)
  └─▶ GET  /api/v1/books/{id}            (Review the generated outline)

Stage 2: CHAPTER GENERATION (requires outline approval)
  └─▶ PATCH /api/v1/books/{id}/outline-notes     (Approve: status = "no_notes_needed")
  └─▶ POST  /api/v1/books/{id}/generate-chapters (AI writes each chapter sequentially)
  └─▶ GET   /api/v1/chapters/book/{id}           (Review all generated chapters)

Stage 3: COMPILATION (requires final review)
  └─▶ PATCH /api/v1/books/{id}/final-review-notes (Approve: status = "no_notes_needed")
  └─▶ POST  /api/v1/books/{id}/compile            (Exports .txt and .docx files)
  └─▶ GET   /api/v1/download/book_{id}.docx       (Download the final book)
```

Each stage has a **gate**: the human must review and approve before the next stage can proceed. This ensures quality control at every step.

---

## Database Schema

### `books` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Unique book identifier |
| `title` | TEXT | Book title |
| `notes_on_outline_before` | TEXT | Guidance notes for AI outline generation |
| `notes_on_outline_after` | TEXT | AI-generated outline content |
| `status_outline_notes` | ENUM | Gate status: `no_notes_needed` / `notes_added` |
| `final_review_notes` | TEXT | Final review notes |
| `final_review_notes_status` | ENUM | Gate status for final review |
| `book_output_status` | TEXT | Overall book pipeline status |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last update timestamp |

### `chapters` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Auto-incrementing chapter ID |
| `book_id` | UUID (FK) | Reference to parent book |
| `chapter_number` | INTEGER | Chapter order number |
| `chapter_title` | TEXT | Chapter title |
| `content` | TEXT | Full chapter content (AI-generated) |
| `summary` | TEXT | Chapter summary (AI-generated) |
| `notes` | TEXT | Human review notes |
| `notes_status` | ENUM | Chapter review status |

---

## Database Screenshots

### Books Table — All Generated Books
Shows 3 books stored in PostgreSQL with their UUIDs, titles, and outline guidance notes.

![Books Table](screenshots/db-books-table.png)

### Books Table — Workflow State Columns
Shows the workflow state columns: `notes_on_outline_after` (AI-generated outline), `status_outline_notes` (approval gate), and `final_review_notes_status`.

![Books Columns](screenshots/db-books-columns.png)

### Chapters Table — Generated Chapters
Shows 25 chapters across multiple books, with chapter numbers, titles, and AI-generated content.

![Chapters Table](screenshots/db-chapters-table.png)

### Chapters Table — AI-Generated Summaries
Each chapter has an AI-generated summary for quick review without reading the full content.

![Chapters Summaries](screenshots/db-chapters-summaries.png)

---

## Key Design Decisions

### 1. Async Everything
The entire stack is async — from FastAPI routes to SQLAlchemy queries to OpenAI API calls. This means the server can handle multiple book generation requests concurrently without blocking.

### 2. State-Driven Workflow Engine
Instead of a simple linear pipeline, I implemented a **state machine** with explicit gates. Each stage checks prerequisites before proceeding:
- Chapters can't be generated until the outline is approved
- The book can't be compiled until the final review is done
- If generation fails mid-way, it resumes from where it left off (chapters already generated are preserved)

### 3. Retry Logic with Tenacity
OpenAI API calls use exponential backoff retries for transient errors (rate limits, timeouts), but immediately fail on permanent errors (invalid requests). This prevents wasting API credits on unrecoverable errors.

### 4. Chapter Summaries
After generating each chapter, the system automatically generates a summary. These summaries are used as context when generating subsequent chapters, ensuring narrative consistency across the book.

### 5. Dual Export Format
Books are exported in both `.txt` (universal) and `.docx` (professional formatting) formats simultaneously.

---

## Docker Support

```bash
# Start everything (PostgreSQL + API server)
docker-compose up --build

# Stop
docker-compose down

# Reset database
docker-compose down -v
docker-compose up --build
```

The `docker-compose.yml` includes:
- PostgreSQL 15 container with persistent volume
- FastAPI application container
- Automatic database migration on startup

---

## Sample CSV Format

```csv
title,notes_on_outline_before
"The Art of Simple Living","Write a short self-help book about minimalism and simple living. Target audience: young professionals feeling overwhelmed."
```

See `sample_books.csv` for more examples.

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | (required) |
| `OPENAI_MODEL` | GPT model to use | `gpt-4o` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:junaid@localhost:5432/book_generator` |
| `SMTP_HOST` | Email notification host | (optional) |
| `SMTP_PORT` | Email notification port | (optional) |

---

## Author

**Junaid Khalid** — [GitHub](https://github.com/Junaid059)
