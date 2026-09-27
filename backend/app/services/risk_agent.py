import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Union

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import RiskAssessment
from app.schemas import RiskAssessmentResult

logger = logging.getLogger(__name__)


# ============================================================================
# Exception Hierarchy
# ============================================================================

class RiskAgentError(Exception):
    """Base exception for risk agent errors."""
    pass


class RiskAPIError(RiskAgentError):
    """Raised when the LLM API call fails or times out."""
    pass


class RiskResponseValidationError(RiskAgentError):
    """Raised when the LLM returns invalid JSON or schema-noncompliant output."""
    pass


# ============================================================================
# Prompt Construction
# ============================================================================

RISK_SYSTEM_PROMPT = """You are an expert fraud and cyber intelligence risk assessment analyst for financial institutions.
Your task is to analyze the provided SMS/text conversation transcript and evaluate fraud risk.

SCAM TYPOLOGIES TO DETECT:
1. Pig Butchering / Sha Zhu Pan:
   - Wrong number opening or accidental contact building artificial rapport
   - Casual introduction of high-yield investment, trading tips, or mentors
   - Sharing unregulated investment portal links or unverified trading URLs
   - Urging victim to make initial deposits or transfers to private crypto wallets or payment handles
2. Advance Fee Fraud / Wire Fraud:
   - Demanding upfront fees, processing charges, or urgent transfers
3. Impersonation / Platform Move:
   - Moving off SMS to encrypted messaging (WhatsApp, Telegram) to evade carrier filters

RISK SCORING SCALE (0 to 100):
- 0 to 29 (Low Risk / Benign): Normal conversation, small talk, everyday inquiries with no scam signals.
  Classification: 'benign_conversation'
- 30 to 69 (Medium Risk / Suspicious): Unsolicited contact, sudden investment/crypto mentions, unverified claims, or requests to move apps.
  Classification: 'suspicious_unsolicited_contact' or 'investment_bait_detected'
- 70 to 100 (High Risk / Confirmed Scam Operation): Direct solicitations for funds, crypto wallet addresses, fake trading links, coercive pressure.
  Classification: 'pig_butchering_suspected' or 'wire_fraud_suspected'

OUTPUT FORMAT REQUIREMENTS:
You MUST respond with valid JSON ONLY (no markdown code blocks, no preamble).
Schema:
{
  "risk_score": <int between 0 and 100>,
  "classification": "<classification_string>",
  "reasons": [
    "<specific transcript-grounded reason 1>",
    "<specific transcript-grounded reason 2>",
    "<specific transcript-grounded reason 3>"
  ]
}

REASONS REQUIREMENTS:
- Every reason MUST be specifically grounded in the transcript (cite the actual statements, claims, URLs, or payment requests made by the scammer).
- Do not provide generic boilerplate. If risk is elevated, provide at least 3 concrete, distinct reasons.
"""


def format_transcript_for_analysis(transcript: Union[str, List[Any]]) -> str:
    """Formats transcript into a clean chronological text block."""
    if isinstance(transcript, str):
        return transcript.strip()

    lines = []
    for turn in transcript:
        if isinstance(turn, dict):
            role = turn.get("role", "unknown")
            text = turn.get("text", "")
        else:
            role = getattr(turn, "role", "unknown")
            text = getattr(turn, "text", "")
        speaker = "Scammer" if role == "scammer" else "Persona"
        lines.append(f"{speaker}: {text}")

    return "\n".join(lines).strip()


# ============================================================================
# Main Service Functions
# ============================================================================

def run_risk_agent(
    transcript: Union[str, List[Any]],
    client: Optional[anthropic.Anthropic] = None,
) -> RiskAssessmentResult:
    """
    Calls the LLM to assess fraud risk on the provided transcript.
    Returns validated RiskAssessmentResult containing risk_score, classification, and reasons.
    """
    formatted_transcript = format_transcript_for_analysis(transcript)
    if not formatted_transcript:
        raise RiskAgentError("Transcript cannot be empty for risk scoring.")

    from app.services.llm_client import generate_llm_response

    last_error: Optional[Exception] = None
    response_content: Optional[str] = None

    for attempt in range(2):
        try:
            response_content = generate_llm_response(
                system_instruction=RISK_SYSTEM_PROMPT,
                conversation_turns=[{"role": "user", "content": f"Transcript to analyze:\n\n{formatted_transcript}"}],
                json_mode=True,
                client=client,
            )
            if not response_content:
                raise RiskResponseValidationError("LLM returned empty content.")
            break
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.RateLimitError) as e:
            last_error = e
            logger.warning(f"Risk agent transient error on attempt {attempt + 1}: {e}")
            if attempt == 0:
                time.sleep(1.0)
        except anthropic.APIError as e:
            raise RiskAPIError(f"LLM API error: {e}") from e
        except RiskResponseValidationError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"Risk agent attempt {attempt + 1} failed: {e}")
            if attempt == 0:
                time.sleep(1.0)
            else:
                raise RiskAPIError(f"Unexpected error communicating with LLM: {e}") from e

    if response_content is None:
        raise RiskAPIError(f"Risk agent API call failed after retries: {last_error}") from last_error

    cleaned_json = response_content.strip()
    if cleaned_json.startswith("```"):
        cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
        cleaned_json = re.sub(r"\s*```$", "", cleaned_json)
    cleaned_json = cleaned_json.strip()

    try:
        parsed_data = json.loads(cleaned_json)
    except json.JSONDecodeError as e:
        raise RiskResponseValidationError(f"Invalid JSON returned by LLM: {cleaned_json}") from e

    if not isinstance(parsed_data, dict):
        raise RiskResponseValidationError(f"Expected JSON object, got: {type(parsed_data)}")

    try:
        result = RiskAssessmentResult.model_validate(parsed_data)
    except Exception as e:
        raise RiskResponseValidationError(f"Risk assessment failed schema validation: {e}") from e

    return result


