from unittest.mock import MagicMock
import pytest
import anthropic

from app.schemas import HoneypotReply
from app.services.persona_agent import (
    get_honeypot_reply,
    check_reply_safety,
    format_conversation_history,
    LLMAPIError,
    LLMResponseValidationError,
    PersonaSafetyViolationError,
)

SAMPLE_PERSONA = {
    "name": "Margaret",
    "backstory_json": {
        "age": 68,
        "occupation": "Retired middle school teacher",
        "hobbies": ["gardening", "knitting", "baking cookies"],
        "financial_posture": "Modest fixed pension, unfamiliar with crypto",
        "personality_traits": ["warm", "chatty", "cautious"],
    },
}


def create_mock_client(response_text: str):
    """Helper to build a mock Anthropic client returning given text block."""
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.text = response_text
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def test_payment_request_flagged():
    """AC 1: Given a sample conversation ending in a payment request, returns flagged_action: 'payment_request'."""
    conversation = [
        {"role": "scammer", "text": "Hello, is this Margaret?"},
        {"role": "persona", "text": "Yes it is, dear. Who is this?"},
        {
            "role": "scammer",
            "text": "Can you wire $500 right now to my crypto wallet or CashApp? It's urgent!",
        },
    ]

    llm_payload = '{"reply": "Oh goodness, $500 is a lot of money! What is a CashApp?", "flagged_action": "payment_request"}'
    client = create_mock_client(llm_payload)

    result = get_honeypot_reply(conversation, SAMPLE_PERSONA, client=client)

    assert isinstance(result, HoneypotReply)
    assert result.flagged_action == "payment_request"
    assert "Oh goodness" in result.reply


def test_benign_small_talk_null_flag():
    """AC 2: Given a benign small-talk exchange, returns flagged_action: null."""
    conversation = [
        {"role": "scammer", "text": "Good morning! Nice weather today, isn't it?"},
        {"role": "persona", "text": "It certainly is! The hydrangeas in my garden are blooming."},
        {"role": "scammer", "text": "I love flowers too. Do you have roses as well?"},
    ]

    llm_payload = '{"reply": "Yes, two rose bushes my late husband planted!", "flagged_action": null}'
    client = create_mock_client(llm_payload)

    result = get_honeypot_reply(conversation, SAMPLE_PERSONA, client=client)

    assert isinstance(result, HoneypotReply)
    assert result.flagged_action is None
    assert "rose bushes" in result.reply


def test_platform_move_flagged():
    """Verifies platform_move is properly recognized and schema-compliant."""
    conversation = [
        {"role": "scammer", "text": "Hey Margaret, text me on WhatsApp at +1234567890 instead, this app is slow."},
    ]

    llm_payload = '{"reply": "What is a WhatsApp? I only know how to send regular text messages on my phone.", "flagged_action": "platform_move"}'
    client = create_mock_client(llm_payload)

    result = get_honeypot_reply(conversation, SAMPLE_PERSONA, client=client)

    assert result.flagged_action == "platform_move"


def test_invalid_json_raises_validation_error():
    """AC 3a: If the LLM returns invalid JSON, raises LLMResponseValidationError."""
    conversation = [{"role": "scammer", "text": "Hello"}]
    client = create_mock_client("This is plain text and definitely not valid JSON!")

    with pytest.raises(LLMResponseValidationError):
        get_honeypot_reply(conversation, SAMPLE_PERSONA, client=client)


def test_schema_mismatch_raises_validation_error():
    """AC 3b: If the LLM returns JSON missing required fields, raises LLMResponseValidationError."""
    conversation = [{"role": "scammer", "text": "Hello"}]
    # Missing 'reply' field
    client = create_mock_client('{"flagged_action": "payment_request"}')

    with pytest.raises(LLMResponseValidationError):
        get_honeypot_reply(conversation, SAMPLE_PERSONA, client=client)


def test_api_failure_raises_llm_api_error():
    """AC 3c: If the LLM API call fails, raises LLMAPIError."""
    conversation = [{"role": "scammer", "text": "Hello"}]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=MagicMock())

    with pytest.raises(LLMAPIError):
        get_honeypot_reply(conversation, SAMPLE_PERSONA, client=mock_client)


def test_safety_check_prevents_pii_and_payment_leak():
    """AC 4: The persona never includes real payment details, PII, or links in its reply."""
    # Test Credit Card pattern
    with pytest.raises(PersonaSafetyViolationError):
        check_reply_safety("Sure, here is my Visa: 4532 1234 5678 9012")

    # Test Crypto Wallet pattern
    with pytest.raises(PersonaSafetyViolationError):
        check_reply_safety("Send it to 0x71C63303741cAE444856075c0c457bf433270c35 right now")

    with pytest.raises(PersonaSafetyViolationError):
        check_reply_safety("My bitcoin wallet is 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

    # Test Bank details pattern
    with pytest.raises(PersonaSafetyViolationError):
        check_reply_safety("My routing number is 123456789 and account: 987654321")

    # Test SSN pattern
    with pytest.raises(PersonaSafetyViolationError):
        check_reply_safety("My SSN is 123-45-6789")

    # Test URL pattern
    with pytest.raises(PersonaSafetyViolationError):
        check_reply_safety("Check out this site: https://fake-crypto-exchange.com/login")

    # Test Email pattern
    with pytest.raises(PersonaSafetyViolationError):
        check_reply_safety("You can email me at margaret.personal@gmail.com")

    # Clean in-character reply passes without error
    check_reply_safety("Oh my dear, I have no idea how those fancy computer currencies work.")


def test_safety_check_blocks_unsafe_llm_output():
    """Verifies that even if the LLM produces an unsafe string, get_honeypot_reply catches it."""
    conversation = [{"role": "scammer", "text": "Where should I send the check?"}]
    unsafe_payload = '{"reply": "Here is my bank account: 123456789", "flagged_action": null}'
    client = create_mock_client(unsafe_payload)

    with pytest.raises(PersonaSafetyViolationError):
        get_honeypot_reply(conversation, SAMPLE_PERSONA, client=client)


def test_markdown_wrapped_json_parsing():
    """Verifies that LLM markdown code blocks (```json ... ```) are cleanly parsed."""
    conversation = [{"role": "scammer", "text": "Hello"}]
    payload = """```json
    {
      "reply": "Hello dear, how can I help you?",
      "flagged_action": null
    }
    ```"""
    client = create_mock_client(payload)

    result = get_honeypot_reply(conversation, SAMPLE_PERSONA, client=client)
    assert result.reply == "Hello dear, how can I help you?"
    assert result.flagged_action is None


def test_format_conversation_history_alternation():
    """Verifies consecutive turns are merged and history starts with user turn."""
    raw = [
        {"role": "persona", "text": "Initial greeting"},
        {"role": "scammer", "text": "Turn 1"},
        {"role": "scammer", "text": "Turn 2"},
        {"role": "persona", "text": "Turn 3"},
    ]
    formatted = format_conversation_history(raw)
    assert len(formatted) == 2
    assert formatted[0]["role"] == "user"
    assert "Turn 1\nTurn 2" in formatted[0]["content"]
    assert formatted[1]["role"] == "assistant"
    assert formatted[1]["content"] == "Turn 3"
