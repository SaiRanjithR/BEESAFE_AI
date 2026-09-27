import logging
import re
import uuid
from typing import Dict, List, Set, Tuple
from sqlalchemy.orm import Session

from app.db.models import ThreatIndicator

logger = logging.getLogger(__name__)

# ============================================================================
# Regex Patterns
# ============================================================================

# Crypto wallets:
# 1. Ethereum / EVM: 0x followed by 40 hex characters
# 2. Bitcoin legacy / P2SH: starts with 1 or 3, 26-35 base58 characters
# 3. Bitcoin bech32: starts with bc1, 42-62 alphanumeric characters
# 4. Solana: base58 string 32-44 chars with mixed alphanumeric
ETH_REGEX = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
BTC_LEGACY_REGEX = re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b")
BTC_BECH32_REGEX = re.compile(r"\bbc1[a-z0-9]{39,59}\b")

# URLs: http/https or www. domains
URL_REGEX = re.compile(
    r"\b(?:https?://|www\.)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s<>'\"{}|\\^`]*)?",
    re.IGNORECASE,
)

# Phone numbers: North American & international E.164 formats (at least 10 digits)
# Matches formats like: +1-555-019-2834, +15550192834, (555) 019-2834, 555-019-2834
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)

# Payment handles:
# 1. CashApp: $Cashtag (must start with letter, NOT digit to avoid currency amounts like $500)
CASHTAG_REGEX = re.compile(r"(?<!\w)\$[a-zA-Z][a-zA-Z0-9_]{1,19}\b")

# 2. Venmo / social handles: @handle (not part of an email address)
HANDLE_REGEX = re.compile(r"(?<![a-zA-Z0-9._%+-])@[a-zA-Z0-9_]{3,30}\b")


def clean_url(raw_url: str) -> str:
    """Strips trailing punctuation frequently caught at the end of sentences."""
    return raw_url.rstrip(".,;:!?)'\"")


def extract_indicators(transcript_text: str) -> List[Dict[str, str]]:
    """
    Extracts threat indicators from text using high-precision regexes.
    Returns a deduplicated list of dicts: [{'indicator_type': '...', 'value': '...'}]
    Supported types:
    - 'crypto_wallet'
    - 'url'
    - 'phone_number'
    - 'payment_handle'
    """
    if not transcript_text:
        return []

    indicators: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str]] = set()

    def add_indicator(itype: str, val: str):
        cleaned_val = val.strip()
        key = (itype, cleaned_val)
        if key not in seen:
            seen.add(key)
            indicators.append({"indicator_type": itype, "value": cleaned_val})

    # 1. Crypto Wallets
    for match in ETH_REGEX.finditer(transcript_text):
        add_indicator("crypto_wallet", match.group(0))

    for match in BTC_BECH32_REGEX.finditer(transcript_text):
        add_indicator("crypto_wallet", match.group(0))

    for match in BTC_LEGACY_REGEX.finditer(transcript_text):
        add_indicator("crypto_wallet", match.group(0))

    # 2. URLs
    for match in URL_REGEX.finditer(transcript_text):
        cleaned = clean_url(match.group(0))
        if cleaned:
            add_indicator("url", cleaned)

    # 3. Phone Numbers
    for match in PHONE_REGEX.finditer(transcript_text):
        raw_phone = match.group(0)
        # Avoid false positives like standard numbers without phone context
        digits = re.sub(r"\D", "", raw_phone)
        if 10 <= len(digits) <= 15:
            add_indicator("phone_number", raw_phone)

    # 4. Payment Handles ($Cashtag & @handle)
    for match in CASHTAG_REGEX.finditer(transcript_text):
        add_indicator("payment_handle", match.group(0))

    for match in HANDLE_REGEX.finditer(transcript_text):
        add_indicator("payment_handle", match.group(0))

    return indicators


def extract_and_persist_indicators(
    db: Session,
    conversation_id: uuid.UUID,
    transcript_text: str,
) -> List[ThreatIndicator]:
    """
    Extracts indicators from the given text and saves any new (not-already-seen-in-this-conversation)
    indicators into the threat_indicators table with status='pending'.
    Returns the newly created ThreatIndicator records.
    """
    extracted = extract_indicators(transcript_text)
    if not extracted:
        return []

    # Get already existing indicator values for this conversation to prevent duplicates
    existing_records = (
        db.query(ThreatIndicator.value)
        .filter(ThreatIndicator.conversation_id == conversation_id)
        .all()
    )
    existing_values = {row[0] for row in existing_records}

    new_indicators: List[ThreatIndicator] = []
    for item in extracted:
        val = item["value"]
        if val not in existing_values:
            indicator_record = ThreatIndicator(
                conversation_id=conversation_id,
                indicator_type=item["indicator_type"],
                value=val,
                status="pending",
            )
            db.add(indicator_record)
            new_indicators.append(indicator_record)
            existing_values.add(val)

    if new_indicators:
        db.commit()
        for ind in new_indicators:
            db.refresh(ind)
            if ind.indicator_type == "url":
                try:
                    from app.services.enrichment import trigger_url_enrichment
                    trigger_url_enrichment(ind.id, ind.value)
                except Exception as e:
                    logger.warning(f"Error triggering URL enrichment for {ind.id}: {e}")

        logger.info(
            f"Extracted and saved {len(new_indicators)} new indicators for conversation {conversation_id}"
        )

    return new_indicators
