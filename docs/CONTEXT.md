# Unified Customer Complaint Communication Dashboard

## Overview

Backend system that collects customer complaints from multiple channels (web, email, social media), classifies them using AI (GPT-4o), detects duplicates via semantic vector search (pgvector), tracks SLA deadlines by severity, generates AI draft responses, and provides trend analytics.

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.11+ |
| Framework | FastAPI 0.111+ (async) |
| Server | Uvicorn 0.30+ |
| ORM | SQLAlchemy 2.0+ (async) |
| Database | PostgreSQL 16+ with pgvector 0.3+ |
| Driver | asyncpg (async), psycopg2-binary (sync fallback) |
| AI | OpenAI GPT-4o (classification/draft), text-embedding-3-small (embeddings) |
| HTTP Client | httpx 0.27+ (async, for OpenAI calls) |
| Validation | Pydantic / pydantic-settings |
| Auth libs | python-jose, passlib/bcrypt (not yet wired) |
| Testing | pytest, pytest-asyncio |
| Linting | Ruff (line-length 120) |

## Quick Start

```bash
cd backend
cp .env.example .env   # edit with your DB + OpenAI keys
uvicorn app.main:app --reload
```

Tables auto-create on startup. No migration tool configured yet.

## Directory Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI entry point, lifespan, CORS, router includes
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (reads .env)
│   │   └── database.py            # Async engine + session factory + get_db dependency
│   ├── models/
│   │   └── models.py              # 6 SQLAlchemy ORM models (all in one file)
│   ├── schemas/
│   │   └── schemas.py             # Pydantic request/response models (all in one file)
│   ├── routers/
│   │   ├── complaints.py          # CRUD + classify + escalate + duplicates + audit
│   │   ├── messages.py            # Messages CRUD + AI draft + draft approval
│   │   ├── users.py               # Users CRUD
│   │   ├── analytics.py           # Trend analytics
│   │   └── sla.py                 # SLA summary + per-complaint SLA
│   └── services/
│       ├── classification.py      # OpenAI GPT-4o classification
│       ├── draft_generator.py     # OpenAI GPT-4o draft response generation
│       ├── duplicate_detector.py  # pgvector cosine similarity search
│       └── embeddings.py          # OpenAI text-embedding-3-small
├── .env                           # Actual config (DB URLs, OpenAI keys)
├── .env.example                   # Template
└── pyproject.toml                 # Dependencies, Ruff config
```

## Key Conventions & Patterns

- **Async everywhere**: FastAPI async routes, async SQLAlchemy sessions, async httpx for OpenAI
- **Auto table creation**: `Base.metadata.create_all` runs on app startup (no Alembic)
- **Per-request DB sessions**: `get_db()` async generator via FastAPI dependencies
- **Separation of concerns**: Routers → HTTP handling, Services → business logic, Models → DB, Schemas → validation
- **Defensive AI fallbacks**: Every OpenAI call is wrapped in try/except with sensible defaults
- **Audit logging**: All meaningful complaint actions logged to `audit_log` table
- **JSON key_issues**: Stored as serialized JSON string in Text column (not JSONB)
- **Raw pgvector SQL**: Duplicate detection uses raw SQL with `<=>` cosine distance operator
- **OpenAI-compatible**: `llm_base_url` config allows swapping to any OpenAI-compatible API
- **No auth middleware yet**: CORS allows all origins; JWT libs included but not wired
- **No frontend exists yet**: Pure API backend

## Enums

| Enum | Values |
|---|---|
| ComplaintType | billing, service, product_defect, delay, other |
| Severity | critical, high, medium, low |
| Sentiment | negative, neutral, positive |
| ComplaintStatus | open, in_progress, resolved, closed, escalated |
| Channel | email, web_form, social_media, call_centre, walk_in, csv_import |
| MessageDirection | inbound, outbound, internal |

## Configuration (backend/app/core/config.py)

| Variable | Default | Description |
|---|---|---|
| DATABASE_URL | (required) | Async PostgreSQL URL (asyncpg) |
| SYNCHRONOUS_DATABASE_URL | (required) | Sync PostgreSQL URL (psycopg2) |
| LLM_API_KEY | (required) | OpenAI API key |
| LLM_MODEL | gpt-4o | Model for classification/draft |
| EMBEDDING_MODEL | text-embedding-3-small | Model for embeddings |
| EMBEDDING_DIMENSIONS | 1536 | Vector dimensions |
| SIMILARITY_THRESHOLD | 0.85 | Cosine similarity threshold for duplicates |
| LLM_BASE_URL | https://api.openai.com/v1 | Base URL (swap for Azure/local) |

## Services Overview

- **classification.py** (`classify_complaint`): Sends title+description to GPT-4o -> returns type, severity, sentiment, product, key_issues, confidence. Falls back to other/medium/0.0 if AI fails.
- **draft_generator.py** (`generate_draft_response`): Sends complaint context to GPT-4o -> returns empathetic draft response.
- **embeddings.py** (`generate_embedding`): Sends text to OpenAI embeddings API -> returns 1536-dim vector.
- **duplicate_detector.py** (`find_duplicates`): Queries pgvector with cosine distance (`<=>`) to find similar complaints. Also contains `compute_sla_due_at` for SLA deadline calculation based on severity.

## SLA Deadlines

| Severity | Response Deadline |
|---|---|
| critical | 1 hour |
| high | 4 hours |
| medium | 8 hours |
| low | 24 hours |
