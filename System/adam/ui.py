from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "WebUI" / "templates"


def _json_script_value(value: dict[str, Any]) -> str:
    return json.dumps(value).replace("</", "<\\/")


def _load(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def agent_page() -> str:
    return _load("agent.html")


def dash_page(settings_public: dict[str, Any]) -> str:
    config = _json_script_value(settings_public)
    return _load("dash.html").replace("__ADAM_CONFIG__", config)


def debug_page(settings_public: dict[str, Any]) -> str:
    config = _json_script_value(settings_public)
    return _load("debug.html").replace("__ADAM_CONFIG__", config)
