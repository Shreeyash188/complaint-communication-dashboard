import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Complaint, ComplaintStatus, Severity, SlaTracking
from app.schemas.schemas import SlaOut

router = APIRouter(tags=["sla"])


@router.get("/sla/summary")
async def sla_summary(
    db: AsyncSession = Depends(get_db),
):
    total_query = select(func.count()).select_from(
        select(SlaTracking).subquery()
    )
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    breached_query = (
        select(func.count())
        .select_from(select(SlaTracking).where(SlaTracking.breached == True).subquery())
    )
    breached_result = await db.execute(breached_query)
    breached = breached_result.scalar() or 0

    open_sla_query = (
        select(func.count())
        .select_from(
            select(SlaTracking)
            .join(Complaint, SlaTracking.complaint_id == Complaint.id)
            .where(Complaint.status.in_([ComplaintStatus.open, ComplaintStatus.in_progress]))
            .subquery()
        )
    )
    open_result = await db.execute(open_sla_query)
    open_active = open_result.scalar() or 0

    by_severity_q = (
        select(SlaTracking.severity_tier, func.count().label("cnt"))
        .group_by(SlaTracking.severity_tier)
    )
    by_severity_result = await db.execute(by_severity_q)
    by_severity = {
        row.severity_tier.value if hasattr(row.severity_tier, "value") else row.severity_tier: row.cnt
        for row in by_severity_result.fetchall()
    }

    return {
        "total_sla_tracked": total,
        "breached": breached,
        "active_within_sla": open_active,
        "by_severity": by_severity,
    }


@router.get("/sla/{complaint_id}", response_model=SlaOut | None)
async def get_sla_for_complaint(
    complaint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SlaTracking).where(SlaTracking.complaint_id == complaint_id)
    )
    sla = result.scalar_one_or_none()
    if not sla:
        return None
    return SlaOut.model_validate(sla)
