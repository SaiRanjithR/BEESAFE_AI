import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.database import SessionLocal
from app.db.models import Conversation, Message, Persona, ThreatIndicator


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


@pytest.fixture
def seed_rbac_data(db_session):
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
        text="Can I send you a gift card?",
        flagged_action="payment_request",
        review_status="pending",
    )
    db_session.add(msg)

    indicator = ThreatIndicator(
        conversation_id=conv.id,
        indicator_type="crypto_wallet",
        value=f"1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf{uuid.uuid4().hex[:4]}",
        status="pending",
    )
    db_session.add(indicator)
    db_session.commit()
    db_session.refresh(msg)
    db_session.refresh(indicator)

    return {
        "conversation": conv,
        "message": msg,
        "indicator": indicator,
    }


def test_missing_or_invalid_api_key_returns_401(client, seed_rbac_data):
    """Endpoints require valid API key; missing or bogus keys return 401."""
    conv_id = seed_rbac_data["conversation"].id
    ind_id = seed_rbac_data["indicator"].id

    # No key provided
    assert client.get("/conversations").status_code == 401
    assert client.get("/review-queue").status_code == 401
    assert client.get("/indicators").status_code == 401
    assert client.post(f"/indicators/{ind_id}/block").status_code == 401

    # Invalid / unrecognized key
    bad_headers = {"x-api-key": "completely_invalid_key_xyz"}
    assert client.get("/conversations", headers=bad_headers).status_code == 401
    assert client.get(f"/conversations/{conv_id}", headers=bad_headers).status_code == 401
    assert client.get("/review-queue", headers=bad_headers).status_code == 401
    assert client.get("/indicators", headers=bad_headers).status_code == 401
    assert client.post(f"/indicators/{ind_id}/block", headers=bad_headers).status_code == 401


def test_institution_viewer_permissions(client, seed_rbac_data):
    """
    TICKET-014 AC:
    - Institution Viewer key can call GET /indicators and POST /indicators/{id}/block.
    - Receives HTTP 403 Forbidden on any conversation/message/transcript endpoint.
    """
    inst_headers = {"x-api-key": settings.INSTITUTION_API_KEY}
    conv_id = seed_rbac_data["conversation"].id
    msg_id = seed_rbac_data["message"].id
    ind_id = seed_rbac_data["indicator"].id

    # 1. Allowed: GET /indicators
    res_list = client.get("/indicators", headers=inst_headers)
    assert res_list.status_code == 200
    assert isinstance(res_list.json(), list)

    # 2. Allowed: POST /indicators/{id}/block
    res_block = client.post(f"/indicators/{ind_id}/block", headers=inst_headers)
    assert res_block.status_code == 200
    assert res_block.json()["status"] == "blocked"

    # 3. FORBIDDEN (403): Conversation list
    res_convs = client.get("/conversations", headers=inst_headers)
    assert res_convs.status_code == 403
    assert "Access forbidden" in res_convs.json()["detail"]

    # 4. FORBIDDEN (403): Conversation transcript detail
    res_detail = client.get(f"/conversations/{conv_id}", headers=inst_headers)
    assert res_detail.status_code == 403
    assert "Access forbidden" in res_detail.json()["detail"]

    # 5. FORBIDDEN (403): Explanation endpoint
    res_explain = client.post(f"/conversations/{conv_id}/explain", headers=inst_headers)
    assert res_explain.status_code == 403

    # 6. FORBIDDEN (403): Review Queue endpoints
    res_queue = client.get("/review-queue", headers=inst_headers)
    assert res_queue.status_code == 403

    res_approve = client.post(f"/review-queue/{msg_id}/approve", headers=inst_headers)
    assert res_approve.status_code == 403

    # 7. FORBIDDEN (403): Simulation endpoints
    res_sim = client.post("/simulate/start-conversation", headers=inst_headers)
    assert res_sim.status_code == 403


def test_analyst_permissions(client, seed_rbac_data):
    """
    TICKET-014 AC:
    - Analyst key can access conversation and review-queue endpoints.
    - Receives HTTP 403 Forbidden when calling POST /indicators/{id}/block.
    """
    analyst_headers = {"x-api-key": settings.ANALYST_API_KEY}
    conv_id = seed_rbac_data["conversation"].id
    ind_id = seed_rbac_data["indicator"].id

    # 1. Allowed: GET /conversations
    res_convs = client.get("/conversations", headers=analyst_headers)
    assert res_convs.status_code == 200

    # 2. Allowed: GET /conversations/{id}
    res_detail = client.get(f"/conversations/{conv_id}", headers=analyst_headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["scammer_contact"] == "+15559876543"

    # 3. Allowed: GET /review-queue
    res_queue = client.get("/review-queue", headers=analyst_headers)
    assert res_queue.status_code == 200

    # 4. Allowed: GET /indicators (Analysts can view intelligence)
    res_inds = client.get("/indicators", headers=analyst_headers)
    assert res_inds.status_code == 200

    # 5. FORBIDDEN (403): POST /indicators/{id}/block
    res_block = client.post(f"/indicators/{ind_id}/block", headers=analyst_headers)
    assert res_block.status_code == 403
    assert "Access forbidden" in res_block.json()["detail"]


def test_admin_permissions_unrestricted(client, seed_rbac_data):
    """Admin key has full unrestricted access to all operations."""
    admin_headers = {"x-api-key": settings.ADMIN_API_KEY}
    conv_id = seed_rbac_data["conversation"].id
    ind_id = seed_rbac_data["indicator"].id

    # Admin can list conversations
    assert client.get("/conversations", headers=admin_headers).status_code == 200

    # Admin can view review queue
    assert client.get("/review-queue", headers=admin_headers).status_code == 200

    # Admin can list indicators
    assert client.get("/indicators", headers=admin_headers).status_code == 200

    # Admin can block indicators
    res_block = client.post(f"/indicators/{ind_id}/block", headers=admin_headers)
    assert res_block.status_code == 200
    assert res_block.json()["status"] == "blocked"
