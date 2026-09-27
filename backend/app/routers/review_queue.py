import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_analyst
from app.db.database import get_db
from app.db.models import Conversation, Message, AuditLog
from app.schemas import ReviewQueueItem, EditReplyRequest, ReviewActionResponse
from app.services.persona_agent import check_reply_safety, PersonaSafetyViolationError
from app.services.twilio_client import send_sms, TwilioClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/review-queue", tags=["Human Review Queue"])


@router.get("", response_model=List[ReviewQueueItem])
def get_pending_review_queue(
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Returns all messages currently waiting for human review (review_status = 'pending').
    """
    pending_messages = (
        db.query(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Message.review_status == "pending")
        .order_by(Message.created_at.asc())
        .all()
    )

    items = []
    for msg in pending_messages:
        conv = msg.conversation
        items.append(
            ReviewQueueItem(
                id=msg.id,
                conversation_id=msg.conversation_id,
                channel=conv.channel,
                scammer_contact=conv.scammer_contact,
                role=msg.role,
                text=msg.text,
                flagged_action=msg.flagged_action,
                review_status=msg.review_status,
                created_at=msg.created_at,
            )
        )
    return items


@router.post("/{message_id}/approve", response_model=ReviewActionResponse)
def approve_pending_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Approves a pending message:
    - Atomically locks message row to prevent race conditions.
    - Transitions review_status to 'approved'.
    - If channel is 'sms', dispatches reply via Twilio.
    - If channel is 'simulated', marks delivered without external dispatch.
    - Logs action to audit_logs.
    """
    # Atomically lock the row
    msg = (
        db.query(Message)
        .filter(Message.id == message_id)
        .with_for_update()
        .first()
    )

    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    if msg.review_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This message has already been handled (current status: {msg.review_status}).",
        )

    conv = db.query(Conversation).filter(Conversation.id == msg.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    if conv.status == "halted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve reply for a halted conversation.",
        )

    # Dispatch reply if SMS channel
    if conv.channel == "sms":
        try:
            send_sms(to_number=conv.scammer_contact, body=msg.text)
        except TwilioClientError as e:
            logger.error(f"Failed to send approved SMS via Twilio: {e}")
            msg.review_status = "send_failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Twilio send failed: {e}",
            )

    msg.review_status = "approved"

    # Write audit log
    audit_entry = AuditLog(
        conversation_id=conv.id,
        actor="analyst",
        action="approved_reply",
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(msg)

    return ReviewActionResponse(
        status="success",
        message_id=msg.id,
        conversation_id=conv.id,
        review_status=msg.review_status,
        conversation_status=conv.status,
    )


@router.post("/{message_id}/edit", response_model=ReviewActionResponse)
def edit_pending_message(
    message_id: uuid.UUID,
    payload: EditReplyRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Edits and sends a pending message:
    - Atomically locks message row.
    - Validates safety of edited text against regex guardrails.
    - Replaces stored message text and sets review_status to 'edited'.
    - If channel is 'sms', dispatches edited reply via Twilio.
    - Logs action to audit_logs.
    """
    msg = (
        db.query(Message)
        .filter(Message.id == message_id)
        .with_for_update()
        .first()
    )

    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    if msg.review_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This message has already been handled (current status: {msg.review_status}).",
        )

    conv = db.query(Conversation).filter(Conversation.id == msg.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    if conv.status == "halted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit reply for a halted conversation.",
        )

    edited_text = payload.text.strip()
    try:
        check_reply_safety(edited_text)
    except PersonaSafetyViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Safety check rejected edited reply: {e}",
        )

    msg.text = edited_text

    # Dispatch reply if SMS channel
    if conv.channel == "sms":
        try:
            send_sms(to_number=conv.scammer_contact, body=edited_text)
        except TwilioClientError as e:
            logger.error(f"Failed to send edited SMS via Twilio: {e}")
            msg.review_status = "send_failed"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Twilio send failed: {e}",
            )

    msg.review_status = "edited"

    # Write audit log
    audit_entry = AuditLog(
        conversation_id=conv.id,
        actor="analyst",
        action="edited_reply",
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(msg)

    return ReviewActionResponse(
        status="success",
        message_id=msg.id,
        conversation_id=conv.id,
        review_status=msg.review_status,
        conversation_status=conv.status,
    )


@router.post("/{message_id}/halt", response_model=ReviewActionResponse)
def halt_pending_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Halts the conversation:
    - Atomically locks message row.
    - Transitions review_status to 'halted'.
    - Transitions conversation status to 'halted'.
    - DOES NOT dispatch any outbound message.
    - Logs action to audit_logs.
    """
    msg = (
        db.query(Message)
        .filter(Message.id == message_id)
        .with_for_update()
        .first()
    )

    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    if msg.review_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This message has already been handled (current status: {msg.review_status}).",
        )

    conv = db.query(Conversation).filter(Conversation.id == msg.conversation_id).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    msg.review_status = "halted"
    conv.status = "halted"

    # Write audit log
    audit_entry = AuditLog(
        conversation_id=conv.id,
        actor="analyst",
        action="halted_conversation",
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(msg)
    db.refresh(conv)

    return ReviewActionResponse(
        status="success",
        message_id=msg.id,
        conversation_id=conv.id,
        review_status=msg.review_status,
        conversation_status=conv.status,
    )
