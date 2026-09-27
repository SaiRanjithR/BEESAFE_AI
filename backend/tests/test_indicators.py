import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.database import get_db, SessionLocal
from app.db.models import Persona, Conversation, Message, ThreatIndicator, RiskAssessment, AuditLog


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    return {"x-api-key": settings.INTERNAL_API_KEY}


@pytest.fixture
def sample_data(db_session):
    # Create persona
    persona = Persona(
        name="InstitutionTestPersona",
        backstory_json={"secret": "Classified Honeypot Strategy", "age": 68},
    )
    db_session.add(persona)
    db_session.commit()
    db_session.refresh(persona)

    # Conversation 1: High risk
    conv1 = Conversation(
        channel="simulated",
        scammer_contact="fake_scammer_high",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(conv1)
    db_session.commit()
    db_session.refresh(conv1)

    # Add private messages in conv1
    msg1 = Message(
        conversation_id=conv1.id,
        role="scammer",
        text="Send ETH to 0x71C63303741cAE444856075c0c457bf433270c35",
        review_status="not_needed",
    )
    msg2 = Message(
        conversation_id=conv1.id,
        role="persona",
        text="I am Margaret and I have retirement money",
        review_status="not_needed",
    )
    db_session.add_all([msg1, msg2])

    ind1 = ThreatIndicator(
        conversation_id=conv1.id,
        indicator_type="crypto_wallet",
        value="0x71C63303741cAE444856075c0c457bf433270c35",
        status="pending",
    )
    ind2 = ThreatIndicator(
        conversation_id=conv1.id,
        indicator_type="url",
        value="https://fraudulent-apex-trading.xyz/login",
        status="pending",
    )
    risk1 = RiskAssessment(
        conversation_id=conv1.id,
        risk_score=92,
        classification="pig_butchering_suspected",
        reasons=["High-pressure cryptocurrency deposit request", "Known deceptive trading domain"],
    )
    db_session.add_all([ind1, ind2, risk1])

    # Conversation 2: Low risk
    conv2 = Conversation(
        channel="sms",
        scammer_contact="+15559876543",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(conv2)
    db_session.commit()
    db_session.refresh(conv2)

    ind3 = ThreatIndicator(
        conversation_id=conv2.id,
        indicator_type="phone_number",
        value="+15559876543",
        status="pending",
    )
    risk2 = RiskAssessment(
        conversation_id=conv2.id,
        risk_score=25,
        classification="benign",
        reasons=["Standard wrong number opening with no financial request"],
    )
    db_session.add_all([ind3, risk2])
    db_session.commit()

    db_session.refresh(ind1)
    db_session.refresh(ind2)
    db_session.refresh(ind3)

    return {
        "persona": persona,
        "conv1": conv1,
        "conv2": conv2,
        "ind1": ind1,
        "ind2": ind2,
        "ind3": ind3,
    }


def test_indicators_endpoint_requires_auth(client):
    res = client.get("/indicators")
    assert res.status_code == 401


def test_indicators_endpoint_returns_indicators_with_risk_scores(client, auth_headers, sample_data):
    res = client.get("/indicators", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 3

    # Check structure of returned objects
    first = next(item for item in data if item["id"] == str(sample_data["ind1"].id))
    assert first["indicator_type"] == "crypto_wallet"
    assert first["value"] == "0x71C63303741cAE444856075c0c457bf433270c35"
    assert first["status"] == "pending"
    assert first["risk_score"] == 92
    assert first["risk_classification"] == "pig_butchering_suspected"
    assert len(first["risk_reasons"]) == 2


def test_indicators_endpoint_role_boundary_strict_privacy(client, auth_headers, sample_data):
    """
    CRITICAL ACCEPTANCE CRITERION:
    The /indicators endpoint never includes conversation transcript or persona data
    in its response — only indicator + risk-score-level data, enforced server-side.
    """
    res = client.get("/indicators", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    # Convert entire JSON response payload to lowercase string
    raw_payload_text = res.text.lower()

    # Verify that no private transcript or persona details leaked
    assert "retirement money" not in raw_payload_text
    assert "classified honeypot strategy" not in raw_payload_text
    assert "margaret" not in raw_payload_text

    # Verify key absence on dictionary keys
    for item in data:
        assert "messages" not in item
        assert "transcript" not in item
        assert "persona" not in item
        assert "persona_name" not in item
        assert "backstory" not in item


def test_indicators_filtering_and_sorting(client, auth_headers, sample_data):
    # Filter by type
    res_type = client.get("/indicators?type=crypto_wallet", headers=auth_headers)
    assert res_type.status_code == 200
    items_type = res_type.json()
    for it in items_type:
        assert it["indicator_type"] == "crypto_wallet"

    # Filter by min_risk
    res_risk = client.get("/indicators?min_risk=80", headers=auth_headers)
    assert res_risk.status_code == 200
    items_risk = res_risk.json()
    for it in items_risk:
        assert it["risk_score"] >= 80

    # Sort by risk_asc
    res_asc = client.get("/indicators?sort_by=risk_asc", headers=auth_headers)
    assert res_asc.status_code == 200
    items_asc = res_asc.json()
    scores = [it["risk_score"] for it in items_asc if it["risk_score"] is not None]
    assert scores == sorted(scores)


def test_block_indicator_success_and_audit_log(client, auth_headers, db_session, sample_data):
    ind = sample_data["ind1"]
    assert ind.status == "pending"

    # Count audit logs before
    initial_audit_count = db_session.query(AuditLog).filter(
        AuditLog.conversation_id == ind.conversation_id,
        AuditLog.action == "blocked_indicator",
    ).count()

    # Block the indicator
    res = client.post(f"/indicators/{ind.id}/block", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "blocked"
    assert data["current_status"] == "blocked"
    assert data["indicator_id"] == str(ind.id)

    # Verify DB status
    db_session.expire_all()
    updated_ind = db_session.query(ThreatIndicator).filter(ThreatIndicator.id == ind.id).first()
    assert updated_ind.status == "blocked"

    # Verify audit log created
    post_audit_count = db_session.query(AuditLog).filter(
        AuditLog.conversation_id == ind.conversation_id,
        AuditLog.action == "blocked_indicator",
    ).count()
    assert post_audit_count == initial_audit_count + 1

    latest_audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.conversation_id == ind.conversation_id, AuditLog.action == "blocked_indicator")
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert latest_audit.actor == "institution_viewer"


def test_block_indicator_idempotency_prevents_duplicate_audit_log(client, auth_headers, db_session, sample_data):
    """
    CRITICAL ACCEPTANCE CRITERION:
    Clicking twice on an already-blocked row doesn't error or duplicate the audit log entry.
    """
    ind = sample_data["ind2"]

    # First block call
    res1 = client.post(f"/indicators/{ind.id}/block", headers=auth_headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "blocked"

    db_session.expire_all()
    audit_count_after_first = db_session.query(AuditLog).filter(
        AuditLog.conversation_id == ind.conversation_id,
        AuditLog.action == "blocked_indicator",
    ).count()

    # Second block call (idempotent)
    res2 = client.post(f"/indicators/{ind.id}/block", headers=auth_headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_blocked"
    assert res2.json()["current_status"] == "blocked"

    db_session.expire_all()
    audit_count_after_second = db_session.query(AuditLog).filter(
        AuditLog.conversation_id == ind.conversation_id,
        AuditLog.action == "blocked_indicator",
    ).count()

    # Must NOT have created a second audit log row
    assert audit_count_after_second == audit_count_after_first


def test_block_nonexistent_indicator_returns_404(client, auth_headers):
    fake_id = uuid.uuid4()
    res = client.post(f"/indicators/{fake_id}/block", headers=auth_headers)
    assert res.status_code == 404


def test_multi_conversation_correlation_count(client, auth_headers, db_session):
    """
    TICKET-010 Acceptance Criteria:
    - Running simulated bot with its constant seeded fake payment handle across 2-3 separate
      conversations results in that indicator showing a count of 2-3 on the Institution Dashboard.
    - Count updates correctly as new matching indicators are extracted.
    """
    unique_suffix = uuid.uuid4().hex[:8]
    test_handle = f"$ApexYieldTest_{unique_suffix}"
    unique_phone = f"+1555{uuid.uuid4().hex[:7]}"

    # 1. Create a persona
    persona = Persona(name=f"CorrelationTestPersona_{unique_suffix}", backstory_json={"age": 55})
    db_session.add(persona)
    db_session.commit()

    # 2. Create 3 distinct conversations
    convs = []
    for i in range(3):
        conv = Conversation(
            channel="simulated",
            scammer_contact=f"simulated_scammer_corr_{unique_suffix}_{i}",
            persona_id=persona.id,
            status="active",
        )
        db_session.add(conv)
        convs.append(conv)
    db_session.commit()

    # 3. Add test_handle to all 3 conversations
    for conv in convs:
        ind = ThreatIndicator(
            conversation_id=conv.id,
            indicator_type="payment_handle",
            value=test_handle,
            status="pending",
        )
        db_session.add(ind)

    # Add a unique indicator to only conversation 0
    unique_ind = ThreatIndicator(
        conversation_id=convs[0].id,
        indicator_type="phone_number",
        value=unique_phone,
        status="pending",
    )
    db_session.add(unique_ind)
    db_session.commit()

    # 4. Fetch indicators from API
    res = client.get("/indicators", headers=auth_headers)
    assert res.status_code == 200
    items = res.json()

    # Verify test_handle has conversation_count == 3
    handle_items = [it for it in items if it["value"] == test_handle]
    assert len(handle_items) == 3
    for it in handle_items:
        assert it["conversation_count"] == 3

    # Verify unique indicator has conversation_count == 1
    unique_items = [it for it in items if it["value"] == unique_phone]
    assert len(unique_items) == 1
    assert unique_items[0]["conversation_count"] == 1

    # 5. Test Criterion 2: Count updates correctly as a 4th conversation extracts the same handle
    conv4 = Conversation(
        channel="simulated",
        scammer_contact=f"simulated_scammer_corr_{unique_suffix}_4",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(conv4)
    db_session.commit()

    ind4 = ThreatIndicator(
        conversation_id=conv4.id,
        indicator_type="payment_handle",
        value=test_handle,
        status="pending",
    )
    db_session.add(ind4)
    db_session.commit()

    # Re-fetch indicators
    res2 = client.get("/indicators", headers=auth_headers)
    assert res2.status_code == 200
    items2 = res2.json()

    handle_items2 = [it for it in items2 if it["value"] == test_handle]
    assert len(handle_items2) == 4
    for it in handle_items2:
        assert it["conversation_count"] == 4


def test_indicators_correlated_only_filter(client, auth_headers):
    res = client.get("/indicators?correlated_only=true", headers=auth_headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) > 0
    for it in items:
        assert it["conversation_count"] > 1


def test_indicators_sort_by_correlated_desc(client, auth_headers):
    res = client.get("/indicators?sort_by=correlated_desc", headers=auth_headers)
    assert res.status_code == 200
    items = res.json()
    counts = [it["conversation_count"] for it in items]
    assert counts == sorted(counts, reverse=True)
