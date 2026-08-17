from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    upstream_base_url: str = "http://localhost:8000"
    upstream_timeout_seconds: float = 5.0
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_timeout_seconds: float = 3.0
    gemini_confidence_threshold: float = 0.85
    log_level: str = "INFO"

    max_heals_per_transaction: int = 2
    rolling_window_seconds: float = 60.0
    rolling_window_max_heals: int = 5
    circuit_cooldown_seconds: float = 30.0

    # v0.1: HMAC proves integrity, not non-repudiation. A real deployment needs
    # asymmetric signing into WORM storage -- called out honestly in the narrative.
    hmac_secret: str = "dev-secret-change-me-in-production"


settings = Settings()
