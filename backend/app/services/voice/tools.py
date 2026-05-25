"""Tool registry: a `@tool` decorator that collects Python callables.

Phase 1 leans on `google-genai`'s automatic function calling — the SDK reads each
function's signature + docstring and turns it into a Gemini function declaration.
We just keep a registry so we can introspect what's wired up and dispatch by name
when we add write-action confirmation (Phase 2).

GOTCHA: tool modules MUST NOT use `from __future__ import annotations`. The SDK
walks `func.__annotations__` and calls `isinstance(value, annotation)` directly,
which crashes when PEP-563 has turned the annotation into a string. Keep type
hints as real type objects in every module that defines `@tool` functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable
    # Phase 2 will gate writes behind an explicit confirmation arg; Phase 1 tools
    # are all read-only so this stays False for now.
    requires_confirmation: bool


_REGISTRY: dict[str, ToolSpec] = {}


def tool(*, requires_confirmation: bool = False) -> Callable[[Callable], Callable]:
    def decorator(func: Callable) -> Callable:
        name = func.__name__
        if name in _REGISTRY:
            raise ValueError(f"Tool {name!r} is already registered.")
        _REGISTRY[name] = ToolSpec(name=name, func=func, requires_confirmation=requires_confirmation)
        return func

    return decorator


def all_tool_callables() -> list[Callable]:
    return [spec.func for spec in _REGISTRY.values()]


def get_tool(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


def registered_names() -> list[str]:
    return list(_REGISTRY.keys())


def _reset_for_tests() -> None:
    _REGISTRY.clear()
