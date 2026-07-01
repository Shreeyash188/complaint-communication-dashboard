# API Reference

Base URL: `/api`

## Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check -> `{"status":"healthy","service":"complaint-dashboard-backend"}` |

---

## Complaints (`/api/complaints`)

### GET `/complaints`
List complaints with pagination and filtering.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| skip | int (default 0) | Offset |
| limit | int (default 50) | Page size |
| status | ComplaintStatus | Filter by status |
| complaint_type | ComplaintType | Filter by type |
| severity | Severity | Filter by severity |
| channel | Channel | Filter by source channel |
| assigned_to | UUID | Filter by assigned user |
| search | str | Search in title/description |
| sort_by | str | Field to sort by (e.g. "created_at") |
| sort_order | str | "asc" or "desc" |

**Response:** `ComplaintListOut` (items array + total count)

---

### POST `/complaints`
Create a new complaint. Auto-classifies via AI, generates embeddings, creates SLA tracking, logs audit.

**Request Body:**
```json
{
  "title": "Wrong amount charged",
  "description": "I was billed $200 instead of $150...",
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "channel": "web_form"
}
```

**Response:** `ComplaintOut` (full complaint with all classification fields)

---

### GET `/complaints/{id}`
Get complaint detail. Includes messages, SLA tracking, audit log, and duplicate_of_id.

**Response:** `ComplaintDetail` (complaint + messages[] + sla + audit_log + duplicate_ids[])

---

### PATCH `/complaints/{id}`
Update complaint fields. If status changes to resolved/closed, sets `resolved_at`. Logs audit.

**Request Body (partial):** Any complaint fields.

**Response:** `ComplaintOut`

---

### POST `/complaints/{id}/classify`
Re-classify a complaint via AI. Updates classification fields and logs audit.

**Response:** `ClassificationResult` (type, severity, sentiment, product, key_issues, confidence)

---

### GET `/complaints/{id}/duplicates`
Find duplicate complaints via pgvector semantic search.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| threshold | float (default from config: 0.85) | Similarity threshold |
| limit | int (default 10) | Max results |

**Response:** List of `DuplicateMatch` (complaint_id, title, similarity_score)

---

### POST `/complaints/{id}/escalate`
Escalate a complaint. Sets status=escalated, optionally reassigns user. Logs audit.

**Request Body:**
```json
{
  "assigned_to": "uuid-here"  // optional
}
```

**Response:** `ComplaintOut`

---

### GET `/complaints/{id}/audit-log`
Get audit trail for a complaint.

**Response:** List of `AuditLogOut` (id, action, performed_by, old_value, new_value, details, created_at)

---

## Messages (`/api/complaints/{id}/messages`)

### GET `/messages`
List non-draft messages for a complaint (ordered by created_at).

**Response:** List of `MessageOut`

---

### POST `/messages`
Create a new message on a complaint.

**Request Body:**
```json
{
  "direction": "inbound | outbound | internal",
  "sender_name": "John Doe",
  "sender_email": "john@example.com",  // optional
  "body": "Message text here"
}
```

**Response:** `MessageOut`

---

### POST `/messages/draft`
Generate an AI draft response using GPT-4o. Creates a message with `is_draft=True`.

**Response:** `MessageOut` (draft)

---

### POST `/messages/{msgId}/approve`
Approve and optionally edit a draft. Sets `is_draft=False`. If `body` is provided, replaces draft body.

**Request Body:**
```json
{
  "body": "Optional edited body text"
}
```

**Response:** `MessageOut`

---

## Users (`/api/users`)

### GET `/users`
List all users (sorted by name).

**Response:** List of `UserOut`

---

### POST `/users`
Create a user. Returns 409 if email already exists.

**Request Body:**
```json
{
  "name": "Jane Agent",
  "email": "jane@company.com",
  "role": "agent",           // default: "agent"
  "team": "support-tier-1",  // optional
  "is_active": true           // default: true
}
```

**Response:** `UserOut`

---

### GET `/users/{id}`
Get single user.

**Response:** `UserOut`

---

### PATCH `/users/{id}`
Update user fields.

**Response:** `UserOut`

---

## Analytics (`/api/analytics`)

### GET `/analytics/trends`
Get complaint trends grouped by type, product, or severity.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| from_date | datetime | Start date |
| to_date | datetime | End date |
| complaint_type | str | Filter by type |
| product | str | Filter by product |
| severity | str | Filter by severity |
| group_by | str (default "type") | "type", "product", or "severity" |

**Response:** `TrendResponse` (group_by + data[] with period, count, group fields)

---

## SLA (`/api/sla`)

### GET `/sla/summary`
SLA summary statistics.

**Response:**
```json
{
  "total_tracked": 150,
  "breached": 5,
  "active_within_sla": 120,
  "by_severity": {
    "critical": {"total": 10, "breached": 2, "active_within_sla": 8},
    "high": {"total": 30, "breached": 2, "active_within_sla": 28},
    "medium": {"total": 60, "breached": 1, "active_within_sla": 59},
    "low": {"total": 50, "breached": 0, "active_within_sla": 50}
  }
}
```

---

### GET `/sla/{complaint_id}`
Get SLA tracking for a specific complaint.

**Response:** `SlaOut` (id, complaint_id, severity_tier, due_at, breached, created_at)

---

## Schema Types

### Enums
| Type | Values |
|------|--------|
| ComplaintType | billing, service, product_defect, delay, other |
| Severity | critical, high, medium, low |
| Sentiment | negative, neutral, positive |
| ComplaintStatus | open, in_progress, resolved, closed, escalated |
| Channel | email, web_form, social_media, call_centre, walk_in, csv_import |
| MessageDirection | inbound, outbound, internal |

### Key Response Shapes

**ComplaintOut:**
```json
{
  "id": "uuid",
  "title": "string",
  "description": "string",
  "customer_name": "string",
  "customer_email": "string",
  "channel": "web_form",
  "complaint_type": "billing",
  "product": "string",
  "severity": "medium",
  "sentiment": "negative",
  "key_issues": "[\"issue1\", \"issue2\"]",
  "classification_confidence": 0.95,
  "needs_review": false,
  "status": "open",
  "duplicate_of_id": "uuid | null",
  "assigned_to": "uuid | null",
  "created_at": "datetime",
  "updated_at": "datetime",
  "resolved_at": "datetime | null"
}
```

**MessageOut:**
```json
{
  "id": "uuid",
  "complaint_id": "uuid",
  "direction": "inbound",
  "sender_name": "string",
  "sender_email": "string",
  "body": "string",
  "is_draft": false,
  "created_at": "datetime"
}
```
