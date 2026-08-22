from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://stockdash:stockdash@localhost:5432/stockdash"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-in-production-must-be-at-least-32-chars"
    token_encryption_key: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

    # LLM
    llm_provider: Literal["openai", "anthropic", "ollama", "groq", "gemini", "stub"] = "stub"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-haiku-20240307"
    ollama_model: str = "llama3"
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.6-27b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"

    # Market Data
    finnhub_api_key: str = ""

    # News
    news_poll_interval: int = 1800  # DEPRECATED — kept for backward compat, ignored by new scheduler
    news_collection_times: str = "09:30,20:00"  # IST, comma-separated HH:MM (9:30 AM after market opens + 8 PM evening)
    news_retention_days: int = 90  # Historical window for pattern analysis
    news_max_articles_per_user: int = 10000  # Safety cap
    newsapi_ai_key: str = ""  # newsapi.ai (Event Registry) API key

    # Broker API Keys
    groww_api_key: str = ""
    groww_api_secret: str = ""
    groww_access_token: str = ""
    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""
    snaptrade_client_id: str = ""
    snaptrade_consumer_key: str = ""
    robinhood_username: str = ""
    robinhood_password: str = ""

    # Telemetry
    telemetry_pin: str = "1234"

    # Telegram Bot
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""  # Comma-separated chat IDs that can receive messages

    # App
    environment: Literal["development", "staging", "production"] = "development"
    cors_origins: str = "http://localhost:5173"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        # Accept comma-separated origins
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
