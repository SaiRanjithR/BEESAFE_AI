import base64
import json
import logging
from typing import Any, Dict, List, Optional, Union

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM gateway errors."""
    pass


class LLMConfigurationError(LLMClientError):
    """Raised when no valid API key is configured."""
    pass


def get_default_provider() -> str:
    """Detects active provider based on configured keys and settings."""
    if settings.LLM_PROVIDER and settings.LLM_PROVIDER.lower() in ("gemini", "google"):
        return "gemini"
    gemini_key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        return "gemini"
    if settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY != "sk-ant-placeholder":
        return "anthropic"
    return "gemini"


_cached_gemini_client: Optional[Any] = None


def get_gemini_client(api_key: Optional[str] = None) -> Any:
    """Returns a cached, persistent genai.Client to avoid repeated SSL handshake overhead."""
    global _cached_gemini_client
    from google import genai
    from google.genai import types

    active_key = api_key or settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
    if not active_key or active_key in ("your_gemini_api_key_here", "sk-placeholder"):
        raise LLMConfigurationError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is not configured in .env. "
            "Please add a valid Google Gemini API key."
        )

    if _cached_gemini_client is None:
        _cached_gemini_client = genai.Client(
            api_key=active_key,
            http_options=types.HttpOptions(timeout=10000),
        )
    return _cached_gemini_client


def call_gemini_generate(
    system_instruction: str,
    contents: Union[str, List[Any]],
    model: Optional[str] = None,
    json_mode: bool = False,
    api_key: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """Executes a content generation request using the Google GenAI SDK."""
    from google.genai import types

    active_client = client or get_gemini_client(api_key=api_key)

    active_model = model or settings.GEMINI_MODEL or "gemini-flash-lite-latest"
    if active_model in ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-1.5-flash"):
        active_model = "gemini-flash-lite-latest"

    config_kwargs = {
        "temperature": 0.7,
        "max_output_tokens": 300,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if json_mode:
        config_kwargs["response_mime_type"] = "application/json"

    config = types.GenerateContentConfig(**config_kwargs)

    response = active_client.models.generate_content(
        model=active_model,
        contents=contents,
        config=config,
    )
    return response.text.strip() if response.text else ""


def call_anthropic_generate(
    system_instruction: str,
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """Executes a message generation request using the Anthropic SDK."""
    import anthropic

    active_key = api_key or settings.ANTHROPIC_API_KEY
    if client is None:
        if not active_key or active_key == "sk-ant-placeholder":
            raise LLMConfigurationError(
                "ANTHROPIC_API_KEY is not configured or is placeholder."
            )
        client = anthropic.Anthropic(api_key=active_key)

    active_model = model or settings.LLM_MODEL or "claude-3-5-sonnet-20241022"

    response = client.messages.create(
        model=active_model,
        system=system_instruction,
        max_tokens=1000,
        messages=messages,
    )
    return response.content[0].text.strip()


def is_gemini_client(client: Any) -> bool:
    if client is None:
        return False
    mod = getattr(type(client), "__module__", "")
    if "google" in mod or "genai" in mod:
        return True
    children = getattr(client, "_mock_children", {})
    if "models" in children and "messages" not in children:
        return True
    return False


def is_anthropic_client(client: Any) -> bool:
    if client is None:
        return False
    mod = getattr(type(client), "__module__", "")
    if "anthropic" in mod:
        return True
    children = getattr(client, "_mock_children", {})
    if "messages" in children and "models" not in children:
        return True
    return False


def generate_llm_response(
    system_instruction: str,
    conversation_turns: List[Dict[str, str]],
    model: Optional[str] = None,
    json_mode: bool = False,
    client: Optional[Any] = None,
) -> str:
    """
    Unified entrypoint for text/conversation LLM generation.
    Supports Google Gemini (default) and Anthropic Claude.
    """
    if is_anthropic_client(client):
        return call_anthropic_generate(
            system_instruction=system_instruction,
            messages=conversation_turns,
            model=model,
            client=client,
        )

    if is_gemini_client(client):
        return call_gemini_generate(
            system_instruction=system_instruction,
            contents=[turn.get("content", str(turn)) for turn in conversation_turns],
            model=model,
            json_mode=json_mode,
            client=client,
        )

    # Use configured provider
    provider = get_default_provider()
    if provider == "gemini":
        formatted_contents = []
        for turn in conversation_turns:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            prefix = "User" if role == "user" else "Assistant"
            formatted_contents.append(f"{prefix}: {content}")
        prompt_block = "\n\n".join(formatted_contents)

        return call_gemini_generate(
            system_instruction=system_instruction,
            contents=prompt_block,
            model=model,
            json_mode=json_mode,
            client=client,
        )
    else:
        return call_anthropic_generate(
            system_instruction=system_instruction,
            messages=conversation_turns,
            model=model,
            client=client,
        )


def generate_vision_caption(
    image_bytes: bytes,
    media_type: str,
    prompt: str,
    model: Optional[str] = None,
    client: Optional[Any] = None,
) -> str:
    """
    Unified entrypoint for multimodal vision captioning.
    Supports Google Gemini (default) and Anthropic Claude.
    """
    if is_anthropic_client(client):
        base64_data = base64.b64encode(image_bytes).decode("utf-8")
        import anthropic
        active_model = model or "claude-3-5-sonnet-20241022"
        response = client.messages.create(
            model=active_model,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )
        return response.content[0].text.strip()

    # Default to Gemini Vision
    from google import genai
    from google.genai import types

    active_key = settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY
    if client is None:
        if not active_key or active_key in ("your_gemini_api_key_here", "sk-placeholder"):
            raise LLMConfigurationError("GEMINI_API_KEY is not configured in .env.")
        client = genai.Client(api_key=active_key)

    active_model = model or settings.GEMINI_MODEL or "gemini-3.8-flash"
    part = types.Part.from_bytes(data=image_bytes, mime_type=media_type)

    response = client.models.generate_content(
        model=active_model,
        contents=[part, prompt],
    )
    return response.text.strip() if response.text else ""
