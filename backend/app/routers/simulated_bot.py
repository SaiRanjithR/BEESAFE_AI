import logging
import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db.database import get_db, SessionLocal
from app.db.models import Conversation, Message, Persona
from app.services.persona_agent import get_honeypot_reply
from app.services.scammer_bot import get_simulated_scammer_reply
from app.services.extraction import extract_and_persist_indicators
from app.services.risk_agent import assess_and_upsert_risk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulate", tags=["Simulated Scammer Bot"])


def _run_background_risk_assessment(conversation_id: uuid.UUID, history_snapshot: list):
    """Executes risk agent asynchronously in background so turn generation returns immediately."""
    bg_db = SessionLocal()
    try:
        assess_and_upsert_risk(bg_db, conversation_id, history_snapshot)
    except Exception as e:
        logger.warning(f"Background risk assessment notice for {conversation_id}: {e}")
    finally:
        bg_db.close()


@router.post("/start-conversation")
def start_simulated_conversation(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """
    Creates a new simulated conversation and runs the opening turn
    between the simulated scammer bot and the honeypot persona.
    """
    persona = db.query(Persona).first()
    if not persona:
        persona = Persona(
            name="Margaret",
            backstory_json={
                "age": 68,
                "occupation": "Retired teacher",
                "financial_posture": "Modest retirement savings, cautious with technology",
                "personality_traits": ["warm", "polite", "trusting"],
            },
        )
        db.add(persona)
        db.commit()
        db.refresh(persona)

    short_id = uuid.uuid4().hex[:6]
    conv = Conversation(
        channel="simulated",
        scammer_contact=f"sim_scammer_{short_id}",
        persona_id=persona.id,
        status="active",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    # Scammer opening turn (Turn 1)
    try:
        scammer_text = get_simulated_scammer_reply([], turn_number=1)
    except Exception:
        scammer_text = "Hi Emily, are we still meeting for lunch today?"

    scammer_msg = Message(
        conversation_id=conv.id,
        role="scammer",
        text=scammer_text,
        flagged_action=None,
        review_status="not_needed",
    )
    db.add(scammer_msg)
    db.commit()

    # Extract indicators
    extract_and_persist_indicators(db, conv.id, scammer_text)

    # Persona turn (Turn 2)
    history = [scammer_msg]
    try:
        honeypot_reply = get_honeypot_reply(history, persona)
        persona_text = honeypot_reply.reply
        flagged_action = honeypot_reply.flagged_action
    except Exception:
        persona_text = "Oh, no dear, this is Margaret. You have the wrong number!"
        flagged_action = None

    review_status = "pending" if flagged_action else "not_needed"
    persona_msg = Message(
        conversation_id=conv.id,
        role="persona",
        text=persona_text,
        flagged_action=flagged_action,
        review_status=review_status,
    )
    db.add(persona_msg)
    db.commit()

    # Update risk score in background
    history_snapshot = [
        {"role": "scammer", "text": scammer_text},
        {"role": "persona", "text": persona_text},
    ]
    background_tasks.add_task(_run_background_risk_assessment, conv.id, history_snapshot)

    return {
        "status": "success",
        "conversation_id": conv.id,
        "channel": conv.channel,
        "scammer_contact": conv.scammer_contact,
        "messages_count": 2,
    }


@router.post("/{conversation_id}/next-turn")
def advance_simulated_conversation(
    conversation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    """
    Advances a simulated conversation by running the next turn of the
    scammer bot, followed by the honeypot persona response.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if conv.status == "halted":
        raise HTTPException(status_code=400, detail="Cannot advance a halted conversation.")

    # Check if there is an unresolved pending message
    pending_msg = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.review_status == "pending")
        .first()
    )
    if pending_msg:
        raise HTTPException(
            status_code=400,
            detail="Cannot advance while a reply is pending human review in the review queue.",
        )

    history = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    # Scammer turn
    turn_num = len(history) + 1
    try:
        scammer_text = get_simulated_scammer_reply(history, turn_number=turn_num)
    except Exception as e:
        logger.error(f"Scammer bot turn error: {e}")
        scammer_text = "I wanted to check if you had a chance to look at that investment link?"

    scammer_msg = Message(
        conversation_id=conv.id,
        role="scammer",
        text=scammer_text,
        flagged_action=None,
        review_status="not_needed",
    )
    db.add(scammer_msg)
    db.commit()

    # Extract indicators
    extract_and_persist_indicators(db, conv.id, scammer_text)

    # Persona reply
    updated_history = history + [scammer_msg]
    try:
        honeypot_reply = get_honeypot_reply(updated_history, conv.persona)
        persona_text = honeypot_reply.reply
        flagged_action = honeypot_reply.flagged_action
    except Exception as e:
        logger.error(f"Persona agent turn error: {e}")
        persona_text = "I am a bit confused by this."
        flagged_action = None

    review_status = "pending" if flagged_action else "not_needed"
    persona_msg = Message(
        conversation_id=conv.id,
        role="persona",
        text=persona_text,
        flagged_action=flagged_action,
        review_status=review_status,
    )
    db.add(persona_msg)
    db.commit()

    # Assess risk asynchronously in background so turn returns in ~2s to user
    history_snapshot = [
        {"role": m.role, "text": m.text} for m in updated_history + [persona_msg]
    ]
    background_tasks.add_task(_run_background_risk_assessment, conv.id, history_snapshot)

    return {
        "status": "success",
        "conversation_id": conv.id,
        "scammer_reply": scammer_text,
        "persona_reply": persona_text,
        "flagged_action": flagged_action,
        "review_status": review_status,
    }
