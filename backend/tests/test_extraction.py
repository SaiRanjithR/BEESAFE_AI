import uuid
import pytest
from app.db.database import SessionLocal
from app.db.models import Conversation, Persona, ThreatIndicator
from app.services.extraction import (
    extract_indicators,
    extract_and_persist_indicators,
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
        channel="sms",
        scammer_contact="+15557778888",
        persona_id=persona.id,
        status="active",
    )
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    return conv


def test_extract_all_four_indicator_types():
    """
    AC 1: Given a transcript containing one of each indicator type,
    all four are correctly extracted with the correct indicator_type label.
    """
    transcript = (
        "Hey! Check out our trading system at https://apex-yield-trade.com/portal! "
        "You can call my broker at +1-555-019-2834. "
        "Send your test deposit to our wallet 0x71C63303741cAE444856075c0c457bf433270c35 "
        "or use CashApp handle $ApexYieldVIP."
    )

    indicators = extract_indicators(transcript)
    type_map = {item["indicator_type"]: item["value"] for item in indicators}

    assert "crypto_wallet" in type_map
    assert type_map["crypto_wallet"] == "0x71C63303741cAE444856075c0c457bf433270c35"

    assert "url" in type_map
    assert type_map["url"] == "https://apex-yield-trade.com/portal"

    assert "phone_number" in type_map
    assert "+1-555-019-2834" in type_map["phone_number"]

    assert "payment_handle" in type_map
    assert type_map["payment_handle"] == "$ApexYieldVIP"


def test_extract_multiple_crypto_formats():
    """Verifies extraction of ETH, BTC legacy, and BTC bech32 addresses."""
    text = (
        "ETH: 0x71C63303741cAE444856075c0c457bf433270c35 "
        "BTC1: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa "
        "BTC2: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
    )
    indicators = extract_indicators(text)
    wallets = [i["value"] for i in indicators if i["indicator_type"] == "crypto_wallet"]

    assert "0x71C63303741cAE444856075c0c457bf433270c35" in wallets
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in wallets
    assert "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq" in wallets


def test_no_false_positives_on_normal_sentences():
    """
    AC 3: A normal sentence with no real indicators produces an empty list
    (no false positives on plain text).
    """
    # Plain chat
    assert extract_indicators("Good morning dear, how are you doing today?") == []

    # Dollar currency amounts (should NOT match $cashtag)
    assert extract_indicators("I went to the store and spent $50 on groceries and $500 on rent.") == []

    # Dates, times, years (should NOT match phone numbers)
    assert extract_indicators("Meeting was set in 2026 at 3pm with 100 participants.") == []

    # Casual mention without real links
    assert extract_indicators("I will text you later this evening when I get home.") == []


def test_clean_url_strips_trailing_punctuation():
    """Verifies that trailing punctuation like '.', '!', ')' is stripped from URLs."""
    text = "Visit https://secure-login.org/auth. Did you see https://example.com/join?"
    indicators = extract_indicators(text)
    urls = [i["value"] for i in indicators if i["indicator_type"] == "url"]

    assert "https://secure-login.org/auth" in urls
    assert "https://example.com/join" in urls


def test_persistence_deduplication(db_session, sample_conversation):
    """
    AC 2: Running extraction twice on the same growing transcript does not create
    duplicate threat_indicators rows for the same value within the same conversation.
    """
    conv_id = sample_conversation.id

    # Turn 1: scammer provides URL and wallet
    text_turn_1 = "Visit https://apex-trade.io and send to 0x71C63303741cAE444856075c0c457bf433270c35."
    new_1 = extract_and_persist_indicators(db_session, conv_id, text_turn_1)
    assert len(new_1) == 2

    # Verify rows in DB
    records_1 = db_session.query(ThreatIndicator).filter(ThreatIndicator.conversation_id == conv_id).all()
    assert len(records_1) == 2
    assert all(r.status == "pending" for r in records_1)

    # Turn 2: same text repeated or growing conversation containing same indicators
    new_2 = extract_and_persist_indicators(db_session, conv_id, text_turn_1)
    # Should insert 0 new rows
    assert len(new_2) == 0

    records_2 = db_session.query(ThreatIndicator).filter(ThreatIndicator.conversation_id == conv_id).all()
    assert len(records_2) == 2

    # Turn 3: Growing conversation introduces a NEW phone number + previously seen URL
    text_turn_3 = "Like I said on https://apex-trade.io, call me at +1-555-444-9999!"
    new_3 = extract_and_persist_indicators(db_session, conv_id, text_turn_3)
    # Only 1 new row (the phone number)
    assert len(new_3) == 1
    assert new_3[0].indicator_type == "phone_number"
    assert "+1-555-444-9999" in new_3[0].value

    # Total in DB is now 3
    records_3 = db_session.query(ThreatIndicator).filter(ThreatIndicator.conversation_id == conv_id).all()
    assert len(records_3) == 3
