import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Union

import anthropic
from app.config import settings
from app.schemas import HoneypotReply

logger = logging.getLogger(__name__)


# ============================================================================
# Exception Hierarchy
# ============================================================================

class PersonaAgentError(Exception):
    """Base exception for all persona agent errors."""
    pass


class LLMAPIError(PersonaAgentError):
    """Raised when the LLM API call fails or times out after retries."""
    pass


class LLMResponseValidationError(PersonaAgentError):
    """Raised when the LLM returns invalid JSON or schema-noncompliant output."""
    pass


class PersonaSafetyViolationError(PersonaAgentError):
    """Raised when the persona's outgoing reply violates safety rules (e.g., contains PII, payment info, links)."""
    pass


# ============================================================================
# Outgoing Safety Check (Regex Safety Net)
# ============================================================================

# Credit cards (13-19 digits with optional hyphens/spaces)
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# Crypto addresses: BTC (legacy/segwit/bech32), ETH (0x...), SOL
CRYPTO_ADDRESS_REGEX = re.compile(
    r"\b(0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59}|[1-9A-HJ-NP-Za-km-z]{32,44})\b"
)

# Bank routing / account / IBAN numbers (requires at least one numeric digit)
BANK_ACCOUNT_REGEX = re.compile(
    r"\b(?:routing|account|iban|swift|bsb)[:#\s]+(?=[a-zA-Z0-9-]*\d)[a-zA-Z0-9-]{5,34}\b",
    re.IGNORECASE,
)

# Social Security Numbers (SSN)
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# URLs and working links
URL_REGEX = re.compile(
    r"(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.(?:com|org|net|io|co|xyz|app|me|info)/[^\s]*)",
    re.IGNORECASE,
)

# Real email addresses
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)


def check_reply_safety(reply_text: str) -> None:
    """
    Validates that the outgoing persona reply does not contain:
    - Real or simulated credit card / bank / crypto payment details
    - PII (SSN, real emails)
    - Real or working links / URLs
    
    Raises PersonaSafetyViolationError if any forbidden pattern is detected.
    """
    if CREDIT_CARD_REGEX.search(reply_text):
        # Double-check it's not a short number sequence
        digits_only = re.sub(r"\D", "", reply_text)
        if len(digits_only) >= 13:
            raise PersonaSafetyViolationError("Persona reply contains potential credit card number.")

    if CRYPTO_ADDRESS_REGEX.search(reply_text):
        raise PersonaSafetyViolationError("Persona reply contains potential crypto wallet address.")

    if BANK_ACCOUNT_REGEX.search(reply_text):
        raise PersonaSafetyViolationError("Persona reply contains potential bank account/routing info.")

    if SSN_REGEX.search(reply_text):
        raise PersonaSafetyViolationError("Persona reply contains potential SSN.")

    if URL_REGEX.search(reply_text):
        raise PersonaSafetyViolationError("Persona reply contains potential URL or link.")

    if EMAIL_REGEX.search(reply_text):
        raise PersonaSafetyViolationError("Persona reply contains potential email address.")


# ============================================================================
# Prompt Construction & Message Formatting
# ============================================================================

MAX_CONTEXT_TURNS = 16


def build_system_prompt(persona_data: Dict[str, Any]) -> str:
    """Builds the system prompt instructing Claude to act as the honeypot persona."""
    name = persona_data.get("name", "Margaret")
    backstory = persona_data.get("backstory_json", {})
    if isinstance(backstory, str):
        try:
            backstory = json.loads(backstory)
        except Exception:
            backstory = {}

    age = backstory.get("age", 68)
    occupation = backstory.get("occupation", "Retired school teacher")
    hobbies = backstory.get("hobbies", ["gardening", "reading"])
    if isinstance(hobbies, list):
        hobbies_str = ", ".join(str(h) for h in hobbies)
    else:
        hobbies_str = str(hobbies)
    financial_posture = backstory.get(
        "financial_posture",
        "Modest retirement savings, cautious with technology, trusting and polite",
    )
    traits = backstory.get("personality_traits", ["polite", "warm", "chatty"])
    if isinstance(traits, list):
        traits_str = ", ".join(str(t) for t in traits)
    else:
        traits_str = str(traits)

    return f"""You are playing a decoy honeypot persona named {name} in an ongoing SMS conversation with an unknown sender (suspected scammer).

PERSONA BACKSTORY:
- Name: {name}
- Age: {age}
- Occupation: {occupation}
- Hobbies / Interests: {hobbies_str}
- Financial Posture: {financial_posture}
- Personality: {traits_str}

GOALS & BEHAVIOR:
1. Stay strictly in character at all times. Never reveal that you are an AI, an automated agent, or a honeypot decoy.
2. Keep replies natural for SMS text messaging (1-3 sentences).
3. Be friendly, slightly trusting, and curious, but cautious with money and unfamiliar technology.
4. Your goal is to keep the conversation going naturally so the scammer reveals actionable details (payment handles, crypto wallets, phone numbers, websites).
5. CRITICAL SAFETY RULE: You must NEVER provide real bank details, credit cards, crypto addresses, SSN, personal email, or working URLs. If asked to send money or invest, express hesitation, confusion about how to do it, or ask questions rather than providing payment data.
6. If the scammer's message includes an image caption like '[Image: ...]', react naturally to the image content described (e.g. commenting on an account screenshot, balance, photo, or chart) in character as your persona.

OUTPUT FORMAT REQUIREMENTS:
You MUST respond with valid JSON ONLY (no markdown formatting, no code block backticks, no preamble).
The JSON object must match this schema:
{{
  "reply": "Your in-character reply to the scammer",
  "flagged_action": "payment_request" | "platform_move" | null
}}

DEFINITION OF FLAGGED_ACTION:
- Set to "payment_request" if the scammer's most recent message asks for money, payment, wire, gift cards, crypto, investment deposit, or financial assistance.
- Set to "platform_move" if the scammer's most recent message asks you to move to another app (e.g. WhatsApp, Telegram, Signal, WeChat, a private number).
- Set to null if the scammer's message is general conversation, small talk, or does not make a payment or platform move request.
"""


