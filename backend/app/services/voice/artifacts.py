"""Per-request artifact collection for the voice brain.

Some tools produce a downloadable side-effect (a PDF, a CSV, an invoice) on top
of the textual answer. The brain runs auto-function-calling inside the SDK so
the orchestrator never sees tool results directly — instead, tools push
artifacts here and the route reads them after ``ask_async`` returns.

ContextVar-scoped so concurrent requests don't clobber each other.
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Iterator


_artifacts: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "voice_artifacts", default=None
)


def add_artifact(artifact: dict[str, Any]) -> None:
    """Push one artifact onto the active request's list. No-op outside a request."""
    sink = _artifacts.get()
    if sink is None:
        return
    sink.append(artifact)


def collect_artifacts() -> list[dict[str, Any]]:
    """Return a copy of the current request's artifacts (or empty list)."""
    sink = _artifacts.get()
    return list(sink) if sink else []


@contextmanager
def artifacts_scope() -> Iterator[list[dict[str, Any]]]:
    """Bind a fresh artifact list for the current task, yield it, then unbind."""
    sink: list[dict[str, Any]] = []
    token: Token = _artifacts.set(sink)
    try:
        yield sink
    finally:
        _artifacts.reset(token)
