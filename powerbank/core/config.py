"""Typed application settings, loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: SecretStr = Field(alias="BOT_TOKEN")
    # Seeded as SUPER_ADMIN at every startup. This is the only way a super
    # admin is ever created -- the bot itself cannot mint one.
    # NoDecode: pydantic-settings would otherwise try to JSON-decode this at the
    # source level and fail on a plain comma-separated string. Our validator parses it.
    super_admin_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list, alias="SUPER_ADMIN_IDS"
    )

    # --- Database ---
    # Local dev defaults to SQLite; production sets a postgresql+asyncpg:// URL.
    database_url: str = Field(
        default="sqlite+aiosqlite:///./powerbank.db",
        alias="DATABASE_URL",
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    # --- Runtime ---
    environment: Literal["dev", "prod"] = Field(default="dev", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Assets ---
    assets_dir: Path = Field(default=PROJECT_ROOT / "assets", alias="ASSETS_DIR")

    @field_validator("super_admin_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, v: object) -> object:
        """Accept SUPER_ADMIN_IDS as a comma-separated string: "123,456" (or empty)."""
        if isinstance(v, str):
            return [int(part) for part in v.split(",") if part.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed exactly once per process."""
    return Settings()  # type: ignore[call-arg]
