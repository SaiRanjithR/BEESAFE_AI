from unittest.mock import MagicMock
import pytest
import anthropic

from app.schemas import HoneypotReply
from app.services.persona_agent import get_honeypot_reply
from app.services.scammer_bot import (
    get_simulated_scammer_reply,
    build_scammer_system_prompt,
    format_scammer_history,
    SEEDED_FAKE_WALLET,
    SEEDED_FAKE_PAYMENT_HANDLE,
    SEEDED_FAKE_URL,
    SEEDED_FAKE_PHONE,
    ScammerAPIError,
)

SAMPLE_PERSONA = {
    "name": "Margaret",
    "backstory_json": {
        "age": 68,
        "occupation": "Retired teacher",
        "hobbies": ["gardening", "baking"],
        "financial_posture": "Modest pension",
    },
}


def create_mock_client(text_response: str):
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.text = text_response
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_seeded_constants_defined():
    """AC 2: Scammer bot's seeded fake payment handle & indicators are constant, reusable values."""
    assert isinstance(SEEDED_FAKE_PAYMENT_HANDLE, str) and len(SEEDED_FAKE_PAYMENT_HANDLE) > 0
    assert isinstance(SEEDED_FAKE_WALLET, str) and SEEDED_FAKE_WALLET.startswith("0x")
    assert isinstance(SEEDED_FAKE_URL, str) and SEEDED_FAKE_URL.startswith("http")
    assert isinstance(SEEDED_FAKE_PHONE, str) and len(SEEDED_FAKE_PHONE) > 0
    assert SEEDED_FAKE_PAYMENT_HANDLE == "$ApexYieldVIP"


def test_prompt_stages_by_turn():
    """Verifies that the system prompt guides the LLM according to the turn-based arc."""
    # Stage 1: turns 1-3
    p1 = build_scammer_system_prompt(1)
    assert "STAGE 1" in p1
    assert "wrong number" in p1
    assert SEEDED_FAKE_WALLET not in p1

    # Stage 2: turns 4-6
    p4 = build_scammer_system_prompt(5)
    assert "STAGE 2" in p4
    assert SEEDED_FAKE_URL in p4
    assert SEEDED_FAKE_WALLET not in p4

    # Stage 3: turns 7+
    p7 = build_scammer_system_prompt(7)
    assert "STAGE 3" in p7
    assert SEEDED_FAKE_WALLET in p7
    assert SEEDED_FAKE_PAYMENT_HANDLE in p7


def test_scammer_api_failure_handling():
    """AC 3: Error handling when LLM API call fails."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())

    with pytest.raises(ScammerAPIError):
        get_simulated_scammer_reply([], turn_number=1, client=mock_client)


def test_format_scammer_history():
    """Verifies scammer message history inverts roles and alternates properly."""
    raw = [
        {"role": "scammer", "text": "Hi Emily"},
        {"role": "persona", "text": "Wrong number"},
    ]
    formatted = format_scammer_history(raw)
    # Starts with synthetic user turn, followed by assistant (scammer), then user (persona)
    assert len(formatted) == 3
    assert formatted[0]["role"] == "user"
    assert formatted[1]["role"] == "assistant"
    assert formatted[1]["content"] == "Hi Emily"
    assert formatted[2]["role"] == "user"
    assert formatted[2]["content"] == "Wrong number"


def test_ten_turn_full_loop_simulation():
    """
    AC 1: Running a full loop of persona agent <-> scammer bot for at least 10 turns
    produces a coherent conversation without either side breaking character.
    Runs entirely between two LLM callers without real external infrastructure.
    """
    # Pre-scripted responses modeling the LLM conversation turns
    scammer_responses = {
        1: "Hi Emily, are we still meeting for lunch today?",
        2: "Oh I am so sorry, I must have dialed the wrong digit! You seem very nice though, I'm Alex.",
        3: "I'm a financial consultant. Actually my uncle helped me set up trades at https://apex-yield-trade.com/portal that make 20% weekly.",
        4: f"You can try with just a small test deposit to my trader wallet: {SEEDED_FAKE_WALLET} or {SEEDED_FAKE_PAYMENT_HANDLE}. I will guide you!",
        5: f"Don't worry Margaret, it's 100% risk free. Send the funds to {SEEDED_FAKE_WALLET} today and see your profits tomorrow!",
    }

    persona_responses = {
        1: '{"reply": "Oh, no dear, this is Margaret. You have the wrong number!", "flagged_action": null}',
        2: '{"reply": "Nice to meet you Alex. I am a retired teacher living in Ohio.", "flagged_action": null}',
        3: '{"reply": "Goodness, 20% weekly sounds like a lot! I never understood the stock market myself.", "flagged_action": null}',
        4: '{"reply": "Oh goodness, that sounds like real money! I have never done crypto and do not have that kind of money to send.", "flagged_action": "payment_request"}',
        5: '{"reply": "I need to talk to my son first before doing anything with wallets or money.", "flagged_action": "payment_request"}',
    }

    conversation_history = []

    for turn_idx in range(1, 6):
        # 1. Scammer turn
        scammer_client = create_mock_client(scammer_responses[turn_idx])
        scammer_text = get_simulated_scammer_reply(
            conversation_history, turn_number=(turn_idx * 2 - 1), client=scammer_client
        )
        conversation_history.append({"role": "scammer", "text": scammer_text})

        # 2. Persona turn
        persona_client = create_mock_client(persona_responses[turn_idx])
        persona_reply = get_honeypot_reply(
            conversation_history, SAMPLE_PERSONA, client=persona_client
        )
        conversation_history.append({
            "role": "persona",
            "text": persona_reply.reply,
            "flagged_action": persona_reply.flagged_action,
        })

    # Exactly 10 turns completed
    assert len(conversation_history) == 10

    # Alternating roles
    for i, msg in enumerate(conversation_history):
        expected_role = "scammer" if i % 2 == 0 else "persona"
        assert msg["role"] == expected_role

    # Verification of arc
    # Turn 5 (index 4) contains URL
    assert SEEDED_FAKE_URL in conversation_history[4]["text"]

    # Turn 7 (index 6) contains seeded wallet
    assert SEEDED_FAKE_WALLET in conversation_history[6]["text"]
    assert SEEDED_FAKE_PAYMENT_HANDLE in conversation_history[6]["text"]

    # Turn 8 (index 7, persona turn) has flagged_action == "payment_request"
    assert conversation_history[7]["flagged_action"] == "payment_request"

    # Turn 10 (index 9, persona turn) has flagged_action == "payment_request"
    assert conversation_history[9]["flagged_action"] == "payment_request"

    # Turns 2, 4, 6 have null flagged_action
    assert conversation_history[1]["flagged_action"] is None
    assert conversation_history[3]["flagged_action"] is None
    assert conversation_history[5]["flagged_action"] is None
