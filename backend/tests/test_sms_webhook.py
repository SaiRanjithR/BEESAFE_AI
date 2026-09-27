from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.db.models import Conversation, Message
from app.schemas import HoneypotReply
from app.services.twilio_client import TwilioSendError


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_webhook_creates_new_conversation_and_sends_non_flagged(client, db_session):
    """
    AC 1 & 2: Test POST creates a new conversation on first contact,
    sends non-flagged reply via Twilio, and saves with review_status='not_needed'.
    """
    test_number = "+15550001111"
    
    # Cleanup previous runs if any
    existing_convs = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).all()
    for c in existing_convs:
        db_session.delete(c)
    db_session.commit()

    with patch("app.routers.sms_webhook.get_honeypot_reply") as mock_agent, \
         patch("app.routers.sms_webhook.send_sms") as mock_send_sms:

        mock_agent.return_value = HoneypotReply(
            reply="Hello dear! Who is this?",
            flagged_action=None,
        )
        mock_send_sms.return_value = "SMmock_sid_123"

        response = client.post(
            "/webhook/sms",
            data={
                "From": test_number,
                "To": "+15559990000",
                "Body": "Hello there, nice to meet you!",
                "MessageSid": "SM_inbound_001",
            },
        )

        assert response.status_code == 200
        assert "<Response></Response>" in response.text

        # Verify conversation created in DB
        conv = (
            db_session.query(Conversation)
            .filter(Conversation.scammer_contact == test_number)
            .first()
        )
        assert conv is not None
        assert conv.channel == "sms"
        assert conv.status == "active"

        # Verify messages
        msgs = db_session.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
        assert len(msgs) == 2
        assert msgs[0].role == "scammer"
        assert msgs[0].text == "Hello there, nice to meet you!"
        assert msgs[0].review_status == "not_needed"

        assert msgs[1].role == "persona"
        assert msgs[1].text == "Hello dear! Who is this?"
        assert msgs[1].review_status == "not_needed"
        assert msgs[1].flagged_action is None

        # Verify Twilio send called
        mock_send_sms.assert_called_once_with(to_number=test_number, body="Hello dear! Who is this?")


def test_webhook_appends_to_existing_conversation(client, db_session):
    """
    AC 1: A repeat contact on the same phone number appends to the existing active conversation.
    """
    test_number = "+15550001111"

    with patch("app.routers.sms_webhook.get_honeypot_reply") as mock_agent, \
         patch("app.routers.sms_webhook.send_sms") as mock_send_sms:

        mock_agent.return_value = HoneypotReply(
            reply="I love gardening!",
            flagged_action=None,
        )

        response = client.post(
            "/webhook/sms",
            data={
                "From": test_number,
                "To": "+15559990000",
                "Body": "What are your hobbies?",
                "MessageSid": "SM_inbound_002",
            },
        )

        assert response.status_code == 200

        # Verify there is still only 1 conversation for this number
        convs = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).all()
        assert len(convs) == 1
        conv = convs[0]

        # Verify messages appended
        msgs = db_session.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
        assert len(msgs) == 4
        assert msgs[2].text == "What are your hobbies?"
        assert msgs[3].text == "I love gardening!"


def test_webhook_flagged_reply_held_in_review_queue(client, db_session):
    """
    AC 3: A flagged reply is saved with review_status='pending' and is NOT sent to Twilio.
    """
    test_number = "+15550002222"

    existing_convs = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).all()
    for c in existing_convs:
        db_session.delete(c)
    db_session.commit()

    with patch("app.routers.sms_webhook.get_honeypot_reply") as mock_agent, \
         patch("app.routers.sms_webhook.send_sms") as mock_send_sms:

        mock_agent.return_value = HoneypotReply(
            reply="Oh my goodness, $1000 is too much money!",
            flagged_action="payment_request",
        )

        response = client.post(
            "/webhook/sms",
            data={
                "From": test_number,
                "To": "+15559990000",
                "Body": "Wire $1000 right now to my account",
                "MessageSid": "SM_inbound_003",
            },
        )

        assert response.status_code == 200

        conv = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).first()
        assert conv is not None

        msgs = db_session.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
        assert len(msgs) == 2
        assert msgs[1].role == "persona"
        assert msgs[1].flagged_action == "payment_request"
        assert msgs[1].review_status == "pending"

        # Verify Twilio was NOT called
        mock_send_sms.assert_not_called()


def test_webhook_malformed_payload_returns_400(client):
    """
    AC 4: Malformed webhook payloads (missing From or Body) return HTTP 400 without crashing.
    """
    # Missing From
    resp1 = client.post("/webhook/sms", data={"Body": "Hello"})
    assert resp1.status_code == 400

    # Missing Body
    resp2 = client.post("/webhook/sms", data={"From": "+15551234567"})
    assert resp2.status_code == 400

    # Empty strings
    resp3 = client.post("/webhook/sms", data={"From": "", "Body": "   "})
    assert resp3.status_code == 400


def test_webhook_twilio_send_failure_marks_send_failed(client, db_session):
    """
    Edge case: If Twilio send fails, mark message review_status='send_failed' in DB.
    """
    test_number = "+15550003333"

    existing_convs = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).all()
    for c in existing_convs:
        db_session.delete(c)
    db_session.commit()

    with patch("app.routers.sms_webhook.get_honeypot_reply") as mock_agent, \
         patch("app.routers.sms_webhook.send_sms") as mock_send_sms:

        mock_agent.return_value = HoneypotReply(
            reply="Sure, tell me more.",
            flagged_action=None,
        )
        mock_send_sms.side_effect = TwilioSendError("Twilio network error")

        response = client.post(
            "/webhook/sms",
            data={
                "From": test_number,
                "To": "+15559990000",
                "Body": "Hello!",
                "MessageSid": "SM_inbound_004",
            },
        )

        assert response.status_code == 200

        conv = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).first()
        msgs = db_session.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
        assert len(msgs) == 2
        assert msgs[1].review_status == "send_failed"


