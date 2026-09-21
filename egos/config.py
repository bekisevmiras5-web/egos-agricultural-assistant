"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, ConfigDict, Field


ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"
load_dotenv(ENV_FILE)


class Settings(BaseModel):
    """Runtime settings for the bot and its HTTP health server."""

    model_config = ConfigDict(extra="ignore")

    bot_token: str = Field(default="")
    weather_api_key: str = Field(default="")
    demo_mode: bool = Field(default=True)
    database_url: str = Field(default="sqlite:///egos.db")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    def require_bot_token(self) -> None:
        """Raise a clear error when polling cannot be started."""
        if not self.bot_token.strip():
            raise ValueError(
                "BOT_TOKEN is empty. Add the token from BotFather to egos/.env."
            )

    def require_weather_api_key(self) -> None:
        """Raise a clear error when live mode has no weather key."""
        if not self.weather_api_key.strip():
            raise ValueError(
                "WEATHER_API_KEY is empty. Add a WeatherAPI.com key or set DEMO_MODE=true."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable configuration object."""
    # The Replit workspace template may expose its own DATABASE_URL for the
    # unrelated TypeScript service. EGOS is intentionally SQLite-first, so only
    # an explicit DATABASE_URL inside egos/.env can change this default.
    file_values = dotenv_values(ENV_FILE)
    database_url = str(file_values.get("DATABASE_URL") or "sqlite:///egos.db")
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        weather_api_key=os.getenv("WEATHER_API_KEY", ""),
        demo_mode=os.getenv("DEMO_MODE", "true").strip().lower()
        in {"1", "true", "yes", "on"},
        database_url=database_url,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )