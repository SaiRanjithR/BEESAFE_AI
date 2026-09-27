import base64
import logging
from typing import Optional
import httpx
import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_MEDIA_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}


def normalize_media_type(raw_type: Optional[str]) -> str:
    """Normalizes raw MIME types to Anthropic-supported image types."""
    if not raw_type:
        return "image/jpeg"
    cleaned = raw_type.split(";")[0].strip().lower()
    return SUPPORTED_MEDIA_TYPES.get(cleaned, "image/jpeg")


def caption_image(
    image_url: str,
    content_type: Optional[str] = None,
    client: Optional[anthropic.Anthropic] = None,
    image_bytes: Optional[bytes] = None,
) -> str:
    """
    Downloads an MMS image (or uses provided bytes), encodes it to base64,
    and calls a vision-capable Claude model to produce a concise 1-2 sentence caption.

    Resilience guarantee:
    Never raises an uncaught exception; returns a fallback caption on network or LLM errors
    to prevent dropping or crashing incoming webhook turns.
    """
    try:
        # 1. Fetch image bytes if not provided directly
        if image_bytes is None:
            auth = None
            if (
                settings.TWILIO_ACCOUNT_SID
                and settings.TWILIO_AUTH_TOKEN
                and "twilio.com" in image_url.lower()
            ):
                auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            with httpx.Client(timeout=10.0, follow_redirects=True) as http_client:
                resp = http_client.get(image_url, auth=auth)
                resp.raise_for_status()
                image_bytes = resp.content
                if not content_type:
                    content_type = resp.headers.get("content-type")

        if not image_bytes:
            logger.warning(f"Empty image bytes received for URL: {image_url}")
            return "empty media attachment"

        media_type = normalize_media_type(content_type)
        base64_data = base64.b64encode(image_bytes).decode("utf-8")

        from app.services.llm_client import generate_vision_caption

        prompt_text = (
            "Provide a concise, factual 1-2 sentence caption of what this image shows. "
            "Focus specifically on visible text, monetary amounts, investment charts, cryptocurrency wallet addresses, "
            "QR codes, certificates, badges, or payment receipts. "
            "Do not start with 'This image shows' or add introductory filler."
        )

        caption = generate_vision_caption(
            image_bytes=image_bytes,
            media_type=media_type,
            prompt=prompt_text,
            client=client,
        )

        caption = caption.strip('"\']')
        return caption if caption else "unspecified visual media"

    except Exception as e:
        logger.warning(f"Vision captioning failed for {image_url}: {e}")
        return "attached photo or screenshot from sender"
