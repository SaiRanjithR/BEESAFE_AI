#!/usr/bin/env python3
"""
reset_db.py - BeeSafe.AI Database Reset & Clean Seeder

Clears all automated test clutter from the database and seeds
one clean, realistic initial demo conversation.
"""

import sys
import uuid
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal
from app.db.models import Conversation, Message, ThreatIndicator, RiskAssessment, AuditLog, Persona


def reset_and_seed():
    db = SessionLocal()
    try:
        print("Cleaning up database records...")
        db.query(AuditLog).delete()
        db.query(ThreatIndicator).delete()
        db.query(RiskAssessment).delete()
        db.query(Message).delete()
        db.query(Conversation).delete()
        db.commit()

        # Ensure default Persona exists
        persona = db.query(Persona).first()
        if not persona:
            persona = Persona(
                id=uuid.uuid4(),
                name="Margaret Chen",
                backstory_json={
                    "age": 72,
                    "occupation": "Retired elementary teacher",
                    "location": "Suburban Ohio",
                    "hobbies": ["gardening", "baking cookies", "reading mystery novels"],
                    "financial_posture": "Modest fixed pension and retirement savings, cautious with technology, polite and trusting",
                    "delay_strategy": "Acts slightly confused, asks polite clarifying questions, delays compliance",
                },
            )
            db.add(persona)
            db.commit()
            db.refresh(persona)

        # Create 1 clean initial demo conversation
        conv = Conversation(
            id=uuid.uuid4(),
            channel="simulated",
            scammer_contact="scammer_demo_01",
            persona_id=persona.id,
            status="active",
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        # Message 1: Scammer opening hook
        msg1 = Message(
            conversation_id=conv.id,
            role="scammer",
            text="Hey Sarah, are we still meeting for lunch today at that Italian place downtown?",
            flagged_action=None,
            review_status="not_needed",
        )
        db.add(msg1)

        # Message 2: Persona polite confusion
        msg2 = Message(
            conversation_id=conv.id,
            role="persona",
            text="Oh dear, I think you have the wrong number! This is Margaret. But I do hope you and Sarah have a lovely lunch!",
            flagged_action=None,
            review_status="not_needed",
        )
        db.add(msg2)

        # Initial Risk Assessment: Low risk
        risk = RiskAssessment(
            conversation_id=conv.id,
            risk_score=15,
            classification="benign_smalltalk",
            reasons=["Opening wrong-number message with no financial or credential solicitation."],
            explanation="This conversation appears to be an initial wrong-number approach with low risk so far.",
        )
        db.add(risk)
        db.commit()

        print("Database reset complete!")
        print(f"Active Conversations: {db.query(Conversation).count()}")
        print(f"Active Messages:      {db.query(Message).count()}")
        print(f"Threat Indicators:    {db.query(ThreatIndicator).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    reset_and_seed()