def assess_and_upsert_risk(
    db: Session,
    conversation_id: uuid.UUID,
    transcript: Union[str, List[Any]],
    client: Optional[anthropic.Anthropic] = None,
    generate_explanation: bool = False,
) -> RiskAssessment:
    """
    Runs the risk agent on the transcript and upserts the result into the
    single risk_assessments row for this conversation.
    """
    assessment_data = run_risk_agent(transcript, client=client)

    existing = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.conversation_id == conversation_id)
        .first()
    )

    explanation = None
    if generate_explanation:
        try:
            explanation = explain_for_demo(assessment_data, client=client)
        except Exception as e:
            logger.warning(f"Could not generate explanation during risk upsert: {e}")

    if existing:
        existing.risk_score = assessment_data.risk_score
        existing.classification = assessment_data.classification
        existing.reasons = assessment_data.reasons
        if explanation:
            existing.explanation = explanation
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        logger.info(f"Updated risk assessment for conversation {conversation_id}: score={existing.risk_score}")
        return existing
    else:
        new_record = RiskAssessment(
            conversation_id=conversation_id,
            risk_score=assessment_data.risk_score,
            classification=assessment_data.classification,
            reasons=assessment_data.reasons,
            explanation=explanation,
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        logger.info(f"Created risk assessment for conversation {conversation_id}: score={new_record.risk_score}")
        return new_record


# ============================================================================
# Explanation Agent (TICKET-012)
# ============================================================================

EXPLANATION_SYSTEM_PROMPT = """You are an executive fraud intelligence briefing specialist.
Your task is to take a technical fraud risk assessment (score, classification, and technical reasons) and rewrite it into a single, cohesive, narrative paragraph suitable for executive stakeholders and demo presentation.

REQUIREMENTS:
1. Tone: Professional, warm, accessible, and natural — avoid dry, clinical bullet-point language.
2. Structure: Exactly ONE well-developed paragraph. Do NOT use bullet points, numbered lists, markdown headers, or quotes.
3. Strict Factuality: You MUST be strictly factually consistent with the provided reasons and classification. Do NOT invent new facts, actions, URLs, or claims not grounded in the technical reasons.
4. Output: Return ONLY the single narrative paragraph text, with no preamble or commentary.
"""


def explain_for_demo(
    risk_assessment: Union[RiskAssessment, RiskAssessmentResult, dict],
    client: Optional[anthropic.Anthropic] = None,
) -> str:
    """
    Calls the LLM to rewrite structured risk reasons into a warm, cohesive single-paragraph
    narrative explanation suitable for executive demos.
    Strictly factually grounded in the provided reasons without altering scores or classifications.
    """
    if isinstance(risk_assessment, dict):
        score = risk_assessment.get("risk_score", 0)
        classification = risk_assessment.get("classification", "unknown")
        reasons = risk_assessment.get("reasons", [])
    elif isinstance(risk_assessment, RiskAssessmentResult):
        score = risk_assessment.risk_score
        classification = risk_assessment.classification
        reasons = risk_assessment.reasons
    else:  # RiskAssessment ORM model
        score = getattr(risk_assessment, "risk_score", 0)
        classification = getattr(risk_assessment, "classification", "unknown")
        reasons = getattr(risk_assessment, "reasons", [])

    if not reasons:
        return "This conversation currently exhibits no elevated fraud risk indicators and reflects standard everyday communication."

    formatted_reasons = "\n".join(f"- {r}" for r in reasons)
    user_prompt = (
        f"Risk Score: {score}/100\n"
        f"Classification: {classification}\n"
        f"Technical Findings:\n{formatted_reasons}\n\n"
        "Please rewrite these findings into a single cohesive narrative paragraph for the demo screen."
    )

    from app.services.llm_client import generate_llm_response

    last_error: Optional[Exception] = None
    explanation_text: Optional[str] = None

    for attempt in range(2):
        try:
            explanation_text = generate_llm_response(
                system_instruction=EXPLANATION_SYSTEM_PROMPT,
                conversation_turns=[{"role": "user", "content": user_prompt}],
                client=client,
            )
            if not explanation_text:
                raise RiskResponseValidationError("LLM returned empty or invalid text response.")
            break
        except (anthropic.APIConnectionError, anthropic.APITimeoutError, anthropic.RateLimitError) as e:
            last_error = e
            logger.warning(f"Explanation agent transient error on attempt {attempt + 1}: {e}")
            if attempt == 0:
                time.sleep(1.0)
        except anthropic.APIError as e:
            raise RiskAPIError(f"LLM API error in explanation agent: {e}") from e
        except RiskResponseValidationError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"Explanation agent attempt {attempt + 1} failed: {e}")
            if attempt == 0:
                time.sleep(1.0)
            else:
                raise RiskAPIError(f"Unexpected error in explanation agent: {e}") from e

    if explanation_text is None:
        raise RiskAPIError(f"Explanation agent failed after retries: {last_error}") from last_error

    # Clean up quotes or markdown wrapper
    cleaned = explanation_text.strip(' "\'\n`')
    # Collapse multiple whitespace/linebreaks into a single coherent paragraph
    single_paragraph = " ".join(cleaned.split())

    return single_paragraph
