import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import CommunicationThread, MessageDirection
from app.schemas.schemas import DraftApprove, MessageCreate, MessageOut
from app.services.draft_generator import generate_draft_response

router = APIRouter(tags=["messages"])


async def _get_message_or_404(
    db: AsyncSession, message_id: uuid.UUID
) -> CommunicationThread:
    result = await db.execute(
        select(CommunicationThread).where(CommunicationThread.id == message_id)
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg


@router.get("/complaints/{complaint_id}/messages", response_model=list[MessageOut])
async def list_messages(
    complaint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CommunicationThread)
        .where(CommunicationThread.complaint_id == complaint_id)
        .where(CommunicationThread.is_draft == False)
        .order_by(CommunicationThread.created_at.asc())
    )
    messages = result.scalars().all()
    return [MessageOut.model_validate(m) for m in messages]


@router.post("/complaints/{complaint_id}/messages", response_model=MessageOut, status_code=201)
async def create_message(
    complaint_id: uuid.UUID,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    from app.routers.complaints import _get_complaint_or_404

    await _get_complaint_or_404(db, complaint_id)

    message = CommunicationThread(
        complaint_id=complaint_id,
        direction=payload.direction,
        sender_name=payload.sender_name,
        sender_email=payload.sender_email,
        body=payload.body,
        is_draft=payload.is_draft,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return MessageOut.model_validate(message)


@router.post("/complaints/{complaint_id}/messages/draft", response_model=MessageOut)
async def generate_draft(
    complaint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from app.routers.complaints import _get_complaint_or_404

    complaint = await _get_complaint_or_404(db, complaint_id)

    draft_body = await generate_draft_response(
        complaint_title=complaint.title,
        complaint_description=complaint.description,
        customer_name=complaint.customer_name,
        complaint_type=complaint.complaint_type.value if complaint.complaint_type else None,
        product=complaint.product,
        severity=complaint.severity.value if complaint.severity else None,
    )

    if not draft_body:
        raise HTTPException(status_code=502, detail="Draft generation failed")

    message = CommunicationThread(
        complaint_id=complaint_id,
        direction=MessageDirection.outbound,
        sender_name="System (AI Draft)",
        sender_email=None,
        body=draft_body,
        is_draft=True,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return MessageOut.model_validate(message)


@router.post("/complaints/{complaint_id}/messages/{message_id}/approve", response_model=MessageOut)
async def approve_draft(
    complaint_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: DraftApprove,
    db: AsyncSession = Depends(get_db),
):
    from app.routers.complaints import _get_complaint_or_404

    await _get_complaint_or_404(db, complaint_id)
    message = await _get_message_or_404(db, message_id)

    if not message.is_draft:
        raise HTTPException(status_code=400, detail="Message is not a draft")

    if payload.edited_body is not None:
        message.body = payload.edited_body
    message.is_draft = False
    await db.commit()
    await db.refresh(message)
    return MessageOut.model_validate(message)
