import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ComplaintEmbedding, Severity
from app.schemas.schemas import DuplicateMatch

SEVERITY_SLA_HOURS: dict[Severity, float] = {
    Severity.critical: 4,
    Severity.high: 24,
    Severity.medium: 72,
    Severity.low: 120,
}


def compute_sla_due_at(severity: Severity, created_at: datetime | None = None) -> datetime:
    base = created_at or datetime.now(timezone.utc)
    hours = SEVERITY_SLA_HOURS.get(severity, 72)
    return base + timedelta(hours=hours)


async def find_duplicates(
    db: AsyncSession,
    complaint_id: uuid.UUID,
    embedding: list[float],
    threshold: float = 0.85,
) -> list[DuplicateMatch]:
    sql = text("""
        SELECT ce.complaint_id, c.title,
               1 - (ce.embedding <=> :query_embedding) AS similarity
        FROM complaint_embeddings ce
        JOIN complaints c ON c.id = ce.complaint_id
        WHERE ce.complaint_id != :complaint_id
        ORDER BY ce.embedding <=> :query_embedding
        LIMIT 10
    """)
    result = await db.execute(
        sql,
        {"query_embedding": str(embedding), "complaint_id": str(complaint_id)},
    )
    rows = result.fetchall()
    return [
        DuplicateMatch(
            complaint_id=row[0],
            title=row[1],
            similarity=row[2],
        )
        for row in rows
        if row[2] >= threshold
    ]
