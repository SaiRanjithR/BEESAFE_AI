import logging
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from app.config import settings

logger = logging.getLogger(__name__)


class TwilioClientError(Exception):
    """Base exception for Twilio client errors."""
    pass


class TwilioConfigurationError(TwilioClientError):
    """Raised when Twilio credentials are not configured."""
    pass


class TwilioSendError(TwilioClientError):
    """Raised when sending an outbound SMS fails."""
    pass


def send_sms(
    to_number: str,
    body: str,
    from_number: Optional[str] = None,
    client: Optional[Client] = None,
) -> str:
    """
    Sends an outbound SMS using the Twilio REST API.
    Returns the message SID on success.
    Raises TwilioSendError or TwilioConfigurationError on failure.
    """
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    default_from = from_number or settings.TWILIO_PHONE_NUMBER

    if client is None:
        if (
            not account_sid
            or account_sid.startswith("ACplaceholder")
            or not auth_token
            or auth_token == "placeholder"
        ):
            raise TwilioConfigurationError("Twilio credentials are not configured.")
        client = Client(account_sid, auth_token)

    if not default_from:
        raise TwilioConfigurationError("Twilio sender phone number is not configured.")

    try:
        message = client.messages.create(
            to=to_number,
            from_=default_from,
            body=body,
        )
        logger.info(f"Outbound SMS sent to {to_number}, SID: {message.sid}")
        return message.sid
    except TwilioRestException as e:
        logger.error(f"Failed to send SMS to {to_number}: {e}")
        raise TwilioSendError(f"Twilio API error: {e.msg}") from e
    except Exception as e:
        logger.error(f"Unexpected error sending SMS to {to_number}: {e}")
        raise TwilioSendError(f"Unexpected SMS send error: {e}") from e