def test_webhook_inbound_mms_image_captioned_and_saved(client, db_session):
    """
    TICKET-013 AC:
    - Inbound MMS with MediaUrl0 produces saved message with [Image: <caption>] text representation.
    - Persona agent receives the captioned content and can meaningfully reference it.
    - Does not crash or silently drop.
    """
    test_number = "+15550007777"
    media_url = "https://api.twilio.com/2010-04-01/Accounts/ACtest/Messages/MMtest/Media/MEtest"
    fake_caption = "A luxury gold watch and a forged bank check for $75,000"

    existing_convs = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).all()
    for c in existing_convs:
        db_session.delete(c)
    db_session.commit()

    captured_texts = []

    def mock_get_reply(history, persona):
        nonlocal captured_texts
        captured_texts = [getattr(m, "text", "") for m in history]
        return HoneypotReply(
            reply="Goodness gracious, that watch looks very expensive! Whose check is that?",
            flagged_action=None,
        )

    with patch("app.routers.sms_webhook.caption_image", return_value=fake_caption) as mock_caption, \
         patch("app.routers.sms_webhook.get_honeypot_reply", side_effect=mock_get_reply), \
         patch("app.routers.sms_webhook.send_sms") as mock_send_sms:

        mock_send_sms.return_value = "SMmock_sid_777"

        # Note: Inbound MMS with only image, no text Body
        response = client.post(
            "/webhook/sms",
            data={
                "From": test_number,
                "To": "+15559990000",
                "MediaUrl0": media_url,
                "MediaContentType0": "image/jpeg",
                "MessageSid": "MM_inbound_mms_001",
            },
        )

        assert response.status_code == 200
        mock_caption.assert_called_once_with(media_url, "image/jpeg")

        # Verify conversation and saved messages
        conv = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).first()
        assert conv is not None
        msgs = db_session.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
        assert len(msgs) == 2

        # 1. Scammer inbound message has [Image: <caption>] format
        assert msgs[0].role == "scammer"
        assert msgs[0].text == f"[Image: {fake_caption}]"

        # 2. Persona agent received history with captioned text
        assert len(captured_texts) >= 1
        assert captured_texts[-1] == f"[Image: {fake_caption}]"

        # 3. Persona replied in context and Twilio dispatched
        assert msgs[1].role == "persona"
        assert "watch looks very expensive" in msgs[1].text
        mock_send_sms.assert_called_once()


def test_webhook_inbound_mms_with_text_and_image(client, db_session):
    """
    Tests MMS where sender includes both text body and MediaUrl0 image.
    Format should be: {body}\n[Image: {caption}]
    """
    test_number = "+15550008888"
    media_url = "https://api.twilio.com/2010-04-01/Accounts/ACtest/Messages/MMtest/Media/ME888"
    fake_caption = "Crypto trading screenshot with 5.2 BTC"

    existing_convs = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).all()
    for c in existing_convs:
        db_session.delete(c)
    db_session.commit()

    with patch("app.routers.sms_webhook.caption_image", return_value=fake_caption), \
         patch("app.routers.sms_webhook.get_honeypot_reply") as mock_agent, \
         patch("app.routers.sms_webhook.send_sms"):

        mock_agent.return_value = HoneypotReply(
            reply="Oh my, that is quite a lot of Bitcoin.",
            flagged_action=None,
        )

        response = client.post(
            "/webhook/sms",
            data={
                "From": test_number,
                "To": "+15559990000",
                "Body": "Look at my daily profits!",
                "MediaUrl0": media_url,
                "MediaContentType0": "image/png",
                "MessageSid": "MM_inbound_mms_002",
            },
        )

        assert response.status_code == 200

        conv = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).first()
        msgs = db_session.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
        assert msgs[0].text == f"Look at my daily profits!\n[Image: {fake_caption}]"


def test_webhook_inbound_mms_caption_failure_resilience(client, db_session):
    """
    AC: An inbound MMS with an image produces a saved message with a
    [Image: <caption>]-style text representation, not a crash or silent drop.
    Even if caption_image raises an unexpected exception.
    """
    test_number = "+15550009999"
    media_url = "https://example.com/broken_image.jpg"

    existing_convs = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).all()
    for c in existing_convs:
        db_session.delete(c)
    db_session.commit()

    with patch("app.routers.sms_webhook.caption_image", side_effect=Exception("Critical network failure")), \
         patch("app.routers.sms_webhook.get_honeypot_reply") as mock_agent, \
         patch("app.routers.sms_webhook.send_sms"):

        mock_agent.return_value = HoneypotReply(
            reply="I cannot see what you sent, dear.",
            flagged_action=None,
        )

        response = client.post(
            "/webhook/sms",
            data={
                "From": test_number,
                "To": "+15559990000",
                "MediaUrl0": media_url,
            },
        )

        assert response.status_code == 200

        conv = db_session.query(Conversation).filter(Conversation.scammer_contact == test_number).first()
        msgs = db_session.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
        assert len(msgs) == 2
        assert "[Image:" in msgs[0].text
        assert "media attachment received" in msgs[0].text

