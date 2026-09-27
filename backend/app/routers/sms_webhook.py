import logging
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.db.database import get_db
from app.db.models import Conversation, Message, Persona
from app.services.persona_agent import get_honeypot_reply, PersonaAgentError
from app.services.twilio_client import send_sms, TwilioClientError
from app.services.extraction import extract_and_persist_indicators
from app.services.risk_agent import assess_and_upsert_risk
from app.services.vision_service import caption_image
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Twilio SMS Webhook"])


async def _validate_twilio_signature(request: Request):
    """
    Validates the X-Twilio-Signature header in production mode.
    Skipped in development to allow curl-based testing.
    """
    if settings.ENVIRONMENT == "development":
        return  # Skip validation in dev for curl testing

    auth_token = settings.TWILIO_AUTH_TOKEN
    if not auth_token or auth_token == "placeholder":
        logger.warning("Twilio auth token not configured; skipping signature validation.")
        return

    validator = RequestValidator(auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    form_data = await request.form()
    params = dict(form_data)

    # Reconstruct the full URL Twilio used to call us
    webhook_url = settings.TWILIO_WEBHOOK_URL or str(request.url)

    if not validator.validate(webhook_url, params, signature):
        logger.warning(f"Invalid Twilio signature from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio request signature.",
        )


@router.post("/sms", status_code=status.HTTP_200_OK, dependencies=[Depends(_validate_twilio_signature)])
async def twilio_sms_webhook(
    request: Request,
    db: Session = Depends(get_db),
    From: Optional[str] = Form(None),
    To: Optional[str] = Form(None),
    Body: Optional[str] = Form(None),
    MessageSid: Optional[str] = Form(None),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
    NumMedia: Optional[str] = Form(None),
):
    """
    Receives Twilio inbound SMS/MMS webhook.
    - Validates presence of 'From' and either 'Body' or 'MediaUrl0'.
    - If 'MediaUrl0' is present (MMS), downloads and captions image using Claude Vision,
      injecting '[Image: <caption>]' into the message text representation.
    - Finds or creates active conversation for the sender's phone number.
    - Saves incoming scammer message.
    - Calls honeypot persona agent for reply.
    - If non-flagged, sends reply immediately via Twilio and marks review_status='not_needed'.
    - If flagged, holds reply in review queue with review_status='pending' and DOES NOT send.
    """
    # Validate payload
    if not From or not From.strip():
        logger.warning(f"Malformed webhook received: missing 'From'.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook payload: 'From' field is required.",
        )

    from_number = From.strip()
    clean_body = Body.strip() if Body and Body.strip() else None
    clean_media_url = MediaUrl0.strip() if MediaUrl0 and MediaUrl0.strip() else None

    if not clean_body and not clean_media_url:
        logger.warning(f"Malformed webhook received: neither Body nor MediaUrl0 provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook payload: either 'Body' or 'MediaUrl0' field is required.",
        )

    # Process MMS image attachment if present (TICKET-013)
    caption_part = None
    if clean_media_url:
        try:
            caption = caption_image(clean_media_url, MediaContentType0)
            caption_part = f"[Image: {caption}]"
        except Exception as e:
            logger.error(f"Error handling MMS image {clean_media_url}: {e}")
            caption_part = "[Image: media attachment received]"

    if clean_body and caption_part:
        message_text = f"{clean_body}\n{caption_part}"
    elif caption_part:
        message_text = caption_part
    else:
        message_text = clean_body

    # Look up existing active conversation for this number
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.channel == "sms",
            Conversation.scammer_contact == from_number,
            Conversation.status == "active",
        )
        .first()
    )

    if not conversation:
        # Get or create default persona
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

        conversation = Conversation(
            channel="sms",
            scammer_contact=from_number,
            persona_id=persona.id,
            status="active",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    else:
        persona = conversation.persona

    # Save inbound scammer message
    scammer_msg = Message(
        conversation_id=conversation.id,
        role="scammer",
        text=message_text,
        flagged_action=None,
        review_status="not_needed",
    )
    db.add(scammer_msg)
    db.commit()
    db.refresh(scammer_msg)

    # Extract and persist threat indicators from scammer message
    extract_and_persist_indicators(db, conversation.id, message_text)

    # Fetch full ordered history for this conversation
    history = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )

    # Call persona agent
    try:
        honeypot_reply = get_honeypot_reply(history, persona)
        reply_text = honeypot_reply.reply
        flagged_action = honeypot_reply.flagged_action
    except Exception as e:
        logger.error(f"Persona agent error for conversation {conversation.id}: {e}")
        # Hold in review queue flagged as system_error per Security & Access doc
        error_msg = Message(
            conversation_id=conversation.id,
            role="persona",
            text="[Error generating response: held for analyst review]",
            flagged_action="system_error",
            review_status="pending",
        )
        db.add(error_msg)
        db.commit()
        return Response(content="<Response></Response>", media_type="application/xml")

    # Handle flagged vs non-flagged reply
    if flagged_action is None:
        # Non-flagged: Attempt to send via Twilio
        send_success = True
        try:
            send_sms(to_number=from_number, body=reply_text)
            review_status = "not_needed"
        except TwilioClientError as e:
            logger.error(f"Failed to send outbound SMS via Twilio: {e}")
            send_success = False
            review_status = "send_failed"

        persona_msg = Message(
            conversation_id=conversation.id,
            role="persona",
            text=reply_text,
            flagged_action=None,
            review_status=review_status,
        )
        db.add(persona_msg)
        db.commit()
    else:
        # Flagged: Hold in review queue, DO NOT SEND
        persona_msg = Message(
            conversation_id=conversation.id,
            role="persona",
            text=reply_text,
            flagged_action=flagged_action,
            review_status="pending",
        )
        db.add(persona_msg)
        db.commit()

    # Recalculate risk score for the conversation
    try:
        updated_history = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
            .all()
        )
        assess_and_upsert_risk(db, conversation.id, updated_history)
    except Exception as e:
        logger.warning(f"Async risk assessment warning for conversation {conversation.id}: {e}")

    return Response(content="<Response></Response>", media_type="application/xml")
