import logging
from enum import Enum

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    LOCAL = "local"
    UAT = "uat"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=True,
    )

    environment: Environment = Environment.LOCAL

    # Telegram
    telegram_bot_token: SecretStr

    # WhatsApp Cloud API (optional -- leave blank to disable WhatsApp)
    whatsapp_access_token: SecretStr = SecretStr("")
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: SecretStr = SecretStr("")

    # Verify API
    verify_api_url: str = "https://api-verify.straker.ai"

    # Order API (ECFMG certified translations)
    order_base_url: str = "https://order.strakertranslations.com"

    # Logging
    log_level: str = "INFO"

    # Webhook / Server
    webhook_base_url: str = ""
    webhook_secret: str = ""
    port: int = 8443

    # Verify database (for storing chat identifiers per project)
    verify_db_host: str = ""
    verify_db_port: int = 3306
    verify_db_user: str = ""
    verify_db_password: SecretStr = SecretStr("")
    verify_db_name: str = "verify"

    @field_validator("log_level", mode="after")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return upper

    @property
    def db_configured(self) -> bool:
        """Check if verify database connection is configured."""
        return bool(self.verify_db_host and self.verify_db_user)

    @property
    def whatsapp_enabled(self) -> bool:
        """Check if WhatsApp integration is configured."""
        token = self.whatsapp_access_token.get_secret_value()
        return bool(token and self.whatsapp_phone_number_id)


def get_settings() -> Settings:
    """Create and return a Settings instance."""
    return Settings()  # type: ignore[call-arg]


def setup_logging(level: str) -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Reduce noise from httpx and telegram library
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
