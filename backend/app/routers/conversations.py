import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_analyst
from app.db.database import get_db
from app.db.models import Conversation, Message, RiskAssessment
from app.schemas import ConversationListItem, ConversationDetail, MessageOut, ThreatIndicatorOut, RiskAssessmentOut
from app.services.risk_agent import explain_for_demo

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationListItem])
def list_conversations(
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Returns list of all conversations for the Analyst Dashboard,
    including channel (sms vs simulated), persona, message counts,
    pending review flag, and latest risk score.
    """
    conversations = (
        db.query(Conversation)
        .order_by(Conversation.created_at.desc())
        .all()
    )

    items = []
    for conv in conversations:
        # Message count and last message
        msgs = conv.messages
        msg_count = len(msgs)
        last_msg = msgs[-1].text if msgs else None
        last_msg_at = msgs[-1].created_at if msgs else None
        has_pending = any(m.review_status == "pending" for m in msgs)

        # Risk score
        risk_score = conv.risk_assessment.risk_score if conv.risk_assessment else None
        risk_class = conv.risk_assessment.classification if conv.risk_assessment else None

        items.append(
            ConversationListItem(
                id=conv.id,
                channel=conv.channel,
                scammer_contact=conv.scammer_contact,
                persona_id=conv.persona_id,
                persona_name=conv.persona.name if conv.persona else "Unknown",
                status=conv.status,
                created_at=conv.created_at,
                message_count=msg_count,
                last_message=last_msg,
                last_message_at=last_msg_at,
                has_pending_review=has_pending,
                risk_score=risk_score,
                risk_classification=risk_class,
            )
        )
    return items


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation_detail(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Returns full details for a conversation including chronological transcript,
    threat indicators, and risk assessment.
    """
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    # Ordered messages
    messages_out = [
        MessageOut(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            text=m.text,
            flagged_action=m.flagged_action,
            review_status=m.review_status,
            created_at=m.created_at,
        )
        for m in conv.messages
    ]

    # Indicators
    indicators_out = [
        ThreatIndicatorOut(
            id=ti.id,
            conversation_id=ti.conversation_id,
            indicator_type=ti.indicator_type,
            value=ti.value,
            status=ti.status,
            known_bad=ti.known_bad,
            domain_age_days=ti.domain_age_days,
            created_at=ti.created_at,
        )
        for ti in conv.threat_indicators
    ]

    # Risk Assessment
    risk_out = None
    if conv.risk_assessment:
        risk_out = RiskAssessmentOut(
            id=conv.risk_assessment.id,
            conversation_id=conv.risk_assessment.conversation_id,
            risk_score=conv.risk_assessment.risk_score,
            classification=conv.risk_assessment.classification,
            reasons=conv.risk_assessment.reasons,
            explanation=conv.risk_assessment.explanation,
            updated_at=conv.risk_assessment.updated_at,
        )

    return ConversationDetail(
        id=conv.id,
        channel=conv.channel,
        scammer_contact=conv.scammer_contact,
        persona_id=conv.persona_id,
        persona_name=conv.persona.name if conv.persona else "Unknown",
        persona_backstory=conv.persona.backstory_json if conv.persona else {},
        status=conv.status,
        created_at=conv.created_at,
        messages=messages_out,
        threat_indicators=indicators_out,
        risk_assessment=risk_out,
    )


@router.post("/{conversation_id}/explain")
def generate_conversation_explanation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Generates a warm, executive narrative explanation of the conversation's risk assessment
    using the Explanation Agent (TICKET-012) and persists it on the RiskAssessment.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    if not conv.risk_assessment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation has no risk assessment to explain.",
        )

    explanation = explain_for_demo(conv.risk_assessment)

    conv.risk_assessment.explanation = explanation
    db.commit()
    db.refresh(conv.risk_assessment)

    return {
        "status": "success",
        "conversation_id": conversation_id,
        "explanation": explanation,
        "risk_score": conv.risk_assessment.risk_score,
        "reasons": conv.risk_assessment.reasons,
    }


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: str = Depends(require_analyst),
):
    """
    Deletes a conversation and cascades deletion of its messages,
    threat indicators, and risk assessments.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    db.delete(conv)
    db.commit()

    return {
        "status": "success",
        "message": f"Conversation '{conversation_id}' deleted successfully.",
        "conversation_id": conversation_id,
    }
