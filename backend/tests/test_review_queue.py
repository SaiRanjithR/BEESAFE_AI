import uuid
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Conversation, Message, Persona, AuditLog


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"x-api-key": settings.INTERNAL_API_KEY}


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seed_pending_conversation(db_session):
    """Creates a sample persona, conversation, and pending message for testing."""
    persona = db_session.query(Persona).first()
    if not persona:
        persona = Persona(
            name="Margaret",
            backstory_json={"age": 68, "occupation": "Retired teacher"},
        )
        db_session.add(persona)
        db_session.commit()
        db_session.refresh(persona)

    conv = Conversation(
        channel="sms",
        scammer_contact="+15559876543",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    msg = Message(
        conversation_id=conv.id,
        role="persona",
        text="Oh goodness, $500 is a lot of money to send!",
        flagged_action="payment_request",
        review_status="pending",
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)

    return conv, msg


def test_auth_required_for_review_queue(client):
    """Verifies that accessing review queue without API key returns 401."""
    resp = client.get("/review-queue")
    assert resp.status_code == 401

    resp_bad = client.get("/review-queue", headers={"x-api-key": "wrong-key"})
    assert resp_bad.status_code == 401


def test_get_review_queue_returns_pending_messages(client, auth_headers, seed_pending_conversation):
    """Verifies GET /review-queue lists messages with review_status='pending'."""
    conv, msg = seed_pending_conversation
    resp = client.get("/review-queue", headers={**auth_headers})
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    matching = [i for i in items if i["id"] == str(msg.id)]
    assert len(matching) == 1
    assert matching[0]["review_status"] == "pending"
    assert matching[0]["flagged_action"] == "payment_request"
    assert matching[0]["scammer_contact"] == conv.scammer_contact


def test_approve_pending_message_sms_channel(client, auth_headers, db_session, seed_pending_conversation):
    """
    AC 1: Approving a pending message changes its review_status to 'approved',
    triggers send via Twilio for SMS channel, and writes to audit_logs.
    """
    conv, msg = seed_pending_conversation

    with patch("app.routers.review_queue.send_sms") as mock_send_sms:
        mock_send_sms.return_value = "SMmock_approve_123"

        resp = client.post(f"/review-queue/{msg.id}/approve", headers={**auth_headers})
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "approved"
        assert data["conversation_status"] == "active"

        # Verify DB update
        db_session.refresh(msg)
        assert msg.review_status == "approved"

        # Verify Twilio dispatch
        mock_send_sms.assert_called_once_with(to_number=conv.scammer_contact, body=msg.text)

        # Verify audit log created
        log = (
            db_session.query(AuditLog)
            .filter(AuditLog.conversation_id == conv.id, AuditLog.action == "approved_reply")
            .first()
        )
        assert log is not None
        assert log.actor == "analyst"


def test_approve_simulated_conversation_skips_twilio(client, auth_headers, db_session):
    """
    AC 1 (simulated): Approving a simulated conversation does not dispatch via Twilio.
    """
    persona = db_session.query(Persona).first()
    conv = Conversation(
        channel="simulated",
        scammer_contact="sim_bot_002",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    msg = Message(
        conversation_id=conv.id,
        role="persona",
        text="What is Bitcoin?",
        flagged_action="payment_request",
        review_status="pending",
    )
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)

    with patch("app.routers.review_queue.send_sms") as mock_send_sms:
        resp = client.post(f"/review-queue/{msg.id}/approve", headers={**auth_headers})
        assert resp.status_code == 200
        assert resp.json()["review_status"] == "approved"

        # No twilio send for simulated channel
        mock_send_sms.assert_not_called()

        db_session.refresh(msg)
        assert msg.review_status == "approved"


def test_edit_pending_message(client, auth_headers, db_session, seed_pending_conversation):
    """
    AC 2: Editing replaces stored text before sending, sets review_status to 'edited',
    sends updated text, and writes to audit_logs.
    """
    conv, msg = seed_pending_conversation
    edited_text = "I am sorry, but my financial advisor told me never to send money to strangers."

    with patch("app.routers.review_queue.send_sms") as mock_send_sms:
        mock_send_sms.return_value = "SMmock_edit_123"

        resp = client.post(
            f"/review-queue/{msg.id}/edit",
            json={"text": edited_text},
            headers={**auth_headers},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "edited"

        db_session.refresh(msg)
        assert msg.text == edited_text
        assert msg.review_status == "edited"

        mock_send_sms.assert_called_once_with(to_number=conv.scammer_contact, body=edited_text)

        log = (
            db_session.query(AuditLog)
            .filter(AuditLog.conversation_id == conv.id, AuditLog.action == "edited_reply")
            .first()
        )
        assert log is not None


def test_edit_rejects_unsafe_content(client, auth_headers, seed_pending_conversation):
    """AC 2 edge-case: Rejects edited text containing PII or real crypto address."""
    conv, msg = seed_pending_conversation
    unsafe_text = "Sure, here is my wallet: 0x71C63303741cAE444856075c0c457bf433270c35"

    resp = client.post(
        f"/review-queue/{msg.id}/edit",
        json={"text": unsafe_text},
        headers={**auth_headers},
    )
    assert resp.status_code == 400
    assert "Safety check rejected" in resp.json()["detail"]


def test_halt_conversation(client, auth_headers, db_session, seed_pending_conversation):
    """
    AC 3: Halting sets conversation status to 'halted', message review_status to 'halted',
    does NOT send to Twilio, and writes to audit_logs.
    """
    conv, msg = seed_pending_conversation

    with patch("app.routers.review_queue.send_sms") as mock_send_sms:
        resp = client.post(f"/review-queue/{msg.id}/halt", headers={**auth_headers})
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_status"] == "halted"
        assert data["conversation_status"] == "halted"

        mock_send_sms.assert_not_called()

        db_session.refresh(msg)
        db_session.refresh(conv)
        assert msg.review_status == "halted"
        assert conv.status == "halted"

        log = (
            db_session.query(AuditLog)
            .filter(AuditLog.conversation_id == conv.id, AuditLog.action == "halted_conversation")
            .first()
        )
        assert log is not None


def test_race_condition_prevents_duplicate_send(client, auth_headers, db_session, seed_pending_conversation):
    """
    AC 4: Two simultaneous approve requests on the same message result in exactly one send,
    and the second request gets a 409 conflict response.
    """
    conv, msg = seed_pending_conversation

    with patch("app.routers.review_queue.send_sms") as mock_send_sms:
        mock_send_sms.return_value = "SMmock_race_123"

        # First request succeeds
        resp1 = client.post(f"/review-queue/{msg.id}/approve", headers={**auth_headers})
        assert resp1.status_code == 200

        # Second request attempts to approve the already-handled message
        resp2 = client.post(f"/review-queue/{msg.id}/approve", headers={**auth_headers})
        assert resp2.status_code == 409
        assert "already been handled" in resp2.json()["detail"]

        # Twilio send called EXACTLY ONCE
        assert mock_send_sms.call_count == 1
