from unittest.mock import MagicMock, patch
import pytest

from app.services.llm_client import (
    call_gemini_generate,
    generate_llm_response,
    generate_vision_caption,
    get_default_provider,
    LLMConfigurationError,
)


def test_get_default_provider():
    assert get_default_provider() in ("gemini", "anthropic")


def test_call_gemini_generate_with_mock():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"reply": "Hello there!", "flagged_action": null}'
    mock_client.models.generate_content.return_value = mock_response

    result = call_gemini_generate(
        system_instruction="You are a helpful persona.",
        contents="Hi Margaret!",
        model="gemini-2.5-flash",
        json_mode=True,
        client=mock_client,
    )

    assert "Hello there!" in result
    mock_client.models.generate_content.assert_called_once()
    kwargs = mock_client.models.generate_content.call_args[1]
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["config"].response_mime_type == "application/json"


def test_generate_llm_response_routes_to_gemini():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is a simulated scammer reply from Gemini."
    mock_client.models.generate_content.return_value = mock_response

    turns = [
        {"role": "user", "content": "Hi Emily, are we still meeting?"}
    ]

    result = generate_llm_response(
        system_instruction="You are a scammer bot.",
        conversation_turns=turns,
        client=mock_client,
    )

    assert result == "This is a simulated scammer reply from Gemini."
    mock_client.models.generate_content.assert_called_once()


def test_generate_vision_caption_routes_to_gemini():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "A photo of an account balance screenshot showing $50,000."
    mock_client.models.generate_content.return_value = mock_response

    dummy_bytes = b"fake-png-bytes"

    result = generate_vision_caption(
        image_bytes=dummy_bytes,
        media_type="image/png",
        prompt="Describe this image",
        client=mock_client,
    )

    assert "$50,000" in result
    mock_client.models.generate_content.assert_called_once()


def test_missing_api_key_raises_configuration_error():
    with patch("app.services.llm_client.settings.GEMINI_API_KEY", None), \
         patch("app.services.llm_client.settings.GOOGLE_API_KEY", None):
        with pytest.raises(LLMConfigurationError):
            call_gemini_generate(
                system_instruction="test",
                contents="test",
                api_key=None,
                client=None,
            )
