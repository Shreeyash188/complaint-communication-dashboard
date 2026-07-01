# Architecture

## System Overview

```
[External Sources / Future React Frontend]
              |
              | REST API (JSON)
              v
    +---------------------+
    |   FastAPI App         |  Uvicorn ASGI server
    |   (app/main.py)       |
    +----------+----------+
               |
    +----------+----------+
    |   Routers             |  Parse requests, call services + DB
    |   (5 files)           |
    +----------+----------+
               |
    +----------+----------+
    |   Services            |  Business logic / AI integration
    |   (4 files)           |
    +----------+----------+
               |
    +----------+----------+
    |   OpenAI API          |  GPT-4o (classification, drafting)
    |   (httpx calls)       |  text-embedding-3-small (embeddings)
    +----------+----------+
               |
    +----------+----------+
    |   SQLAlchemy 2.0      |  Async ORM
    +----------+----------+
               |
    +----------+----------+
    |   PostgreSQL 16       |  With pgvector extension
    |   (asyncpg)           |  6 tables
    +---------------------+
```

## Layer Responsibilities

### 1. Entry Point (`app/main.py`)
- Creates FastAPI app with title/description/version
- Lifespan context manager: creates tables on startup, disposes engine on shutdown
- Configures CORS (all origins allowed)
- Registers 5 routers under `/api` prefix
- Exposes `/api/health` endpoint

### 2. Routers (`app/routers/`)
- **complaints.py** (421 lines): Main CRUD + classification + duplicate detection + escalation + audit
- **messages.py** (121 lines): Message CRUD + AI draft generation + draft approval
- **users.py** (74 lines): User CRUD (email uniqueness check)
- **analytics.py** (57 lines): Trend analysis with grouping/filtering
- **sla.py** (72 lines): SLA summary stats + per-complaint SLA

Each router receives `db: AsyncSession` via FastAPI dependency injection and uses it in `async with db as session:` blocks.

### 3. Services (`app/services/`)
- **classification.py**: Calls GPT-4o with structured JSON prompt to classify complaint field values
- **draft_generator.py**: Calls GPT-4o to generate customer-facing draft responses
- **embeddings.py**: Calls OpenAI Embeddings API to produce 1536-dim vectors
- **duplicate_detector.py**: Executes raw pgvector SQL for cosine similarity search

### 4. Core (`app/core/`)
- **config.py**: Pydantic `Settings` class, loads from `.env` file
- **database.py**: Creates async engine, `async_sessionmaker`, and `get_db()` dependency

### 5. Models (`app/models/models.py`)
All 6 SQLAlchemy ORM models: `User`, `Complaint`, `CommunicationThread`, `SlaTracking`, `ComplaintEmbedding`, `AuditLog`

### 6. Schemas (`app/schemas/schemas.py`)
Pydantic models for request validation and response serialization.

## Data Flow: Creating a Complaint

```
POST /api/complaints { title, description, customer_name, customer_email, channel }
       |
       v
[1] Create Complaint row in DB
       |
       v
[2] classify_complaint(title, description) -> OpenAI GPT-4o
    Returns: type, severity, sentiment, product, key_issues, confidence
       |
       v
[3] Update complaint with classification results
    If confidence < 0.5: set needs_review = True
       |
       v
[4] generate_embedding(title + " " + description) -> OpenAI Embeddings API
    Returns: 1536-dimensional vector
       |
       v
[5] Store embedding in complaint_embeddings table
       |
       v
[6] compute_sla_due_at(severity) -> datetime
    SLA: critical=1h, high=4h, medium=8h, low=24h
       |
       v
[7] Store SLA record in sla_tracking table
       |
       v
[8] Log audit entry: action="complaint.created"
       |
       v
[9] Return ComplaintOut response
```

## Data Flow: AI Draft Generation

```
POST /api/complaints/{id}/messages/draft
       |
       v
[1] Fetch complaint (title, description, customer_name, type, product, severity)
       |
       v
[2] generate_draft_response(complaint_data) -> OpenAI GPT-4o
    Prompt includes: title, description, customer, type, product, severity
       |
       v
[3] Create CommunicationThread with is_draft=True, direction=outbound
       |
       v
[4] Return draft message
       |
[5] Agent later calls POST .../messages/{msgId}/approve { body? }
    -> Sets is_draft=False, optionally edits body
```

## Data Flow: Duplicate Detection

```
GET /api/complaints/{id}/duplicates
       |
       v
[1] Fetch complaint_embedding for {id}
       |
       v
[2] find_duplicates(embedding, threshold=0.85, limit=10)
    Raw SQL: SELECT ... ORDER BY embedding <=> :target_embedding
    WHERE cosine_distance >= threshold
       |
       v
[3] Return list of DuplicateMatch (complaint_id, title, similarity_score)
```

## Layer Diagram (File Dependencies)

```
main.py
  ├── core/config.py          (no deps on other app modules)
  ├── core/database.py        (imports from config, models)
  ├── models/__init__.py      (re-exports models.py)
  ├── schemas/schemas.py      (no deps on other app modules)
  ├── routers/*.py            (imports from schemas, models, services, database)
  └── services/*.py           (imports from core/config, models, schemas)

services/
  ├── classification.py       (imports config, httpx)
  ├── draft_generator.py      (imports config, httpx)
  ├── embeddings.py           (imports config, httpx)
  └── duplicate_detector.py   (imports config, models)
```

## File Naming Convention

Each layer uses the conventional filename:
- `models.py` for SQLAlchemy models (in `models/`)
- `schemas.py` for Pydantic schemas (in `schemas/`)
- Named after domain for routers (`complaints.py`, `messages.py`, etc.)
- Named after function for services (`classification.py`, `embeddings.py`, etc.)
- `config.py` and `database.py` for core infrastructure
- `main.py` for entry point
