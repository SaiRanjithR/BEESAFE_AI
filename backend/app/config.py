from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env values take precedence over stale host shell variables
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)
else:
    load_dotenv(override=True)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgrespassword@localhost:5432/trapline"

    # LLM provider (Google Gemini default)
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    LLM_PROVIDER: str = "gemini"

    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gemini-3.5-flash-lite"

    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    TWILIO_WEBHOOK_URL: Optional[str] = None

    # Internal API auth & Multi-Role Keys (TICKET-014)
    INTERNAL_API_KEY: str = "default_internal_api_key_for_dev"
    ADMIN_API_KEY: str = "trapline_admin_secret_key"
    ANALYST_API_KEY: str = "trapline_analyst_secret_key"
    INSTITUTION_API_KEY: str = "trapline_institution_secret_key"

    N8N_WEBHOOK_URL: Optional[str] = None
    N8N_ENRICHMENT_ENABLED: bool = False

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
