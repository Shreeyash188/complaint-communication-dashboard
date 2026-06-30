from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Complaint, ComplaintType, Severity
from app.schemas.schemas import TrendDataPoint, TrendFilters, TrendResponse

router = APIRouter(tags=["analytics"])


@router.get("/analytics/trends", response_model=TrendResponse)
async def get_trends(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    complaint_type: ComplaintType | None = None,
    product: str | None = None,
    severity: Severity | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Complaint)

    if start_date:
        query = query.where(Complaint.created_at >= start_date)
    if end_date:
        query = query.where(Complaint.created_at <= end_date)
    if complaint_type:
        query = query.where(Complaint.complaint_type == complaint_type)
    if product:
        query = query.where(Complaint.product == product)
    if severity:
        query = query.where(Complaint.severity == severity)

    base_sub = query.subquery()

    by_type_q = select(base_sub.c.complaint_type, func.count().label("cnt")).group_by(base_sub.c.complaint_type)
    by_type_result = await db.execute(by_type_q)
    by_type = [
        TrendDataPoint(label=str(row.complaint_type or "unknown"), count=row.cnt, period="total")
        for row in by_type_result.fetchall()
    ]

    by_product_q = select(base_sub.c.product, func.count().label("cnt")).group_by(base_sub.c.product)
    by_product_result = await db.execute(by_product_q)
    by_product = [
        TrendDataPoint(label=str(row.product or "unknown"), count=row.cnt, period="total")
        for row in by_product_result.fetchall()
    ]

    by_severity_q = select(base_sub.c.severity, func.count().label("cnt")).group_by(base_sub.c.severity)
    by_severity_result = await db.execute(by_severity_q)
    by_severity = [
        TrendDataPoint(label=str(row.severity or "unknown"), count=row.cnt, period="total")
        for row in by_severity_result.fetchall()
    ]

    return TrendResponse(by_type=by_type, by_product=by_product, by_severity=by_severity)
