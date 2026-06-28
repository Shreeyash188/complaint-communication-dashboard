import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ComplaintType(str, enum.Enum):
    billing = "billing"
    service = "service"
    product_defect = "product_defect"
    delay = "delay"
    other = "other"


class Severity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class Sentiment(str, enum.Enum):
    negative = "negative"
    neutral = "neutral"
    positive = "positive"


class ComplaintStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"
    escalated = "escalated"


class Channel(str, enum.Enum):
    email = "email"
    web_form = "web_form"
    social_media = "social_media"
    call_centre = "call_centre"
    walk_in = "walk_in"
    csv_import = "csv_import"


class MessageDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"
    internal = "internal"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="agent")
    team: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    assigned_complaints: Mapped[list["Complaint"]] = relationship(back_populates="assigned_to_user")


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    channel: Mapped[Channel] = mapped_column(Enum(Channel), nullable=False, default=Channel.web_form)

    complaint_type: Mapped[ComplaintType | None] = mapped_column(Enum(ComplaintType), nullable=True)
    product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    severity: Mapped[Severity | None] = mapped_column(Enum(Severity), nullable=True)
    sentiment: Mapped[Sentiment | None] = mapped_column(Enum(Sentiment), nullable=True)
    key_issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[ComplaintStatus] = mapped_column(Enum(ComplaintStatus), nullable=False, default=ComplaintStatus.open)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("complaints.id"), nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_to_user: Mapped[User | None] = relationship(back_populates="assigned_complaints")
    duplicate_of: Mapped["Complaint | None"] = relationship(remote_side="Complaint.id", foreign_keys=[duplicate_of_id])
    communication_threads: Mapped[list["CommunicationThread"]] = relationship(back_populates="complaint", cascade="all, delete-orphan")
    sla_tracking: Mapped["SlaTracking | None"] = relationship(back_populates="complaint", uselist=False, cascade="all, delete-orphan")
    embedding: Mapped["ComplaintEmbedding | None"] = relationship(back_populates="complaint", uselist=False, cascade="all, delete-orphan")
    audit_entries: Mapped[list["AuditLog"]] = relationship(back_populates="complaint", cascade="all, delete-orphan")


class CommunicationThread(Base):
    __tablename__ = "communication_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("complaints.id"), nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(Enum(MessageDirection), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    complaint: Mapped["Complaint"] = relationship(back_populates="communication_threads")


class SlaTracking(Base):
    __tablename__ = "sla_tracking"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("complaints.id"), unique=True, nullable=False)
    severity_tier: Mapped[Severity] = mapped_column(Enum(Severity), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    breached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    complaint: Mapped["Complaint"] = relationship(back_populates="sla_tracking")


class ComplaintEmbedding(Base):
    __tablename__ = "complaint_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("complaints.id"), unique=True, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    complaint: Mapped["Complaint"] = relationship(back_populates="embedding")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    complaint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("complaints.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    performed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    complaint: Mapped["Complaint"] = relationship(back_populates="audit_entries")
