import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import (
    AuditLog,
    Channel,
    Complaint,
    ComplaintEmbedding,
    ComplaintStatus,
    ComplaintType,
    Severity,
    SlaTracking,
)
from app.schemas.schemas import (
    ClassificationResult,
    ComplaintCreate,
    ComplaintDetail,
    ComplaintListOut,
    ComplaintOut,
    ComplaintUpdate,
    DuplicateMatch,
    EscalateRequest,
    AuditLogOut,
)
from app.services.classification import classify_complaint
from app.services.duplicate_detector import compute_sla_due_at, find_duplicates
from app.services.embeddings import generate_embedding

router = APIRouter(tags=["complaints"])


def _serialize_key_issues(issues: list[str] | None) -> str | None:
    return json.dumps(issues) if issues is not None else None


def _deserialize_key_issues(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def _log_audit(
    db: AsyncSession,
    complaint_id: uuid.UUID,
    action: str,
    performed_by: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    details: str | None = None,
):
    entry = AuditLog(
        complaint_id=complaint_id,
        action=action,
        performed_by=performed_by,
        old_value=old_value,
        new_value=new_value,
        details=details,
    )
    db.add(entry)
    await db.commit()


async def _get_complaint_or_404(db: AsyncSession, complaint_id: uuid.UUID) -> Complaint:
    result = await db.execute(select(Complaint).where(Complaint.id == complaint_id))
    complaint = result.scalar_one_or_none()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.get("/complaints", response_model=ComplaintListOut)
async def list_complaints(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ComplaintStatus | None = None,
    complaint_type: ComplaintType | None = None,
    severity: Severity | None = None,
    channel: Channel | None = None,
    assigned_to: uuid.UUID | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    query = select(Complaint)

    if status:
        query = query.where(Complaint.status == status)
    if complaint_type:
        query = query.where(Complaint.complaint_type == complaint_type)
    if severity:
        query = query.where(Complaint.severity == severity)
    if channel:
        query = query.where(Complaint.channel == channel)
    if assigned_to:
        query = query.where(Complaint.assigned_to == assigned_to)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            Complaint.title.ilike(pattern) | Complaint.description.ilike(pattern)
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    sort_column = getattr(Complaint, sort_by, Complaint.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    complaints = result.scalars().all()

    items = []
    for c in complaints:
        complaint_dict = {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "customer_name": c.customer_name,
            "customer_email": c.customer_email,
            "channel": c.channel,
            "complaint_type": c.complaint_type,
            "product": c.product,
            "severity": c.severity,
            "sentiment": c.sentiment,
            "key_issues": _deserialize_key_issues(c.key_issues),
            "classification_confidence": c.classification_confidence,
            "needs_review": c.needs_review,
            "status": c.status,
            "duplicate_of_id": c.duplicate_of_id,
            "assigned_to": c.assigned_to,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "resolved_at": c.resolved_at,
        }
        items.append(ComplaintOut(**complaint_dict))

    return ComplaintListOut(items=items, total=total, page=page, page_size=page_size)


@router.post("/complaints", response_model=ComplaintOut, status_code=201)
async def create_complaint(
    payload: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
):
    complaint = Complaint(
        title=payload.title,
        description=payload.description,
        customer_name=payload.customer_name,
        customer_email=payload.customer_email,
        channel=payload.channel,
    )
    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)

    classification = await classify_complaint(payload.title, payload.description)
    complaint.complaint_type = classification.type
    complaint.product = classification.product
    complaint.severity = classification.severity
    complaint.sentiment = classification.sentiment
    complaint.key_issues = _serialize_key_issues(classification.key_issues)
    complaint.classification_confidence = classification.confidence
    if classification.confidence < 0.5:
        complaint.needs_review = True

    embedding_vector = await generate_embedding(
        f"{payload.title}\n{payload.description}"
    )
    if embedding_vector:
        embedding_record = ComplaintEmbedding(
            complaint_id=complaint.id,
            embedding=embedding_vector,
            model_name=None,
        )
        db.add(embedding_record)

    sla_due = compute_sla_due_at(classification.severity, complaint.created_at)
    sla_record = SlaTracking(
        complaint_id=complaint.id,
        severity_tier=classification.severity,
        due_at=sla_due,
    )
    db.add(sla_record)

    await db.commit()
    await db.refresh(complaint)

    await _log_audit(db, complaint.id, "complaint.created", details="Complaint created with auto-classification")

    complaint_out = {
        "id": complaint.id,
        "title": complaint.title,
        "description": complaint.description,
        "customer_name": complaint.customer_name,
        "customer_email": complaint.customer_email,
        "channel": complaint.channel,
        "complaint_type": complaint.complaint_type,
        "product": complaint.product,
        "severity": complaint.severity,
        "sentiment": complaint.sentiment,
        "key_issues": _deserialize_key_issues(complaint.key_issues),
        "classification_confidence": complaint.classification_confidence,
        "needs_review": complaint.needs_review,
        "status": complaint.status,
        "duplicate_of_id": complaint.duplicate_of_id,
        "assigned_to": complaint.assigned_to,
        "created_at": complaint.created_at,
        "updated_at": complaint.updated_at,
        "resolved_at": complaint.resolved_at,
    }
    return ComplaintOut(**complaint_out)


@router.get("/complaints/{complaint_id}", response_model=ComplaintDetail)
async def get_complaint(
    complaint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    complaint = await _get_complaint_or_404(db, complaint_id)

    from app.schemas.schemas import AuditLogOut, MessageOut, SlaOut

    messages = [MessageOut.model_validate(m) for m in (complaint.communication_threads or [])]
    sla = SlaOut.model_validate(complaint.sla_tracking) if complaint.sla_tracking else None
    audit_entries = [AuditLogOut.model_validate(a) for a in (complaint.audit_entries or [])]

    duplicate_query = select(Complaint.id).where(Complaint.duplicate_of_id == complaint_id)
    dup_result = await db.execute(duplicate_query)
    duplicate_ids = [row[0] for row in dup_result.fetchall()]

    complaint_out = {
        "id": complaint.id,
        "title": complaint.title,
        "description": complaint.description,
        "customer_name": complaint.customer_name,
        "customer_email": complaint.customer_email,
        "channel": complaint.channel,
        "complaint_type": complaint.complaint_type,
        "product": complaint.product,
        "severity": complaint.severity,
        "sentiment": complaint.sentiment,
        "key_issues": _deserialize_key_issues(complaint.key_issues),
        "classification_confidence": complaint.classification_confidence,
        "needs_review": complaint.needs_review,
        "status": complaint.status,
        "duplicate_of_id": complaint.duplicate_of_id,
        "assigned_to": complaint.assigned_to,
        "created_at": complaint.created_at,
        "updated_at": complaint.updated_at,
        "resolved_at": complaint.resolved_at,
        "messages": messages,
        "sla": sla,
        "audit_log": audit_entries,
        "duplicate_complaint_ids": duplicate_ids,
    }
    return ComplaintDetail(**complaint_out)


@router.patch("/complaints/{complaint_id}", response_model=ComplaintOut)
async def update_complaint(
    complaint_id: uuid.UUID,
    payload: ComplaintUpdate,
    db: AsyncSession = Depends(get_db),
):
    complaint = await _get_complaint_or_404(db, complaint_id)
    update_data = payload.model_dump(exclude_unset=True)

    old_status = complaint.status.value if complaint.status else None

    if "key_issues" in update_data:
        update_data["key_issues"] = _serialize_key_issues(update_data["key_issues"])

    for field, value in update_data.items():
        setattr(complaint, field, value)

    if payload.status == ComplaintStatus.resolved:
        complaint.resolved_at = datetime.now(timezone.utc)
    elif payload.status == ComplaintStatus.closed:
        complaint.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(complaint)

    change_details = ", ".join(f"{k}: {v}" for k, v in update_data.items())
    await _log_audit(
        db,
        complaint.id,
        "complaint.updated",
        old_value=old_status,
        new_value=complaint.status.value if complaint.status else None,
        details=change_details,
    )

    complaint_out = {
        "id": complaint.id,
        "title": complaint.title,
        "description": complaint.description,
        "customer_name": complaint.customer_name,
        "customer_email": complaint.customer_email,
        "channel": complaint.channel,
        "complaint_type": complaint.complaint_type,
        "product": complaint.product,
        "severity": complaint.severity,
        "sentiment": complaint.sentiment,
        "key_issues": _deserialize_key_issues(complaint.key_issues),
        "classification_confidence": complaint.classification_confidence,
        "needs_review": complaint.needs_review,
        "status": complaint.status,
        "duplicate_of_id": complaint.duplicate_of_id,
        "assigned_to": complaint.assigned_to,
        "created_at": complaint.created_at,
        "updated_at": complaint.updated_at,
        "resolved_at": complaint.resolved_at,
    }
    return ComplaintOut(**complaint_out)


@router.post("/complaints/{complaint_id}/classify", response_model=ClassificationResult)
async def reclassify_complaint(
    complaint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    complaint = await _get_complaint_or_404(db, complaint_id)
    result = await classify_complaint(complaint.title, complaint.description)

    complaint.complaint_type = result.type
    complaint.product = result.product
    complaint.severity = result.severity
    complaint.sentiment = result.sentiment
    complaint.key_issues = _serialize_key_issues(result.key_issues)
    complaint.classification_confidence = result.confidence
    complaint.needs_review = result.confidence < 0.5

    await db.commit()
    await db.refresh(complaint)
    await _log_audit(db, complaint.id, "complaint.classified", details=f"Re-classified with confidence {result.confidence}")

    return result


@router.get("/complaints/{complaint_id}/duplicates", response_model=list[DuplicateMatch])
async def get_duplicates(
    complaint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    complaint = await _get_complaint_or_404(db, complaint_id)
    embedding_result = await db.execute(
        select(ComplaintEmbedding).where(ComplaintEmbedding.complaint_id == complaint_id)
    )
    emb = embedding_result.scalar_one_or_none()
    if not emb or not emb.embedding:
        return []

    return await find_duplicates(db, complaint_id, emb.embedding)


@router.post("/complaints/{complaint_id}/escalate", response_model=ComplaintOut)
async def escalate_complaint(
    complaint_id: uuid.UUID,
    payload: EscalateRequest,
    db: AsyncSession = Depends(get_db),
):
    complaint = await _get_complaint_or_404(db, complaint_id)
    complaint.status = ComplaintStatus.escalated
    if payload.escalated_to:
        complaint.assigned_to = payload.escalated_to
    await db.commit()
    await db.refresh(complaint)
    await _log_audit(
        db,
        complaint.id,
        "complaint.escalated",
        details=payload.reason or "No reason provided",
    )

    complaint_out = {
        "id": complaint.id,
        "title": complaint.title,
        "description": complaint.description,
        "customer_name": complaint.customer_name,
        "customer_email": complaint.customer_email,
        "channel": complaint.channel,
        "complaint_type": complaint.complaint_type,
        "product": complaint.product,
        "severity": complaint.severity,
        "sentiment": complaint.sentiment,
        "key_issues": _deserialize_key_issues(complaint.key_issues),
        "classification_confidence": complaint.classification_confidence,
        "needs_review": complaint.needs_review,
        "status": complaint.status,
        "duplicate_of_id": complaint.duplicate_of_id,
        "assigned_to": complaint.assigned_to,
        "created_at": complaint.created_at,
        "updated_at": complaint.updated_at,
        "resolved_at": complaint.resolved_at,
    }
    return ComplaintOut(**complaint_out)


@router.get("/complaints/{complaint_id}/audit-log", response_model=list[AuditLogOut])
async def get_audit_log(
    complaint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    complaint = await _get_complaint_or_404(db, complaint_id)
    return complaint.audit_entries or []
