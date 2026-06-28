import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.models import (
    Channel,
    ComplaintStatus,
    ComplaintType,
    MessageDirection,
    Sentiment,
    Severity,
)


class ComplaintCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1, max_length=255)
    customer_email: str = Field(..., min_length=1, max_length=255)
    channel: Channel = Channel.web_form


class ComplaintUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: ComplaintStatus | None = None
    complaint_type: ComplaintType | None = None
    product: str | None = None
    severity: Severity | None = None
    sentiment: Sentiment | None = None
    key_issues: list[str] | None = None
    assigned_to: uuid.UUID | None = None
    duplicate_of_id: uuid.UUID | None = None
    needs_review: bool | None = None


class ClassificationResult(BaseModel):
    type: ComplaintType = ComplaintType.other
    product: str = ""
    severity: Severity = Severity.medium
    sentiment: Sentiment = Sentiment.neutral
    key_issues: list[str] = []
    confidence: float = 0.0


class MessageCreate(BaseModel):
    direction: MessageDirection
    sender_name: str = Field(..., min_length=1, max_length=255)
    sender_email: str | None = None
    body: str = Field(..., min_length=1)
    is_draft: bool = False


class DraftApprove(BaseModel):
    edited_body: str | None = None


class EscalateRequest(BaseModel):
    escalated_to: uuid.UUID | None = None
    reason: str | None = None


class TrendFilters(BaseModel):
    start_date: datetime | None = None
    end_date: datetime | None = None
    complaint_type: ComplaintType | None = None
    product: str | None = None
    severity: Severity | None = None


class ReportExportRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    format: str = "csv"


class SlaOut(BaseModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    severity_tier: Severity
    due_at: datetime
    breached: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    direction: MessageDirection
    sender_name: str
    sender_email: str | None
    body: str
    is_draft: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: uuid.UUID
    complaint_id: uuid.UUID
    action: str
    performed_by: str | None
    old_value: str | None
    new_value: str | None
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplaintOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    customer_name: str
    customer_email: str
    channel: Channel
    complaint_type: ComplaintType | None
    product: str | None
    severity: Severity | None
    sentiment: Sentiment | None
    key_issues: list[str] | None
    classification_confidence: float | None
    needs_review: bool
    status: ComplaintStatus
    duplicate_of_id: uuid.UUID | None
    assigned_to: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class ComplaintDetail(ComplaintOut):
    messages: list[MessageOut] = []
    sla: SlaOut | None = None
    audit_log: list[AuditLogOut] = []
    duplicate_complaint_ids: list[uuid.UUID] = []


class ComplaintListOut(BaseModel):
    items: list[ComplaintOut]
    total: int
    page: int
    page_size: int


class DuplicateMatch(BaseModel):
    complaint_id: uuid.UUID
    title: str
    similarity: float


class TrendDataPoint(BaseModel):
    label: str
    count: int
    period: str


class TrendResponse(BaseModel):
    by_type: list[TrendDataPoint]
    by_product: list[TrendDataPoint]
    by_severity: list[TrendDataPoint]


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)
    role: str = "agent"
    team: str | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    team: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
