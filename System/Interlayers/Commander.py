from __future__ import annotations

try:
    from adam.action import Action, ActionLayer
except ImportError:  # pragma: no cover
    from System.adam.action import Action, ActionLayer  # type: ignore


__all__ = ["Action", "ActionLayer"]
