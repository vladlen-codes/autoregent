from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    upstream_base_url: str = "http://localhost:8000"
    upstream_timeout_seconds: float = 5.0
    gemini_api_key: str | None = None
    log_level: str = "INFO"


settings = Settings()
