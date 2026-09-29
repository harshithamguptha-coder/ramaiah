"""Runtime configuration for the Q-Compass backend.

Every value can be overridden with an environment variable so the same code
runs locally, in Docker, or in CI without edits.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from the environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Q-Compass API"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Comma-separated list of origins allowed to call the API.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    upload_dir: str = "uploads"
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MB
    allowed_extensions: tuple[str, ...] = (".csv", ".xlsx", ".json")

    # How many analyses to keep in the in-memory store before evicting the oldest.
    store_max_items: int = 50

    # Simulated per-stage latency (seconds) so the UI progress states are visible.
    simulate_pipeline_delay: float = 0.35

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
