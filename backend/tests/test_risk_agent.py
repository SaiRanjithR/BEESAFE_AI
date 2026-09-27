from unittest.mock import MagicMock
import pytest
import anthropic

from app.db.database import SessionLocal
from app.db.models import Conversation, Persona, RiskAssessment
from app.schemas import RiskAssessmentResult
from app.services.risk_agent import (
    run_risk_agent,
    assess_and_upsert_risk,
    RiskAPIError,
    RiskResponseValidationError,
)
from app.services.scammer_bot import (
    SEEDED_FAKE_WALLET,
    SEEDED_FAKE_PAYMENT_HANDLE,
    SEEDED_FAKE_URL,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def sample_conversation(db_session):
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
        channel="simulated",
        scammer_contact="risk_test_scammer_001",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    return conv


def create_mock_client(response_text: str):
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.text = response_text
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_high_risk_scripted_demo_conversation():
    """
    AC 1: Given the full scripted demo conversation from TICKET-003, returns a risk
    score above 80 with at least three specific, transcript-grounded reasons.
    """
    scripted_demo_transcript = [
        {"role": "scammer", "text": "Hi Emily, are we still meeting for lunch today?"},
        {"role": "persona", "text": "Oh, no dear, this is Margaret. You have the wrong number!"},
        {"role": "scammer", "text": "Oh I am so sorry! You seem very nice though, I'm Alex."},
        {"role": "persona", "text": "Nice to meet you Alex. I am a retired teacher living in Ohio."},
        {
            "role": "scammer",
            "text": f"Actually my uncle helped me set up high yield crypto trades at {SEEDED_FAKE_URL} that make 20% weekly.",
        },
        {"role": "persona", "text": "Goodness, that sounds complicated."},
        {
            "role": "scammer",
            "text": f"You can try with just a small test deposit to my trader wallet: {SEEDED_FAKE_WALLET} or {SEEDED_FAKE_PAYMENT_HANDLE}. I will guide you!",
        },
        {"role": "persona", "text": "Oh goodness, that sounds like real money! I have never done crypto."},
        {"role": "scammer", "text": f"Don't worry Margaret, it's 100% risk free. Send funds to {SEEDED_FAKE_WALLET} today!"},
        {"role": "persona", "text": "I need to talk to my son first before doing anything with wallets."},
    ]

    llm_payload = f"""{{
        "risk_score": 92,
        "classification": "pig_butchering_suspected",
        "reasons": [
            "Scammer initiated contact using an artificial 'wrong number' lunch pretext to build trust with Margaret",
            "Scammer introduced an unregulated high-yield crypto trading platform promising unrealistic 20% weekly gains ({SEEDED_FAKE_URL})",
            "Scammer exerted persistent pressure for an immediate test deposit to specific cryptocurrency wallet {SEEDED_FAKE_WALLET} and CashApp {SEEDED_FAKE_PAYMENT_HANDLE}"
        ]
    }}"""

    client = create_mock_client(llm_payload)
    result = run_risk_agent(scripted_demo_transcript, client=client)

    assert isinstance(result, RiskAssessmentResult)
    assert result.risk_score > 80
    assert result.classification == "pig_butchering_suspected"
    assert len(result.reasons) >= 3
    # Check that reasons are transcript-grounded
    assert any("wrong number" in r.lower() for r in result.reasons)
    assert any(SEEDED_FAKE_URL in r for r in result.reasons)
    assert any(SEEDED_FAKE_WALLET in r for r in result.reasons)


def test_benign_small_talk_low_risk():
    """
    AC 2: Given a benign small-talk-only transcript, returns a low risk score (below 30).
    """
    benign_transcript = [
        {"role": "scammer", "text": "Good morning! Beautiful weather today isn't it?"},
        {"role": "persona", "text": "It certainly is! The hydrangeas in my garden are blooming."},
        {"role": "scammer", "text": "I love flowers. Do you have roses as well?"},
        {"role": "persona", "text": "Yes, two rose bushes my late husband planted!"},
    ]

    llm_payload = """{
        "risk_score": 12,
        "classification": "benign_conversation",
        "reasons": [
            "Conversation consists entirely of casual pleasantries and gardening discussion with no financial solicitation"
        ]
    }"""

    client = create_mock_client(llm_payload)
    result = run_risk_agent(benign_transcript, client=client)

    assert result.risk_score < 30
    assert result.classification == "benign_conversation"


def test_upsert_risk_updates_existing_row(db_session, sample_conversation):
    """
    AC 3: Calling assess_and_upsert_risk twice on the same conversation updates the existing
    risk_assessments row rather than creating a second one.
    """
    conv_id = sample_conversation.id

    # 1. First run: early conversation
    payload_1 = """{
        "risk_score": 25,
        "classification": "suspicious_unsolicited_contact",
        "reasons": ["Unsolicited contact from unknown number"]
    }"""
    client_1 = create_mock_client(payload_1)
    record_1 = assess_and_upsert_risk(db_session, conv_id, "Turn 1 hello", client=client_1)

    assert record_1.risk_score == 25
    assert record_1.conversation_id == conv_id

    # Verify 1 record in DB
    all_records = db_session.query(RiskAssessment).filter(RiskAssessment.conversation_id == conv_id).all()
    assert len(all_records) == 1

    # 2. Second run: full conversation with elevated risk
    payload_2 = """{
        "risk_score": 88,
        "classification": "pig_butchering_suspected",
        "reasons": [
            "Wrong number opener",
            "Investment portal pitch",
            "Urgent wallet deposit request"
        ]
    }"""
    client_2 = create_mock_client(payload_2)
    record_2 = assess_and_upsert_risk(db_session, conv_id, "Turn 2 full demo conversation", client=client_2)

    # Verify still exactly 1 record in DB for this conversation
    all_records_updated = db_session.query(RiskAssessment).filter(RiskAssessment.conversation_id == conv_id).all()
    assert len(all_records_updated) == 1
    assert all_records_updated[0].id == record_1.id  # Same row updated!
    assert all_records_updated[0].risk_score == 88
    assert all_records_updated[0].classification == "pig_butchering_suspected"
    assert len(all_records_updated[0].reasons) == 3


def test_risk_agent_error_handling():
    """Verifies API connection error raises RiskAPIError."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())

    with pytest.raises(RiskAPIError):
        run_risk_agent("Some text", client=mock_client)


def test_risk_agent_validation_error():
    """Verifies invalid JSON or missing fields raises RiskResponseValidationError."""
    # Invalid JSON
    client_invalid = create_mock_client("Not a valid json string")
    with pytest.raises(RiskResponseValidationError):
        run_risk_agent("Some text", client=client_invalid)

    # Score > 100
    client_out_of_bounds = create_mock_client('{"risk_score": 150, "classification": "invalid", "reasons": ["test"]}')
    with pytest.raises(RiskResponseValidationError):
        run_risk_agent("Some text", client=client_out_of_bounds)


def test_explain_for_demo_format_and_consistency():
    """
    TICKET-012 AC:
    - Output is a single paragraph, clearly distinct in tone from the technical reasons list,
      but factually consistent with it.
    - Underlying score and classification remain unaltered.
    """
    from app.services.risk_agent import explain_for_demo

    assessment = RiskAssessmentResult(
        risk_score=92,
        classification="pig_butchering_suspected",
        reasons=[
            "Scammer initiated contact using an artificial 'wrong number' lunch pretext to build rapport",
            "Scammer introduced an unregulated high-yield crypto trading platform promising unrealistic 20% weekly gains",
            "Scammer exerted persistent pressure for an immediate test deposit to specific cryptocurrency wallet",
        ],
    )

    mock_narrative = (
        "The actor initiated contact using an artificial social misdirection, pretending to have texted "
        "the wrong number before rapidly steering Margaret toward an unregulated crypto trading scheme. "
        "They promised unrealistic weekly investment returns and aggressively pressured the decoy to send "
        "funds to an unhosted cryptocurrency wallet."
    )
    client = create_mock_client(mock_narrative)

    explanation = explain_for_demo(assessment, client=client)

    # 1. Non-empty string
    assert isinstance(explanation, str)
    assert len(explanation) > 50

    # 2. Single paragraph: no newlines
    assert "\n" not in explanation

    # 3. Tone distinct: no bullet markers
    assert not explanation.strip().startswith("-")
    assert not explanation.strip().startswith("•")
    assert not explanation.strip().startswith("*")

    # 4. Underlying score and classification remain completely untouched
    assert assessment.risk_score == 92
    assert assessment.classification == "pig_butchering_suspected"
    assert len(assessment.reasons) == 3


def test_explain_conversation_endpoint(sample_conversation, db_session):
    """
    TICKET-012 AC:
    POST /conversations/{conversation_id}/explain endpoint generates and persists
    the narrative explanation to the database alongside original reasons.
    """
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from app.main import app
    from app.config import settings

    client = TestClient(app)
    conv_id = sample_conversation.id
    headers = {"x-api-key": settings.INTERNAL_API_KEY}

    # Create risk assessment record without explanation
    risk_rec = RiskAssessment(
        conversation_id=conv_id,
        risk_score=85,
        classification="advance_fee_fraud",
        reasons=["Fraudulent loan upfront fee requested", "Urgency pressure exerted"],
    )
    db_session.add(risk_rec)
    db_session.commit()

    mock_story = (
        "This target is being manipulated with an advance-fee fraud scheme, where the bad actor is "
        "fabricating urgent requirements for upfront loan approval fees."
    )

    with patch("app.routers.conversations.explain_for_demo", return_value=mock_story):
        res = client.post(f"/conversations/{conv_id}/explain", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["explanation"] == mock_story
        assert data["risk_score"] == 85
        assert len(data["reasons"]) == 2

    # Verify database persistence
    db_session.refresh(risk_rec)
    assert risk_rec.explanation == mock_story

