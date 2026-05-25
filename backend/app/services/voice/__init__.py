"""Voice assistant v2 — Gemini-backed brain + tool registry.

Importing this package triggers tool registration via the `actions` subpackage's
side-effect imports. Phase 1 ships a minimal turn loop and one reference tool.
"""

from . import actions  # noqa: F401 -- side-effect: registers tools

from .artifacts import artifacts_scope, collect_artifacts
from .brain import ask, ask_async
from .db_context import current_session, use_session
from .tools import all_tool_callables, get_tool

__all__ = [
    "artifacts_scope",
    "ask",
    "ask_async",
    "all_tool_callables",
    "collect_artifacts",
    "current_session",
    "get_tool",
    "use_session",
]
