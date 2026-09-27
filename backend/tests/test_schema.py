import uuid
import pytest
from sqlalchemy import inspect
from app.db.database import SessionLocal, engine
from app.db.models import (
    Base,
    Persona,
    Conversation,
    Message,
    ThreatIndicator,
    RiskAssessment,
    AuditLog,
)


def test_all_six_tables_exist():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    expected_tables = {
        "personas",
        "conversations",
        "messages",
        "threat_indicators",
        "risk_assessments",
        "audit_logs",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"


def test_conversations_columns_and_fk():
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("conversations")}
    assert "id" in columns
    assert "channel" in columns
    assert "scammer_contact" in columns
    assert "persona_id" in columns
    assert "status" in columns
    assert "created_at" in columns

    fks = inspector.get_foreign_keys("conversations")
    fk_persona = next((fk for fk in fks if fk["referred_table"] == "personas"), None)
    assert fk_persona is not None
    assert fk_persona["referred_columns"] == ["id"]


def test_messages_columns_and_fk():
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("messages")}
    assert "id" in columns
    assert "conversation_id" in columns
    assert "role" in columns
    assert "text" in columns
    assert "flagged_action" in columns
    assert "review_status" in columns
    assert "created_at" in columns

    fks = inspector.get_foreign_keys("messages")
    fk_conv = next((fk for fk in fks if fk["referred_table"] == "conversations"), None)
    assert fk_conv is not None
    assert fk_conv["referred_columns"] == ["id"]


def test_threat_indicators_columns_and_fk():
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("threat_indicators")}
    assert "id" in columns
    assert "conversation_id" in columns
    assert "indicator_type" in columns
    assert "value" in columns
    assert "status" in columns
    assert "known_bad" in columns
    assert "domain_age_days" in columns
    assert "created_at" in columns

    fks = inspector.get_foreign_keys("threat_indicators")
    fk_conv = next((fk for fk in fks if fk["referred_table"] == "conversations"), None)
    assert fk_conv is not None
    assert fk_conv["referred_columns"] == ["id"]


def test_risk_assessments_columns_and_fk_unique():
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("risk_assessments")}
    assert "id" in columns
    assert "conversation_id" in columns
    assert "risk_score" in columns
    assert "classification" in columns
    assert "reasons" in columns
    assert "explanation" in columns
    assert "updated_at" in columns

    fks = inspector.get_foreign_keys("risk_assessments")
    fk_conv = next((fk for fk in fks if fk["referred_table"] == "conversations"), None)
    assert fk_conv is not None

    # Check unique constraint on conversation_id
    unique_constraints = inspector.get_unique_constraints("risk_assessments")
    conv_unique = any("conversation_id" in uc["column_names"] for uc in unique_constraints)
    assert conv_unique is True


def test_audit_logs_columns_and_fk():
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("audit_logs")}
    assert "id" in columns
    assert "conversation_id" in columns
    assert "actor" in columns
    assert "action" in columns
    assert "created_at" in columns

    fks = inspector.get_foreign_keys("audit_logs")
    fk_conv = next((fk for fk in fks if fk["referred_table"] == "conversations"), None)
    assert fk_conv is not None


def test_insert_and_relationships():
    db = SessionLocal()
    try:
        # Create a persona
        persona = Persona(
            name="Test Persona",
            backstory_json={"age": 55, "occupation": "Accountant"},
        )
        db.add(persona)
        db.commit()
        db.refresh(persona)

        # Create a conversation
        conv = Conversation(
            channel="simulated",
            scammer_contact="test_scammer_999",
            persona_id=persona.id,
            status="active",
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        # Create a message
        msg = Message(
            conversation_id=conv.id,
            role="scammer",
            text="Hello there, are you interested in crypto?",
            flagged_action=None,
            review_status="not_needed",
        )
        db.add(msg)

        # Create a threat indicator
        indicator = ThreatIndicator(
            conversation_id=conv.id,
            indicator_type="crypto_wallet",
            value="0x71C...test",
            status="pending",
        )
        db.add(indicator)

        # Create a risk assessment
        risk = RiskAssessment(
            conversation_id=conv.id,
            risk_score=85,
            classification="pig_butchering_suspected",
            reasons=["Unsolicited contact", "Crypto pitch"],
        )
        db.add(risk)

        # Create an audit log
        audit = AuditLog(
            conversation_id=conv.id,
            actor="analyst_1",
            action="viewed_conversation",
        )
        db.add(audit)

        db.commit()

        # Query and verify
        queried_conv = db.query(Conversation).filter(Conversation.id == conv.id).first()
        assert queried_conv is not None
        assert len(queried_conv.messages) == 1
        assert queried_conv.messages[0].text == "Hello there, are you interested in crypto?"
        assert len(queried_conv.threat_indicators) == 1
        assert queried_conv.threat_indicators[0].value == "0x71C...test"
        assert queried_conv.risk_assessment.risk_score == 85
        assert len(queried_conv.audit_logs) == 1
        assert queried_conv.persona.name == "Test Persona"

    finally:
        # Cleanup test records
        db.rollback()
        db.close()