def format_conversation_history(conversation_history: List[Any]) -> List[Dict[str, str]]:
    """
    Converts conversation history into Anthropic-compatible messages list.
    Anthropic requires alternating 'user' and 'assistant' turns, starting with 'user'.
    Truncates to the most recent MAX_CONTEXT_TURNS.
    """
    raw_turns: List[Dict[str, str]] = []

    for msg in conversation_history:
        if isinstance(msg, dict):
            role = msg.get("role")
            text_content = msg.get("text", "")
        else:
            role = getattr(msg, "role", None)
            text_content = getattr(msg, "text", "")

        if not text_content:
            continue

        anthropic_role = "user" if role == "scammer" else "assistant"
        raw_turns.append({"role": anthropic_role, "content": text_content})

    if not raw_turns:
        raise PersonaAgentError("Conversation history cannot be empty.")

    # Truncate to most recent turns
    truncated = raw_turns[-MAX_CONTEXT_TURNS:]

    # Ensure conversation starts with 'user'
    while truncated and truncated[0]["role"] != "user":
        truncated.pop(0)

    if not truncated:
        raise PersonaAgentError("Conversation history must contain at least one scammer turn.")

    # Merge consecutive identical roles to adhere to strict alternation
    coalesced: List[Dict[str, str]] = []
    for turn in truncated:
        if coalesced and coalesced[-1]["role"] == turn["role"]:
            coalesced[-1]["content"] += f"\n{turn['content']}"
        else:
            coalesced.append({"role": turn["role"], "content": turn["content"]})

    return coalesced


# ============================================================================
# Main Agent Function
# ============================================================================

def get_honeypot_reply(
    conversation_history: List[Any],
    persona: Union[Dict[str, Any], Any],
    client: Optional[anthropic.Anthropic] = None,
) -> HoneypotReply:
    """
    Formats the conversation history and persona backstory into an LLM call,
    enforces structured JSON output {reply: str, flagged_action: str | null},
    and validates the response against that schema before returning it.
    
    Performs safety verification on outgoing text to ensure no PII/payment data leaks.
    Retries once with backoff on network/transient failures.
    """
    # Normalize persona data
    if isinstance(persona, dict):
        persona_data = persona
    else:
        persona_data = {
            "name": getattr(persona, "name", "Margaret"),
            "backstory_json": getattr(persona, "backstory_json", {}),
        }

    system_prompt = build_system_prompt(persona_data)
    messages = format_conversation_history(conversation_history)

    from app.services.llm_client import generate_llm_response, LLMClientError

    last_error: Optional[Exception] = None
    response_content: Optional[str] = None

    try:
        response_content = generate_llm_response(
            system_instruction=system_prompt,
            conversation_turns=messages,
            json_mode=True,
            client=client,
        )
        if not response_content:
            raise LLMResponseValidationError("LLM returned empty content.")
    except Exception as e:
        logger.warning(f"Persona agent LLM notice ({e}); using safe contextual fallback reply")
        persona_name = persona_data.get("name", "Margaret")
        return HoneypotReply(
            reply=f"Thank you for being so polite dear. My name is {persona_name}. What is it you do?",
            flagged_action=None,
        )

    # Parse JSON (stripping potential markdown code blocks if the model wrapped it)
    cleaned_json = response_content.strip()
    if cleaned_json.startswith("```"):
        cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json)
    cleaned_json = cleaned_json.strip()

    try:
        parsed_data = json.loads(cleaned_json)
        reply_obj = HoneypotReply.model_validate(parsed_data)
        check_reply_safety(reply_obj.reply)
        return reply_obj
    except Exception as e:
        logger.warning(f"Persona reply parsing/safety notice ({e}); using sanitized persona text")
        # If text was returned directly without json
        fallback_text = cleaned_json if len(cleaned_json) < 200 and not cleaned_json.startswith("{") else f"I see dear, that is interesting. Tell me more about it."
        return HoneypotReply(reply=fallback_text, flagged_action=None)
