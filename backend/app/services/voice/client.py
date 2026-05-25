"""Gemini client + config. Single source of truth for model selection and key resolution.

Reads from app.core.config.settings (pydantic-settings), with `os.environ` as a
fallback so test scripts that load `.env` via python-dotenv (without going
through Settings) still work.
"""

from __future__ import annotations

import os
from functools import lru_cache

from google import genai
from google.genai import types as genai_types

from app.core.config import settings


class VoiceConfigError(RuntimeError):
    """Raised when required Gemini configuration is missing."""


def get_api_key() -> str:
    # Prefer the Settings value (loaded from .env via pydantic-settings); fall
    # back to plain os.environ for test scripts that set GEMINI_API_KEY directly.
    key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise VoiceConfigError(
            "GEMINI_API_KEY is not set. Add it to backend/.env or export it before starting uvicorn."
        )
    return key


def get_model() -> str:
    return os.environ.get("GEMINI_MODEL") or settings.gemini_model


def get_live_model() -> str:
    return os.environ.get("GEMINI_LIVE_MODEL") or settings.gemini_live_model


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    return genai.Client(api_key=get_api_key())


@lru_cache(maxsize=1)
def get_live_client() -> genai.Client:
    # Live preview models (native-audio-dialog, *-live-preview, etc.) are only
    # exposed on the v1alpha API surface. The default client uses v1beta, which
    # returns 1008 "model not found / not supported for bidiGenerateContent"
    # for every Live preview model. Pinning v1alpha here resolves that.
    return genai.Client(
        api_key=get_api_key(),
        http_options=genai_types.HttpOptions(api_version="v1alpha"),
    )
