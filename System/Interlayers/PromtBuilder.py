from __future__ import annotations

try:
    from adam.prompt import PromptBuilder
except ImportError:  # pragma: no cover
    from System.adam.prompt import PromptBuilder  # type: ignore


__all__ = ["PromptBuilder"]
