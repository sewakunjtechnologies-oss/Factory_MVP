from __future__ import annotations

import json
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Factory Owner MVP"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./data/factory.db"
    secret_key: str = Field(default="change-me-in-production", min_length=16)
    # 7 days. Factory owner uses the app daily — re-login once a week is
    # tolerable; anything shorter is friction. Override per env var if needed.
    access_token_expire_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"
    gemini_api_key: Optional[str] = None
    # gemini_model: regular generateContent (REST). gemini_live_model: bidiGenerateContent
    # (WebSocket voice). The Live API only accepts Live-class models — the plain
    # "gemini-2.5-flash" id does NOT support bidiGenerateContent.
    gemini_model: str = "gemini-2.5-flash"
    gemini_live_model: str = "gemini-2.5-flash-preview-native-audio-dialog"
    cors_origins: List[str] = [
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:5174",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Union[str, List[str]]) -> List[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
