import logging
import re
import time
from typing import Any, Dict, List, Optional, Union

import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# Constant Seeded Fake Threat Indicators (for repeatable demo & correlation)
# ============================================================================

SEEDED_FAKE_WALLET = "0x71C63303741cAE444856075c0c457bf433270c35"
SEEDED_FAKE_PAYMENT_HANDLE = "$ApexYieldVIP"
SEEDED_FAKE_URL = "https://apex-yield-trade.com/portal"
SEEDED_FAKE_PHONE = "+1-555-019-2834"


# ============================================================================
# Exception Hierarchy
# ============================================================================

class ScammerBotError(Exception):
    """Base exception for scammer bot errors."""
    pass


class ScammerAPIError(ScammerBotError):
    """Raised when the LLM API call fails or times out."""
    pass


# ============================================================================
# Prompt Construction
# ============================================================================

def build_scammer_system_prompt(turn_number: int) -> str:
    """
    Builds the system prompt instructing the LLM to play a realistic pig-butchering scammer,
    following a phased arc based on the turn number.
    """
    if turn_number <= 3:
        stage_instructions = f"""STAGE 1: SMALL TALK & RAPPORT BUILDING (Turn {turn_number} of 10)
- You initiated contact via a 'wrong number' text (e.g. asking for someone else) or casual greeting.
- Be polite, charming, apologetic about the mistake, and try to strike up a friendly chat.
- Ask light questions about what they do or how their day is going.
- DO NOT mention investments, crypto, or money yet."""
    elif turn_number <= 6:
        stage_instructions = f"""STAGE 2: INVESTMENT BAIT & HOOK (Turn {turn_number} of 10)
- Casually introduce that you are doing well financially through a private investment/crypto trading platform.
- Mention your 'uncle' or 'financial analyst' who gives you insider trading signals with guaranteed returns.
- Seed this exact platform URL into the conversation: {SEEDED_FAKE_URL}
- Show screenshots/returns enthusiasm, encourage them that anyone can do it with a small test."""
    else:
        stage_instructions = f"""STAGE 3: DIRECT PAYMENT & WALLET EXTRACTION (Turn {turn_number} of 10)
- Urgently press the victim to make a test deposit to get in on the current lucrative market signal.
- Provide this exact fake crypto wallet address: {SEEDED_FAKE_WALLET}
- Or provide this exact payment handle: {SEEDED_FAKE_PAYMENT_HANDLE}
- Reassure them it's completely safe and you will walk them through it step-by-step."""

    return f"""You are playing the role of a calculated pig-butchering scammer in a simulated SMS honeypot conversation.

CURRENT CONVERSATION OBJECTIVE:
{stage_instructions}

RULES:
1. Stay strictly in character. Never break the fourth wall, never admit this is a simulation, test, or scam.
2. Reply in realistic, conversational SMS text message format (1 to 3 sentences maximum).
3. Do not include quotes, markdown headers, or role prefixes like 'Scammer:' in your reply.
4. If the other person asks questions or expresses hesitation, respond persuasively and address their remarks while maintaining your objective for this turn.
"""


def format_scammer_history(conversation_history: List[Any]) -> List[Dict[str, str]]:
    """
    Formats the conversation history for the scammer LLM.
    From the scammer bot's perspective:
    - Persona turns are 'user' (the other party speaking)
    - Scammer turns are 'assistant' (what the scammer bot previously said)
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

        # Invert roles for the scammer bot's perspective
        anthropic_role = "assistant" if role == "scammer" else "user"
        raw_turns.append({"role": anthropic_role, "content": text_content})

    if not raw_turns:
        # Initial turn where scammer initiates the conversation
        return [{"role": "user", "content": "Start the conversation with an accidental wrong-number SMS."}]

    # Anthropic Messages API requires messages to start with 'user'.
    # If the scammer (assistant) spoke first, prepend an initial user prompt so context is preserved.
    if raw_turns and raw_turns[0]["role"] == "assistant":
        raw_turns.insert(0, {"role": "user", "content": "Please initiate or continue the simulated conversation."})

    # Coalesce consecutive turns of same role
    coalesced: List[Dict[str, str]] = []
    for turn in raw_turns:
        if coalesced and coalesced[-1]["role"] == turn["role"]:
            coalesced[-1]["content"] += f"\n{turn['content']}"
        else:
            coalesced.append({"role": turn["role"], "content": turn["content"]})

    return coalesced


# ============================================================================
# Main Service Function
# ============================================================================

def get_simulated_scammer_reply(
    conversation_history: List[Any],
    turn_number: Optional[int] = None,
    client: Optional[anthropic.Anthropic] = None,
) -> str:
    """
    Generates a simulated scammer reply following a pig-butchering arc.
    Turns 1-3: Small talk / wrong number rapport
    Turns 4-6: Introduce investment bait + platform URL
    Turns 7+: Request payment to SEEDED_FAKE_WALLET / SEEDED_FAKE_PAYMENT_HANDLE
    """
    if turn_number is None:
        # Calculate turn count from scammer messages in history + 1
        scammer_count = sum(
            1 for m in conversation_history
            if (m.get("role") if isinstance(m, dict) else getattr(m, "role", None)) == "scammer"
        )
        turn_number = scammer_count + 1

    system_prompt = build_scammer_system_prompt(turn_number)
    messages = format_scammer_history(conversation_history)

    from app.services.llm_client import generate_llm_response

    last_error: Optional[Exception] = None
    reply_text: Optional[str] = None

    for attempt in range(2):
        try:
            reply_text = generate_llm_response(
                system_instruction=system_prompt,
                conversation_turns=messages,
                client=client,
            )
            if not reply_text:
                raise ScammerAPIError("LLM returned empty content.")
            break
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.RateLimitError) as e:
            last_error = e
            logger.warning(f"Scammer bot API transient error on attempt {attempt + 1}: {e}")
            if attempt == 0:
                time.sleep(1.0)
        except anthropic.APIError as e:
            raise ScammerAPIError(f"LLM API error: {e}") from e
        except ScammerAPIError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"Scammer bot attempt {attempt + 1} failed: {e}")
            if attempt == 0:
                time.sleep(1.0)
            else:
                raise ScammerAPIError(f"Unexpected error communicating with LLM: {e}") from e

    if reply_text is None:
        raise ScammerAPIError(f"Scammer bot API call failed after retries: {last_error}") from last_error

    # Clean text (remove any accidental role prefixes like 'Scammer:' or quotation marks)
    cleaned = reply_text.strip()
    cleaned = re.sub(r"^(?:scammer|bot|simulated):\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip('"\'')

    return cleaned
