from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_log_level: str = "INFO"

    database_url: str = "sqlite:///./ezeus.db"
    redis_url: str = "redis://localhost:6379/0"

    paperless_base_url: str = "http://localhost:8000"
    paperless_api_token: str = ""
    paperless_webhook_secret: str = ""
    admin_api_secret: str = ""
    proxy_auth_secret: str = ""
    credential_encryption_key: str = ""
    public_webhook_base_url: str = ""
    paperless_verify_tls: bool = True

    local_only: bool = True
    cloud_ai_globally_allowed: bool = False

    ollama_enabled: bool = False
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: int = 300
    ollama_max_input_chars: int = 24_000
    ollama_keep_alive: str = "10m"

    ocr_provider: str = "paddleocr"
    ocr_language: str = "de"
    ocr_device: str = "cpu"
    ocr_timeout_seconds: int = 300
    ocr_qwen_cleanup_enabled: bool = True
    ocr_qwen_cleanup_timeout_seconds: int = 180
    max_document_bytes: int = 100 * 1024 * 1024

    job_max_retries: int = 3
    job_retry_delays_seconds: Annotated[tuple[int, ...], NoDecode] = Field(default=(30, 120, 600))

    @field_validator("job_retry_delays_seconds", mode="before")
    @classmethod
    def parse_retry_delays(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(int(item.strip()) for item in value.split(",") if item.strip())
        return value

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if self.app_env == "production":
            missing = [
                name
                for name, value in (
                    ("PAPERLESS_API_TOKEN", self.paperless_api_token),
                    ("PAPERLESS_WEBHOOK_SECRET", self.paperless_webhook_secret),
                    ("ADMIN_API_SECRET", self.admin_api_secret),
                    ("CREDENTIAL_ENCRYPTION_KEY", self.credential_encryption_key),
                )
                if not value or value == "change-me" or value.startswith("example-")
            ]
            if "example-" in self.database_url:
                missing.append("DATABASE_URL")
            if missing:
                raise ValueError(f"Missing secure configuration: {', '.join(missing)}")
        if self.cloud_ai_globally_allowed and self.local_only:
            raise ValueError("Cloud AI cannot be enabled while LOCAL_ONLY is true")
        if self.ollama_timeout_seconds <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be positive")
        if self.ollama_max_input_chars < 1000:
            raise ValueError("OLLAMA_MAX_INPUT_CHARS must be at least 1000")
        if self.job_max_retries < 0:
            raise ValueError("JOB_MAX_RETRIES must not be negative")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
