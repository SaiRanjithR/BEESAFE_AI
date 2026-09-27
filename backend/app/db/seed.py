import uuid
from app.db.database import SessionLocal
from app.db.models import Persona, Conversation


def seed_database():
    db = SessionLocal()
    try:
        # Check if persona already exists
        persona = db.query(Persona).first()
        if not persona:
            persona = Persona(
                id=uuid.uuid4(),
                name="Margaret",
                backstory_json={
                    "age": 68,
                    "occupation": "Retired middle school teacher",
                    "location": "Suburban Ohio",
                    "hobbies": ["gardening", "knitting", "baking cookies", "reading mystery novels"],
                    "financial_posture": "Modest fixed pension and retirement savings, unfamiliar with crypto or complex banking apps, trusting and polite",
                    "personality_traits": ["warm", "a bit lonely", "chatty", "cautious but eager to make friends"],
                },
            )
            db.add(persona)
            db.commit()
            db.refresh(persona)
            print(f"Created persona: {persona.name} ({persona.id})")
        else:
            print(f"Existing persona found: {persona.name} ({persona.id})")

        # Check if a seed conversation exists
        conversation = db.query(Conversation).filter(Conversation.persona_id == persona.id).first()
        if not conversation:
            conversation = Conversation(
                id=uuid.uuid4(),
                channel="simulated",
                scammer_contact="simulated_scammer_001",
                persona_id=persona.id,
                status="active",
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            print(f"Created conversation: {conversation.id} for persona {persona.name}")
        else:
            print(f"Existing conversation found: {conversation.id}")

        return persona, conversation
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
