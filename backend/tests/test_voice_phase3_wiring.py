"""Phase 3 wiring smoke tests.

These verify the plumbing — route registration, tool-declaration construction,
config builder — without opening a real WebSocket to Gemini. End-to-end audio
testing requires a microphone and quota and is done manually in the browser.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def test_voice_ws_route_is_registered() -> None:
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/api/v1/voice/stream" in paths, (
        f"voice WS route not registered; got: {sorted(p for p in paths if 'voice' in p)}"
    )


def test_live_config_includes_all_tools() -> None:
    """The Live API uses hand-built FunctionDeclarations instead of auto-FC, so
    confirm every registered tool successfully converts to a declaration."""
    from app.services.voice.live import _tool_declarations
    from app.services.voice.tools import registered_names

    declarations = _tool_declarations()
    declared_names = {d.name for d in declarations}
    assert declared_names == set(registered_names()), (
        f"missing declarations: registered={set(registered_names())} declared={declared_names}"
    )


def test_live_config_response_modality_is_audio() -> None:
    from app.services.voice.live import _live_config

    cfg = _live_config()
    modalities = [m.value if hasattr(m, "value") else str(m) for m in (cfg.response_modalities or [])]
    assert any(m.upper() == "AUDIO" for m in modalities), (
        f"Live config must request AUDIO modality; got: {modalities}"
    )
    # System instruction must include the write-action confirmation rule so
    # the model knows to use the two-step confirmed=False / confirmed=True flow.
    instruction_text = ""
    if cfg.system_instruction:
        for part in cfg.system_instruction.parts or []:
            instruction_text += getattr(part, "text", "") or ""
    assert "confirmation" in instruction_text.lower()
    assert "confirmed" in instruction_text.lower()


def test_live_model_env_override() -> None:
    """Confirm get_live_model picks up the env var if set, otherwise the default."""
    import importlib

    import app.services.voice.client as client_mod

    original = os.environ.get("GEMINI_LIVE_MODEL")
    try:
        os.environ["GEMINI_LIVE_MODEL"] = "test-live-model"
        importlib.reload(client_mod)
        assert client_mod.get_live_model() == "test-live-model"
    finally:
        if original is None:
            os.environ.pop("GEMINI_LIVE_MODEL", None)
        else:
            os.environ["GEMINI_LIVE_MODEL"] = original
        importlib.reload(client_mod)
