import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import SessionLocal
from app.db.models import Persona, Conversation, ThreatIndicator
from app.services.enrichment import (
    parse_domain,
    lookup_rdap_domain_age,
    lookup_url_blocklist,
    perform_local_enrichment,
    trigger_url_enrichment,
)
from app.services.extraction import extract_and_persist_indicators


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


def test_parse_domain_utility():
    assert parse_domain("https://apex-yield-trade.com/portal/login?id=123") == "apex-yield-trade.com"
    assert parse_domain("http://sub.domain.org/path") == "sub.domain.org"
    assert parse_domain("portal.scam.xyz") == "portal.scam.xyz"
    assert parse_domain("") == ""


def test_lookup_rdap_seeded_domain_simulation():
    """Seeded fake domains return simulated brand-new domain age (4 days)."""
    age = lookup_rdap_domain_age("apex-yield-trade.com")
    assert age == 4


def test_lookup_rdap_network_error_graceful_handling():
    """RDAP failure or timeout must return None and NEVER raise an exception."""
    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("Connection timed out to rdap.org")

    age = lookup_rdap_domain_age("unknown-failing-domain.com", client=mock_client)
    assert age is None


def test_lookup_url_blocklist_detection():
    # Known bad domain / keyword
    assert lookup_url_blocklist("https://apex-yield-trade.com/portal", "apex-yield-trade.com") is True
    assert lookup_url_blocklist("https://fraudulent-crypto.xyz/login", "fraudulent-crypto.xyz") is True
    # Benign domain
    assert lookup_url_blocklist("https://google.com/search", "google.com") is False


def test_perform_local_enrichment():
    ind_id = uuid.uuid4()
    url = "https://apex-yield-trade.com/portal"
    res = perform_local_enrichment(ind_id, url)

    assert res["indicator_id"] == ind_id
    assert res["known_bad"] is True
    assert res["domain_age_days"] == 4


def test_enrichment_webhook_callback_updates_indicator(client, db_session):
    """
    Tests POST /webhook/enrichment-result updates the threat indicator record with
    known_bad and domain_age_days, returning 200.
    """
    persona = Persona(name="EnrichTestPersona", backstory_json={})
    db_session.add(persona)
    db_session.commit()

    conv = Conversation(channel="simulated", scammer_contact="scammer_enrich_1", persona_id=persona.id)
    db_session.add(conv)
    db_session.commit()

    ind = ThreatIndicator(
        conversation_id=conv.id,
        indicator_type="url",
        value="https://test-suspicious-domain.com/auth",
        status="pending",
    )
    db_session.add(ind)
    db_session.commit()
    db_session.refresh(ind)

    # Initial state
    assert ind.known_bad is None
    assert ind.domain_age_days is None

    # Call /webhook/enrichment-result
    payload = {
        "indicator_id": str(ind.id),
        "known_bad": True,
        "domain_age_days": 12,
    }
    response = client.post("/webhook/enrichment-result", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["known_bad"] is True
    assert data["domain_age_days"] == 12

    # Verify DB update
    db_session.expire_all()
    updated_ind = db_session.query(ThreatIndicator).filter(ThreatIndicator.id == ind.id).first()
    assert updated_ind.known_bad is True
    assert updated_ind.domain_age_days == 12


def test_enrichment_webhook_callback_not_found(client):
    fake_id = str(uuid.uuid4())
    payload = {
        "indicator_id": fake_id,
        "known_bad": False,
        "domain_age_days": 500,
    }
    response = client.post("/webhook/enrichment-result", json=payload)
    assert response.status_code == 404


def test_extraction_automatically_triggers_url_enrichment(db_session):
    """
    TICKET-011 Acceptance Criterion 1:
    A newly extracted URL indicator triggers the workflow automatically
    (via the backend calling the enrichment dispatcher after TICKET-006 extraction runs).
    """
    persona = Persona(name="AutoEnrichPersona", backstory_json={})
    db_session.add(persona)
    db_session.commit()

    conv = Conversation(channel="simulated", scammer_contact="auto_enrich_scammer", persona_id=persona.id)
    db_session.add(conv)
    db_session.commit()

    test_url = f"https://apex-yield-trade.com/portal/test_{uuid.uuid4().hex[:6]}"
    transcript = f"Here is the link: {test_url} please deposit soon."

    # Run extraction
    new_inds = extract_and_persist_indicators(db_session, conv.id, transcript)
    assert len(new_inds) >= 1

    url_ind = next(it for it in new_inds if it.indicator_type == "url")
    assert url_ind.value == test_url

    # Verify enrichment ran automatically and populated fields
    db_session.expire_all()
    refreshed_ind = db_session.query(ThreatIndicator).filter(ThreatIndicator.id == url_ind.id).first()
    assert refreshed_ind.domain_age_days == 4
    assert refreshed_ind.known_bad is True


def test_trigger_url_enrichment_with_mocked_n8n_webhook(db_session):
    """
    Verifies that when N8N_ENRICHMENT_ENABLED is True and webhook URL is configured,
    trigger_url_enrichment calls the external n8n webhook.
    """
    persona = Persona(name="N8NMockPersona", backstory_json={})
    db_session.add(persona)
    db_session.commit()

    conv = Conversation(channel="simulated", scammer_contact="n8n_scammer", persona_id=persona.id)
    db_session.add(conv)
    db_session.commit()

    ind = ThreatIndicator(
        conversation_id=conv.id,
        indicator_type="url",
        value="https://example-n8n-target.com/page",
        status="pending",
    )
    db_session.add(ind)
    db_session.commit()
    db_session.refresh(ind)

    with patch("app.services.enrichment.settings.N8N_ENRICHMENT_ENABLED", True), \
         patch("app.services.enrichment.settings.N8N_WEBHOOK_URL", "http://n8n-test:5678/webhook/enrich"), \
         patch("httpx.Client.post") as mock_post:

        mock_post.return_value = MagicMock(status_code=200)

        trigger_url_enrichment(ind.id, ind.value)

        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://n8n-test:5678/webhook/enrich"
        assert call_args[1]["json"]["indicator_id"] == str(ind.id)
        assert call_args[1]["json"]["value"] == ind.value
