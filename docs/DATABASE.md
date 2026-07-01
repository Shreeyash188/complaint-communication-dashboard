# Database Schema

All tables use UUID primary keys and timestamp with timezone columns. Tables are auto-created on app startup via `Base.metadata.create_all`.

**Database:** PostgreSQL 16+ with **pgvector** extension (for `vector(1536)` column type).

---

## Entity-Relationship Diagram

```
users 1---* complaints (assigned_to)
complaints 1---* communication_threads (cascade delete)
complaints 1---1 sla_tracking
complaints 1---1 complaint_embeddings
complaints 1---* audit_log (cascade delete)
complaints 1---1 complaints (duplicate_of_id, self-referential)
```

---

## Table: `users`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, server_default=uuid4 |
| name | String(255) | NOT NULL |
| email | String(255) | UNIQUE, NOT NULL |
| role | String(50) | NOT NULL, default "agent" |
| team | String(100) | NULLABLE |
| is_active | Boolean | default True |
| created_at | DateTime(timezone=True) | server_default=now() |

**Relationships:** `assigned_complaints` -> Complaint (via `assigned_to` FK)

---

## Table: `complaints`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, server_default=uuid4 |
| title | String(500) | NOT NULL |
| description | Text | NOT NULL |
| customer_name | String(255) | NOT NULL |
| customer_email | String(255) | NOT NULL |
| channel | Enum(Channel) | NOT NULL, default web_form |
| complaint_type | Enum(ComplaintType) | NULLABLE (set by AI) |
| product | String(255) | NULLABLE (set by AI) |
| severity | Enum(Severity) | NULLABLE (set by AI) |
| sentiment | Enum(Sentiment) | NULLABLE (set by AI) |
| key_issues | Text | NULLABLE (JSON-serialized list) |
| classification_confidence | Float | NULLABLE |
| needs_review | Boolean | default False |
| status | Enum(ComplaintStatus) | NOT NULL, default open |
| duplicate_of_id | UUID | FK -> complaints.id, NULLABLE |
| assigned_to | UUID | FK -> users.id, NULLABLE |
| created_at | DateTime(timezone=True) | server_default=now() |
| updated_at | DateTime(timezone=True) | server_default=now(), onupdate=now() |
| resolved_at | DateTime(timezone=True) | NULLABLE |

**Indexes:** None explicitly defined (rely on PK/default FK indexes).

**Relationships:**
- `assigned_to_user` -> User
- `duplicate_of` -> Complaint (self-referential)
- `communication_threads` -> CommunicationThread (cascade delete)
- `sla_tracking` -> SlaTracking (uselist=False, one-to-one)
- `embedding` -> ComplaintEmbedding (uselist=False, one-to-one)
- `audit_entries` -> AuditLog (cascade delete)

---

## Table: `communication_threads`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, server_default=uuid4 |
| complaint_id | UUID | FK -> complaints.id, NOT NULL |
| direction | Enum(MessageDirection) | NOT NULL (inbound/outbound/internal) |
| sender_name | String(255) | NOT NULL |
| sender_email | String(255) | NULLABLE |
| body | Text | NOT NULL |
| is_draft | Boolean | default False |
| created_at | DateTime(timezone=True) | server_default=now() |

**Relationship:** `complaint` -> Complaint

---

## Table: `sla_tracking`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, server_default=uuid4 |
| complaint_id | UUID | FK -> complaints.id, UNIQUE, NOT NULL |
| severity_tier | Enum(Severity) | NOT NULL |
| due_at | DateTime(timezone=True) | NOT NULL |
| breached | Boolean | default False |
| created_at | DateTime(timezone=True) | server_default=now() |

**Relationship:** `complaint` -> Complaint (uselist=False)

---

## Table: `complaint_embeddings`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, server_default=uuid4 |
| complaint_id | UUID | FK -> complaints.id, UNIQUE, NOT NULL |
| embedding | Vector(1536) | NULLABLE (pgvector type) |
| model_name | String(255) | NULLABLE |
| created_at | DateTime(timezone=True) | server_default=now() |

**Relationship:** `complaint` -> Complaint (uselist=False)

**Note:** This table is queried using raw SQL with the pgvector cosine distance operator (`<=>`):
```sql
SELECT ..., 1 - (embedding <=> :target_embedding) AS similarity
FROM complaint_embeddings
WHERE complaint_id != :complaint_id
  AND 1 - (embedding <=> :target_embedding) >= :threshold
ORDER BY embedding <=> :target_embedding
LIMIT :limit
```

---

## Table: `audit_log`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, server_default=uuid4 |
| complaint_id | UUID | FK -> complaints.id, NOT NULL |
| action | String(100) | NOT NULL |
| performed_by | String(255) | NULLABLE |
| old_value | Text | NULLABLE |
| new_value | Text | NULLABLE |
| details | Text | NULLABLE |
| created_at | DateTime(timezone=True) | server_default=now() |

**Relationship:** `complaint` -> Complaint

---

## Enums (SQLAlchemy, stored as strings)

| Python Enum | Values |
|-------------|--------|
| ComplaintType | billing, service, product_defect, delay, other |
| Severity | critical, high, medium, low |
| Sentiment | negative, neutral, positive |
| ComplaintStatus | open, in_progress, resolved, closed, escalated |
| Channel | email, web_form, social_media, call_centre, walk_in, csv_import |
| MessageDirection | inbound, outbound, internal |

---

## SLA Deadline Calculation

Defined in `duplicate_detector.py` (`compute_sla_due_at`):

| Severity | Hours Added |
|----------|-------------|
| critical | 1 |
| high | 4 |
| medium | 8 |
| low | 24 |

`due_at = utcnow() + timedelta(hours=hours)` stored in `sla_tracking.due_at`.
