# Automated Book Generation System

A production-quality, workflow-driven pipeline for generating books using OpenAI's GPT-4. Built with FastAPI, PostgreSQL, and SQLAlchemy.

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- PostgreSQL running locally (default: `localhost:5432`)
- OpenAI API key

### 1. Create the PostgreSQL database

```sql
CREATE DATABASE book_generator;
```

### 2. Install dependencies

```bash
cd "Media Marson Trial"
pip install -r requirements.txt
```

### 3. Configure environment

Edit `.env` and set your `OPENAI_API_KEY`:

```
OPENAI_API_KEY=sk-your-actual-key-here
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start the server

```bash
python run.py
```

The API will be available at **http://localhost:8000**  
Interactive docs at **http://localhost:8000/docs**

---

## Quick Start (Docker)

```bash
# Set your OpenAI key in .env first
docker-compose up --build
```

---

## Project Structure

```
app/
├── main.py              # FastAPI app, lifespan, middleware, router registration
├── config.py            # Pydantic Settings (reads .env)
├── database.py          # Async SQLAlchemy engine, session factory, dependency
├── models/
│   └── book.py          # SQLAlchemy ORM models (Book, Chapter)
├── schemas/
│   └── book.py          # Pydantic request/response schemas
├── routers/
│   ├── books.py         # Book CRUD + workflow trigger endpoints
│   └── chapters.py      # Chapter CRUD + notes endpoints
├── services/
│   ├── llm_service.py   # OpenAI API wrapper (outline, chapter, summary)
│   └── notification_service.py  # SMTP email notifications
├── workflows/
│   └── book_workflow.py # State-driven workflow engine (3 stages)
└── utils/
    └── file_handler.py  # CSV/Excel parser, .txt/.docx export, outline parser
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/books/` | Upload CSV/Excel to create books |
| POST | `/api/v1/books/single` | Create a single book manually |
| GET | `/api/v1/books/` | List all books |
| GET | `/api/v1/books/{book_id}` | Get book with chapters |
| POST | `/api/v1/books/{book_id}/generate-outline` | Trigger outline generation |
| POST | `/api/v1/books/{book_id}/generate-chapters` | Trigger chapter generation |
| POST | `/api/v1/books/{book_id}/compile` | Compile final book output |
| PATCH | `/api/v1/books/{book_id}/outline-notes` | Update outline review notes |
| PATCH | `/api/v1/books/{book_id}/final-review-notes` | Update final review notes |
| GET | `/api/v1/chapters/{chapter_id}` | Get a chapter |
| PATCH | `/api/v1/chapters/{chapter_id}/notes` | Update chapter notes |
| GET | `/api/v1/chapters/book/{book_id}` | Get all chapters for a book |
| GET | `/api/v1/download/{filename}` | Download generated files |
| GET | `/health` | Health check |

---

## Typical Workflow

```
1. Upload CSV  →  POST /api/v1/books/
2. Generate Outline  →  POST /api/v1/books/{id}/generate-outline
3. Review & Approve  →  PATCH /api/v1/books/{id}/outline-notes
   (set status_outline_notes = "no_notes_needed")
4. Generate Chapters  →  POST /api/v1/books/{id}/generate-chapters
5. (Optional) Add chapter notes  →  PATCH /api/v1/chapters/{id}/notes
6. Set final review  →  PATCH /api/v1/books/{id}/final-review-notes
   (set final_review_notes_status = "no_notes_needed")
7. Compile  →  POST /api/v1/books/{id}/compile
8. Download  →  GET /api/v1/download/book_{id}.docx
```

---

## Sample CSV Format

```csv
title,notes_on_outline_before
"My Book Title","Notes and guidance for the AI to generate the outline"
```

See `sample_books.csv` for examples.
