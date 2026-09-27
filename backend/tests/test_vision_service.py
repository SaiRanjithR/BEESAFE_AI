from unittest.mock import MagicMock, patch
import pytest

from app.services.vision_service import (
    caption_image,
    normalize_media_type,
    SUPPORTED_MEDIA_TYPES,
)


def test_normalize_media_type():
    assert normalize_media_type("image/jpeg") == "image/jpeg"
    assert normalize_media_type("image/jpg") == "image/jpeg"
    assert normalize_media_type("image/png; charset=utf-8") == "image/png"
    assert normalize_media_type("image/webp") == "image/webp"
    assert normalize_media_type("image/gif") == "image/gif"
    assert normalize_media_type("application/octet-stream") == "image/jpeg"
    assert normalize_media_type(None) == "image/jpeg"


def test_caption_image_with_bytes_success():
    """Test caption_image successfully calls vision model and returns formatted caption."""
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "A fake investment portfolio dashboard showing a balance of $85,000 USDT with a deposit button."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    dummy_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"

    caption = caption_image(
        image_url="https://example.com/fake_image.png",
        content_type="image/png",
        client=mock_client,
        image_bytes=dummy_bytes,
    )

    assert "fake investment portfolio" in caption
    assert "$85,000" in caption
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["messages"][0]["content"][0]["type"] == "image"
    assert call_kwargs["messages"][0]["content"][0]["source"]["media_type"] == "image/png"


def test_caption_image_http_download_success():
    """Test caption_image downloads from URL using httpx and produces caption."""
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.text = "A fraudulent banking wire transfer receipt for $10,000."
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    dummy_bytes = b"fake-jpeg-binary-data"

    mock_http_resp = MagicMock()
    mock_http_resp.status_code = 200
    mock_http_resp.content = dummy_bytes
    mock_http_resp.headers = {"content-type": "image/jpeg"}

    with patch("httpx.Client.get", return_value=mock_http_resp):
        caption = caption_image(
            image_url="https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/MM123/Media/ME123",
            client=mock_client,
        )

    assert caption == "A fraudulent banking wire transfer receipt for $10,000."


def test_caption_image_network_error_resilience():
    """
    AC: Never crash or silently drop.
    If image download fails, returns clean fallback caption string.
    """
    mock_client = MagicMock()

    with patch("httpx.Client.get", side_effect=Exception("Connection timed out")):
        caption = caption_image(
            image_url="https://example.com/unreachable.jpg",
            client=mock_client,
        )

    assert isinstance(caption, str)
    assert len(caption) > 0
    assert "attached photo" in caption or "sender" in caption
    # Model should not have been called because download failed
    mock_client.messages.create.assert_not_called()


def test_caption_image_llm_error_resilience():
    """If LLM call fails, returns fallback caption without crashing."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("Anthropic API 500 error")

    dummy_bytes = b"image-bytes"

    caption = caption_image(
        image_url="https://example.com/test.jpg",
        content_type="image/jpeg",
        client=mock_client,
        image_bytes=dummy_bytes,
    )

    assert isinstance(caption, str)
    assert "attached photo" in caption or "sender" in caption
