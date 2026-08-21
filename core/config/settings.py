from functools import lru_cache
from typing import Annotated

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL


def _is_insecure_placeholder(value: str) -> bool:
    return not value or value == "change-me" or value.startswith("example-")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    # Containers deliberately bind all pod interfaces; exposure is controlled
    # by the Service/Ingress or the loopback-only Compose port mapping.
    app_host: str = "0.0.0.0"  # nosec B104
    app_port: int = 8080
    app_log_level: str = "INFO"
    forwarded_allow_ips: str = "127.0.0.1"

    # Kubernetes injects the individual POSTGRES_* values so the password never
    # has to be interpolated inside a ConfigMap.  DATABASE_URL still takes
    # precedence for managed databases and existing installations.
    database_url: str = ""
    postgres_host: str = ""
    postgres_port: int = 5432
    postgres_user: str = "ezeus"
    postgres_database: str = "ezeus"
    postgres_password: str = ""
    redis_url: str = "redis://localhost:6379/0"

    paperless_base_url: str = "http://localhost:8000"
    paperless_api_token: str = ""
    paperless_webhook_secret: str = ""
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
    ollama_max_response_bytes: int = 1_048_576
    ollama_keep_alive: str = "10m"

    job_max_retries: int = 3
    job_retry_delays_seconds: Annotated[tuple[int, ...], NoDecode] = Field(default=(30, 120, 600))

    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 120
    rate_limit_burst: int = 30
    rate_limit_max_clients: int = 10_000
    rate_limit_trust_proxy_headers: bool = False
    rate_limit_exempt_paths: Annotated[tuple[str, ...], NoDecode] = Field(
        default=("/health", "/ready", "/static/")
    )

    outbound_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = Field(default=())
    outbound_private_allowed_hosts: Annotated[tuple[str, ...], NoDecode] = Field(default=())
    outbound_block_private_networks: bool = True

    paperless_max_download_bytes: int = 50 * 1024 * 1024
    paperless_max_text_chars: int = 2_000_000
    allowed_document_mime_types: Annotated[tuple[str, ...], NoDecode] = Field(
        default=(
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/tiff",
            "image/webp",
            "text/plain",
        )
    )

    regex_hard_timeout_seconds: float = 2.0

    outbox_poll_seconds: float = 1.0
    outbox_claim_timeout_seconds: int = 300
    outbox_batch_size: int = 50
    outbox_max_backoff_seconds: int = 300

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("job_retry_delays_seconds", mode="before")
    @classmethod
    def parse_retry_delays(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(int(item.strip()) for item in value.split(",") if item.strip())
        return value

    @field_validator(
        "rate_limit_exempt_paths",
        "outbound_allowed_hosts",
        "outbound_private_allowed_hosts",
        "allowed_document_mime_types",
        mode="before",
    )
    @classmethod
    def parse_csv_tuple(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        if not self.database_url:
            if self.postgres_host:
                self.database_url = URL.create(
                    "postgresql+psycopg",
                    username=self.postgres_user,
                    password=self.postgres_password,
                    host=self.postgres_host,
                    port=self.postgres_port,
                    database=self.postgres_database,
                ).render_as_string(hide_password=False)
            else:
                self.database_url = "sqlite:///./ezeus.db"
        if self.app_env == "production":
            missing = [
                name
                for name, value in (
                    ("PAPERLESS_API_TOKEN", self.paperless_api_token),
                    ("PAPERLESS_WEBHOOK_SECRET", self.paperless_webhook_secret),
                    ("CREDENTIAL_ENCRYPTION_KEY", self.credential_encryption_key),
                )
                if _is_insecure_placeholder(value)
            ]
            if self.postgres_host and _is_insecure_placeholder(self.postgres_password):
                missing.append("POSTGRES_PASSWORD")
            if (
                self.database_url.startswith("sqlite")
                or "change-me" in self.database_url
                or "example-" in self.database_url
                or "$(" in self.database_url
            ):
                missing.append("DATABASE_URL")
            if missing:
                raise ValueError(f"Missing secure configuration: {', '.join(missing)}")
            try:
                Fernet(self.credential_encryption_key.encode())
            except (TypeError, ValueError) as exc:
                raise ValueError("CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key") from exc
        if self.cloud_ai_globally_allowed and self.local_only:
            raise ValueError("Cloud AI cannot be enabled while LOCAL_ONLY is true")
        if self.ollama_timeout_seconds <= 0:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be positive")
        if self.ollama_max_input_chars < 1000 or self.ollama_max_response_bytes <= 0:
            raise ValueError("Ollama input and response limits must be positive")
        if self.job_max_retries < 0:
            raise ValueError("JOB_MAX_RETRIES must not be negative")
        if self.rate_limit_requests_per_minute <= 0:
            raise ValueError("RATE_LIMIT_REQUESTS_PER_MINUTE must be positive")
        if self.rate_limit_burst < 0:
            raise ValueError("RATE_LIMIT_BURST must not be negative")
        if self.rate_limit_max_clients <= 0:
            raise ValueError("RATE_LIMIT_MAX_CLIENTS must be positive")
        if self.paperless_max_download_bytes <= 0 or self.paperless_max_text_chars <= 0:
            raise ValueError("Paperless response limits must be positive")
        if self.regex_hard_timeout_seconds <= 0:
            raise ValueError("REGEX_HARD_TIMEOUT_SECONDS must be positive")
        if self.outbox_poll_seconds <= 0 or self.outbox_claim_timeout_seconds <= 0:
            raise ValueError("Outbox timing values must be positive")
        if self.outbox_batch_size <= 0 or self.outbox_max_backoff_seconds <= 0:
            raise ValueError("Outbox limits must be positive")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
