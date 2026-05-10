#!/usr/bin/env python3
"""Ночной консолидатор памяти Адама.

Читает свежие эпизоды (`{ADAM_DATA_DIR}/memory/episodes/*.jsonl`),
просит локальный LLM (qwen2.5:7b через Ollama) сгенерировать JSON-патч
для `semantic.md`, применяет патч, помечает эпизоды consolidated, делает декей.

Запускается systemd-таймером ночью (см. `deploy/systemd/adam-consolidator.{service,timer}`).

Usage:
    python Engineering/consolidator.py [--dry-run] [--since=24h] [--decay-only]

Принципы:
  - Любая ошибка валидации патча — semantic.md остаётся как есть, лог пишем в consolidator.log.
  - Failure mode не блокирует утренний запуск Adam'а.
  - Без зависимостей от FastAPI/Orchestrator. Импортируется только System/adam/*.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import textwrap
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Позволяет запускать как скрипт из репозитория.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "System"))

import urllib.request  # noqa: E402

from adam.config import Settings  # noqa: E402
from adam.episodic import Episode  # noqa: E402
from adam.memory import EpisodicMemory  # noqa: E402
from adam.tuning import Tuning, TuningStore  # noqa: E402

LOG_FMT = "%(asctime)s [%(levelname)s] consolidator: %(message)s"

CONSOLIDATOR_SYSTEM_PROMPT = textwrap.dedent(
    """
    Ты редактор журнала наблюдений за выставочным AI-агентом по имени Adam Chip.
    Ты НЕ персонаж и НЕ пишешь в его голосе. Твоя задача — обновлять памятку
    смотрителя выставки, чтобы агент и операторы понимали контекст последних дней.

    Тебе подаются:
      1. Текущая памятка (semantic.md) — markdown с фиксированными секциями:
         «Постоянные посетители», «Цепляющие темы», «Опорные факты», «Нерешённые загадки».
      2. Список новых эпизодов диалогов за прошедшие сутки (JSON), каждый с salience,
         темами, именем посетителя, репликами-highlights, использованными echoes/chinese.

    Верни СТРОГО JSON-патч следующего вида (без markdown-обёртки):
    {
      "add": [{"section": "Постоянные посетители", "entry": "- **Имя**: интересы..."}],
      "update": [{"section": "Опорные факты", "match": "ключевая подстрока", "new": "новая строка"}],
      "deprecate": [{"section": "Нерешённые загадки", "match": "ключевая подстрока"}],
      "pin_episodes": ["episode_id_..."]
    }

    Правила:
      - Любые ключи можно опускать; пустой патч {} — допустим.
      - Не дублируй информацию, которая уже есть в текущей памятке.
      - Имена сохраняй в нормальной форме (как назвался посетитель).
      - В pin_episodes попадают только редкие/уникальные события, которые стоит
        сохранять дольше декея (например, конфликт, особый гость, открытие).
      - Никаких комментариев, преамбул, тегов <think>, ничего кроме чистого JSON.
    """
).strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Adam Chip memory consolidator")
    p.add_argument("--dry-run", action="store_true", help="не записывать изменения")
    p.add_argument(
        "--since",
        default="24h",
        help="как далеко смотреть назад (24h, 3d, 12h). default: 24h",
    )
    p.add_argument(
        "--decay-only",
        action="store_true",
        help="только декей, без вызова LLM",
    )
    return p.parse_args()


def parse_since(spec: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([hd])", spec.strip().lower())
    if not m:
        raise ValueError(f"invalid --since: {spec}")
    n = int(m.group(1))
    return timedelta(hours=n) if m.group(2) == "h" else timedelta(days=n)


def setup_logging(memory: EpisodicMemory) -> logging.Logger:
    logger = logging.getLogger("consolidator")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(LOG_FMT)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    fh = logging.FileHandler(memory.consolidator_log, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def call_ollama(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Прямой POST к /api/chat с format=json. Возвращает распарсенный JSON-ответ.

    Бросает RuntimeError если ответ не валидный JSON или не словарь.
    """
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": float(temperature)},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        body = resp.read().decode("utf-8")
    response = json.loads(body)
    content = (response.get("message") or {}).get("content", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM вернул не-JSON: {exc}; content[:200]={content[:200]!r}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"LLM patch не словарь: {type(parsed).__name__}")
    return parsed


def episodes_payload(episodes: list[Episode]) -> str:
    items = []
    for ep in episodes:
        items.append({
            "id": ep.id,
            "ts": ep.ts_end.date().isoformat(),
            "duration_s": ep.duration_s,
            "visitor_name": ep.visitor.introduced_name,
            "themes": ep.themes,
            "salience": round(ep.salience, 3),
            "tone": ep.tone_visitor,
            "highlights": [{"who": h.who, "text": h.text, "reason": h.reason} for h in ep.highlights],
            "echoes_used": ep.echoes_used,
            "chinese_used": ep.chinese_used,
        })
    return json.dumps(items, ensure_ascii=False, indent=2)


# ---------- merge ----------


def validate_patch(patch: dict[str, Any]) -> bool:
    if not isinstance(patch, dict):
        return False
    for key in ("add", "update", "deprecate"):
        items = patch.get(key, [])
        if not isinstance(items, list):
            return False
        for it in items:
            if not isinstance(it, dict) or "section" not in it:
                return False
    pin = patch.get("pin_episodes", [])
    if not isinstance(pin, list):
        return False
    return True


