"""Environment driven configuration.

Only variables that the code actually reads are defined here. Secrets are
wrapped in SecretStr so they never appear in logs or repr output.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./triage.db"
    app_secret_key: SecretStr = SecretStr("")
    cors_origins: str = "http://localhost:5173"
    trust_proxy_headers: bool = False

    # Retention and abuse limits
    conversation_retention_hours: int = Field(default=72, ge=1, le=24 * 30)
    max_messages_per_conversation: int = Field(default=60, ge=5, le=500)
    max_followup_questions: int = Field(default=8, ge=3, le=20)
    max_text_chars: int = Field(default=1000, ge=100, le=5000)
    max_json_body_bytes: int = 64 * 1024
    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_heavy_per_minute: int = Field(default=12, ge=1)

    # Audio
    max_audio_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    max_audio_seconds: int = Field(default=60, ge=5, le=300)
    min_audio_bytes: int = 1500

    # Speech to text (OpenAI compatible transcription endpoint)
    speech_api_key: SecretStr = SecretStr("")
    speech_api_base_url: str = "https://api.openai.com/v1"
    speech_model: str = "whisper-1"
    speech_default_language: str = "hi"
    speech_timeout_seconds: float = 30.0
    speech_min_confidence: float = 0.45

    # Text to speech (OpenAI compatible speech endpoint)
    tts_api_key: SecretStr = SecretStr("")
    tts_api_base_url: str = "https://api.openai.com/v1"
    tts_model: str = "tts-1"
    tts_voice: str = "nova"
    tts_timeout_seconds: float = 20.0

    # LLM (Anthropic Messages API)
    llm_api_key: SecretStr = SecretStr("")
    llm_api_base_url: str = "https://api.anthropic.com"
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_timeout_seconds: float = 15.0
    llm_extraction_enabled: bool = True
    translation_languages: str = ""

    # Deployment specific safety information. Never defaulted to a real number.
    emergency_contact_number: str = ""
    emergency_contact_label: str = ""
    crisis_helpline_number: str = ""

    metrics_enabled: bool = True
    metrics_token: SecretStr = SecretStr("")

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def translation_language_list(self) -> list[str]:
        return [o.strip() for o in self.translation_languages.split(",") if o.strip()]

    @property
    def secret_bytes(self) -> bytes:
        return self.app_secret_key.get_secret_value().encode()

    def validate_for_runtime(self) -> None:
        """Fail fast on unsafe production configuration."""
        if self.app_env == "production":
            if len(self.app_secret_key.get_secret_value()) < 32:
                raise RuntimeError("APP_SECRET_KEY must be at least 32 characters in production")
            if self.database_url.startswith("sqlite"):
                raise RuntimeError("SQLite is not supported in production, set DATABASE_URL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
