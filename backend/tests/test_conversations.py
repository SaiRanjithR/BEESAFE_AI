import uuid
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Conversation, Message, Persona, ThreatIndicator, RiskAssessment


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
def seed_dashboard_data(db_session):
    persona = db_session.query(Persona).first()
    if not persona:
        persona = Persona(
            name="Margaret",
            backstory_json={"age": 68, "occupation": "Retired teacher"},
        )
        db_session.add(persona)
        db_session.commit()
        db_session.refresh(persona)

    # 1. Real SMS conversation
    sms_conv = Conversation(
        channel="sms",
        scammer_contact="+15551234567",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(sms_conv)

    # 2. Simulated conversation
    sim_conv = Conversation(
        channel="simulated",
        scammer_contact="sim_scammer_test_99",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(sim_conv)
    db_session.commit()

    # Add messages to simulated conversation
    m1 = Message(
        conversation_id=sim_conv.id,
        role="scammer",
        text="Hello Margaret, check out https://scam-site.org",
        flagged_action=None,
        review_status="not_needed",
    )
    m2 = Message(
        conversation_id=sim_conv.id,
        role="persona",
        text="What is this site?",
        flagged_action=None,
        review_status="not_needed",
    )
    m3 = Message(
        conversation_id=sim_conv.id,
        role="scammer",
        text="Send $500 to 0x71C63303741cAE444856075c0c457bf433270c35",
        flagged_action=None,
        review_status="not_needed",
    )
    m4 = Message(
        conversation_id=sim_conv.id,
        role="persona",
        text="I cannot do that.",
        flagged_action="payment_request",
        review_status="pending",
    )
    db_session.add_all([m1, m2, m3, m4])

    # Threat indicator
    ti = ThreatIndicator(
        conversation_id=sim_conv.id,
        indicator_type="crypto_wallet",
        value="0x71C63303741cAE444856075c0c457bf433270c35",
        status="pending",
    )
    db_session.add(ti)

    # Risk Assessment
    ra = RiskAssessment(
        conversation_id=sim_conv.id,
        risk_score=85,
        classification="pig_butchering_suspected",
        reasons=["Direct crypto solicitation"],
    )
    db_session.add(ra)

    db_session.commit()
    return sms_conv, sim_conv


def test_list_conversations_endpoint(client, auth_headers, seed_dashboard_data):
    """
    AC 1: Verifies GET /conversations returns conversations with visual channel distinction,
    message counts, risk scores, and pending review flags.
    """
    sms_conv, sim_conv = seed_dashboard_data

    resp = client.get("/conversations", headers={**auth_headers})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    # Check channels exist
    channels = {c["channel"] for c in data}
    assert "sms" in channels
    assert "simulated" in channels

    # Check simulated item has pending review flag and risk score
    matching_sim = next(c for c in data if c["id"] == str(sim_conv.id))
    assert matching_sim["has_pending_review"] is True
    assert matching_sim["risk_score"] == 85
    assert matching_sim["message_count"] == 4


def test_get_conversation_detail_endpoint(client, auth_headers, seed_dashboard_data):
    """
    AC 2: Verifies GET /conversations/{id} returns all messages in chronological order,
    threat indicators, and risk assessment data.
    """
    _, sim_conv = seed_dashboard_data

    resp = client.get(f"/conversations/{sim_conv.id}", headers={**auth_headers})
    assert resp.status_code == 200
    detail = resp.json()

    assert detail["id"] == str(sim_conv.id)
    assert detail["channel"] == "simulated"
    assert detail["persona_name"] == "Margaret"

    # Messages in order
    msgs = detail["messages"]
    assert len(msgs) == 4
    assert msgs[0]["role"] == "scammer"
    assert msgs[1]["role"] == "persona"
    assert msgs[3]["review_status"] == "pending"

    # Indicators
    indicators = detail["threat_indicators"]
    assert len(indicators) == 1
    assert indicators[0]["indicator_type"] == "crypto_wallet"
    assert indicators[0]["value"] == "0x71C63303741cAE444856075c0c457bf433270c35"

    # Risk Assessment
    risk = detail["risk_assessment"]
    assert risk is not None
    assert risk["risk_score"] == 85
    assert risk["classification"] == "pig_butchering_suspected"


def test_start_simulated_conversation_endpoint(client, auth_headers):
    """Verifies POST /simulate/start-conversation initializes a demo conversation."""
    with patch("app.routers.simulated_bot.get_simulated_scammer_reply") as mock_scammer, \
         patch("app.routers.simulated_bot.get_honeypot_reply") as mock_persona:

        mock_scammer.return_value = "Hi Emily, wrong number?"
        mock_persona.return_value = MagicMock(reply="No dear, this is Margaret.", flagged_action=None)

        resp = client.post("/simulate/start-conversation", headers={**auth_headers})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["channel"] == "simulated"
        assert data["messages_count"] == 2
