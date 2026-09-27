import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.sql import text as sa_text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    name = Column(Text, nullable=False)
    backstory_json = Column(JSONB, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    conversations = relationship("Conversation", back_populates="persona")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    channel = Column(Text, nullable=False)  # 'sms' or 'simulated'
    scammer_contact = Column(Text, nullable=False)
    persona_id = Column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(
        Text,
        nullable=False,
        default="active",
        server_default=sa_text("'active'"),
    )  # 'active', 'halted', 'completed'
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    persona = relationship("Persona", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.created_at",
        cascade="all, delete-orphan",
    )
    threat_indicators = relationship(
        "ThreatIndicator",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    risk_assessment = relationship(
        "RiskAssessment",
        back_populates="conversation",
        uselist=False,
        cascade="all, delete-orphan",
    )
    audit_logs = relationship("AuditLog", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(Text, nullable=False)  # 'scammer' or 'persona'
    text = Column(Text, nullable=False)
    flagged_action = Column(Text, nullable=True)  # 'payment_request', 'platform_move', or null
    review_status = Column(
        Text,
        nullable=False,
        default="not_needed",
        server_default=sa_text("'not_needed'"),
    )  # 'not_needed', 'pending', 'approved', 'edited', 'halted'
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    conversation = relationship("Conversation", back_populates="messages")


class ThreatIndicator(Base):
    __tablename__ = "threat_indicators"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    indicator_type = Column(Text, nullable=False)  # 'crypto_wallet', 'phone_number', 'url', 'payment_handle'
    value = Column(Text, nullable=False)
    status = Column(
        Text,
        nullable=False,
        default="pending",
        server_default=sa_text("'pending'"),
    )  # 'pending', 'blocked'
    known_bad = Column(Boolean, nullable=True)  # Populated via n8n / blocklist enrichment
    domain_age_days = Column(Integer, nullable=True)  # Populated via n8n / RDAP enrichment
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    conversation = relationship("Conversation", back_populates="threat_indicators")


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    risk_score = Column(Integer, nullable=False)  # 0–100
    classification = Column(Text, nullable=False)  # e.g. 'pig_butchering_suspected'
    reasons = Column(JSONB, nullable=False)  # array of strings
    explanation = Column(Text, nullable=True)  # Warm narrative paragraph generated by explanation agent
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    conversation = relationship("Conversation", back_populates="risk_assessment")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sa_text("gen_random_uuid()"),
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor = Column(Text, nullable=False)
    action = Column(Text, nullable=False)  # e.g. 'approved_reply', 'blocked_indicator', 'halted_conversation'
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    conversation = relationship("Conversation", back_populates="audit_logs")