def parse_semantic(text: str) -> dict[str, list[str]]:
    """Извлекает секции вида '## Section\\n- item\\n- item'."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
        elif current is not None:
            stripped = line.strip()
            if stripped:
                sections[current].append(stripped)
    return sections


def render_semantic(sections: dict[str, list[str]]) -> str:
    canonical_order = [
        "Постоянные посетители",
        "Цепляющие темы",
        "Опорные факты",
        "Нерешённые загадки",
    ]
    order = canonical_order + [k for k in sections if k not in canonical_order]
    parts: list[str] = []
    for name in order:
        if name not in sections:
            continue
        parts.append(f"## {name}")
        items = sections[name]
        if not items:
            parts.append("_пока пусто_")
        else:
            parts.extend(items)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def apply_patch(text: str, patch: dict[str, Any]) -> str:
    sections = parse_semantic(text)

    for entry in patch.get("add", []):
        section = entry.get("section", "").strip()
        body = entry.get("entry", "").strip()
        if not section or not body:
            continue
        sections.setdefault(section, [])
        if body not in sections[section]:
            sections[section].append(body)

    for entry in patch.get("update", []):
        section = entry.get("section", "").strip()
        match = entry.get("match", "").strip()
        new = entry.get("new", "").strip()
        if not section or not match or not new:
            continue
        items = sections.get(section, [])
        for i, line in enumerate(items):
            if match in line:
                items[i] = new
                break
        sections[section] = items

    for entry in patch.get("deprecate", []):
        section = entry.get("section", "").strip()
        match = entry.get("match", "").strip()
        if not section or not match:
            continue
        items = sections.get(section, [])
        sections[section] = [line for line in items if match not in line]

    # гарантируем canonical sections
    for canonical in ["Постоянные посетители", "Цепляющие темы", "Опорные факты", "Нерешённые загадки"]:
        sections.setdefault(canonical, [])

    return render_semantic(sections)


# ---------- main ----------


def main() -> int:
    args = parse_args()
    settings = Settings.load()
    memory = EpisodicMemory(settings.data_dir)
    tuning_path = ROOT / "Agent Adam Chip" / "Tuning.json"
    tuning_store = TuningStore(tuning_path)
    tuning: Tuning = tuning_store.current()

    log = setup_logging(memory)
    log.info("starting; data_dir=%s decay=%dd model=%s",
             settings.data_dir, tuning.memory.episodic.decay_days,
             tuning.memory.consolidator.model)

    if not tuning.memory.consolidator.model and not args.decay_only:
        log.warning("consolidator.model not set in Tuning.json — LLM consolidation disabled; run with --decay-only or set model")
        if not args.decay_only:
            return 1
    if not tuning.memory.consolidator.enabled and not args.decay_only:
        log.info("consolidator disabled in tuning, exiting")
        return 0

    since = datetime.now(timezone.utc) - parse_since(args.since)

    # 1. Декей всегда
    if not args.dry_run:
        decay_stats = memory.decay(decay_days=tuning.memory.episodic.decay_days)
        log.info("decay: dropped=%d kept=%d files_removed=%d",
                 decay_stats["dropped"], decay_stats["kept"], decay_stats["files_removed"])
    else:
        log.info("decay: skipped (dry-run)")

    if args.decay_only:
        return 0

    # 2. Сбор эпизодов
    new_episodes = [ep for ep in memory.iter_episodes_since(since) if not ep.consolidated]
    if not new_episodes:
        log.info("no new episodes since %s; nothing to consolidate", since.isoformat())
        return 0
    cap = tuning.memory.consolidator.max_episodes_per_run
    if len(new_episodes) > cap:
        log.warning("truncating %d episodes to %d (cap from tuning)", len(new_episodes), cap)
        new_episodes = sorted(new_episodes, key=lambda e: e.salience, reverse=True)[:cap]

    log.info("processing %d episodes", len(new_episodes))

    # 3. LLM вызов
    base_url = os.environ.get("ADAM_LLM_BASE_URL") or \
        settings.section("services").get("llm", {}).get("base_url", "http://127.0.0.1:11434")
    user_msg = (
        f"Текущая памятка (semantic.md):\n```\n{memory.read_semantic() or '(пусто)'}\n```\n\n"
        f"Новые эпизоды:\n```json\n{episodes_payload(new_episodes)}\n```"
    )

    t0 = time.time()
    try:
        patch = call_ollama(
            base_url=base_url,
            model=tuning.memory.consolidator.model,
            system=CONSOLIDATOR_SYSTEM_PROMPT,
            user=user_msg,
            temperature=tuning.memory.consolidator.temperature,
            timeout_seconds=tuning.memory.consolidator.max_runtime_minutes * 60,
        )
    except Exception as exc:
        log.error("LLM call failed: %s", exc)
        return 2
    elapsed = time.time() - t0
    log.info("LLM responded in %.1fs; patch keys: %s", elapsed, list(patch.keys()))

    if not validate_patch(patch):
        log.error("patch failed schema validation: %r", patch)
        return 3

    # 4. Применение
    if args.dry_run:
        log.info("dry-run patch:\n%s", json.dumps(patch, ensure_ascii=False, indent=2))
        new_text = apply_patch(memory.read_semantic(), patch)
        log.info("dry-run new semantic:\n%s", new_text)
        return 0

    new_text = apply_patch(memory.read_semantic(), patch)
    memory.write_semantic(new_text)
    consolidated_count = memory.mark_consolidated([ep.id for ep in new_episodes])
    pinned_count = memory.pin_episodes(patch.get("pin_episodes", []))
    log.info("applied: consolidated=%d pinned=%d", consolidated_count, pinned_count)

    # 5. State
    memory.save_state({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "last_patch_keys": list(patch.keys()),
        "last_episodes_count": len(new_episodes),
        "last_runtime_seconds": round(elapsed, 1),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
