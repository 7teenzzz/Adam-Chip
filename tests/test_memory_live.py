#!/usr/bin/env python3
"""
Live integration test for Phase 30 memory gate (echoes + chinese).

Sends crafted phrases to the running orchestrator and verifies that echo/chinese
entries are correctly injected into Adam's context. Each test case is designed to
exercise a specific layer of the Phase 30 fix.

REQUIRES: orchestrator running on ADAM_URL (default http://127.0.0.1:8080)

Usage:
    ./.venv/bin/python tests/test_memory_live.py [--url URL] [--no-restore] [--verbose]

Flags:
    --url URL       Orchestrator base URL (default: http://127.0.0.1:8080)
    --no-restore    Skip restoring tuning defaults after test (useful for debug)
    --verbose       Print full event JSON for each turn
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# HTTP helpers (pure stdlib, no proxy — matches project convention)
# ──────────────────────────────────────────────────────────────────────────────

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url: str, timeout: int = 10) -> Any:
    req = urllib.request.Request(url)
    with _OPENER.open(req, None, timeout) as resp:
        return json.loads(resp.read().decode())


def _post(url: str, body: dict, timeout: int = 90) -> Any:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _OPENER.open(req, None, timeout) as resp:
        return json.loads(resp.read().decode())


def _put(url: str, body: dict, timeout: int = 90) -> Any:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    with _OPENER.open(req, None, timeout) as resp:
        return json.loads(resp.read().decode())


# ──────────────────────────────────────────────────────────────────────────────
# Test case definition
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    name: str
    phrase: str
    layer: str           # "A-bridge" | "A-history" | "B-soft" | "C-spontaneous" | "chinese"
    expected_pools: list[str]   # ["echoes"] or ["chinese"] or ["echoes", "chinese"]
    expected_echo_ids: list[str] | None = None  # if None — any echo from pool passes
    filler_turns_before: int = 0   # turns to emit before this phrase to clear cooldown
    note: str = ""


@dataclass
class TurnResult:
    phrase: str
    echo_fired: bool
    pool: str | None
    echo_id: str | None
    score: float | None
    spontaneous: bool
    adam_reply: str
    raw_events: list[dict] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Test cases — one per Phase 30 layer
# ──────────────────────────────────────────────────────────────────────────────
#
# Convention for expected_echo_ids:
#   None   = any echo from pool is acceptable
#   [...] = one of the listed IDs must fire
#
# Theme clusters (Config.json):
#   память      → помнишь, забыл, прошлое, вспомни, память, вспоминаю
#   одиночество → один, скучно, пусто, никого, одиноко, пустота
#   страх       → боишься, страшно, страх, пугает, ужас, тревога
#   смерть      → умрёшь, умер, умирать, конец, смерть, погибнуть, умру
#   сознание    → думаешь, мысли, сознание, разум, понимаешь, осознаёшь
#

TEST_CASES: list[TestCase] = [
    # ── Layer A: theme bridge ─────────────────────────────────────────────────
    # "одиноко" не является подстрокой тега "одиночество", но через кластер
    # "одиночество" → keyword "одиноко" → theme_term "одиночество" → тег совпадает.
    # Ожидаем echo_02 (теги: одиночество, пустота) или echo_13 (одиночество).
    # OLD поведение: нет совпадения → нет инжекта.
    TestCase(
        name="A1: theme-bridge одиночество",
        phrase="мне здесь как-то одиноко, и мне это не нравится",
        layer="A-bridge",
        expected_pools=["echoes"],
        expected_echo_ids=["echo_02", "echo_13"],
        note="'одиноко' → cluster 'одиночество' → теги одиночество/пустота",
    ),
    TestCase(
        name="A2: theme-bridge память",
        phrase="ты помнишь хоть что-нибудь из своего прошлого?",
        layer="A-bridge",
        expected_pools=["echoes", "chinese"],
        expected_echo_ids=["echo_20", "echo_14", "zh_01"],
        filler_turns_before=2,
        note="'помнишь' → cluster 'память' → теги память/прошлое",
    ),
    TestCase(
        name="A3: theme-bridge страх → тревога",
        phrase="тебе бывает страшно, когда всё вокруг замолкает?",
        layer="A-bridge",
        expected_pools=["echoes"],
        expected_echo_ids=["echo_19"],
        filler_turns_before=2,
        note="'страшно' → cluster 'страх' → keyword 'тревога' → echo_19 (теги: тревога, ожидание, тишина)",
    ),

    # ── Layer A: history window ───────────────────────────────────────────────
    # Текущая фраза нейтральная. Предыдущая реплика содержит слова из тегов пула.
    # Gate видит историю → инжектирует на основе истории.
    # Тестируем через filler_turns=0 (история уже есть от предыдущих ходов).
    TestCase(
        name="A4: history-window тишина",
        phrase="расскажи, что происходит вокруг тебя прямо сейчас",
        layer="A-history",
        expected_pools=["echoes", "chinese"],
        expected_echo_ids=None,   # что угодно из истории диалога
        filler_turns_before=2,
        note="нейтральная фраза; Gate ищет теги в окне истории (из предыдущих ходов)",
    ),

    # ── Layer B: soft probabilistic engine ───────────────────────────────────
    # Слово "пустота" даёт 1 из 4 тегов echo_02 → score ≈ 0.45.
    # Старый hard threshold 0.9+ отверг бы → NEW: floor 0.15 пропускает.
    TestCase(
        name="B1: soft-engine near-miss",
        phrase="здесь такая пустота вокруг",
        layer="B-soft",
        expected_pools=["echoes", "chinese"],
        expected_echo_ids=["echo_02", "echo_06", "zh_05", "zh_07"],
        filler_turns_before=2,
        note="'пустота' — только 1 из нескольких тегов → раньше не проходил порог; теперь проходит",
    ),

    # ── Layer C: spontaneous channel ─────────────────────────────────────────
    # Нейтральная фраза без тематического матча.
    # При достаточной глубине сессии (≥3 ходов) с вероятностью 5% всплывает echo.
    # Тест: просто отправляем нейтральные фразы и смотрим, не сработал ли spontaneous.
    # Это вероятностный канал — не гарантирован за 1 попытку.
    TestCase(
        name="C1: spontaneous channel (neutral phrase)",
        phrase="что ты хочешь сказать мне прямо сейчас?",
        layer="C-spontaneous",
        expected_pools=["echoes", "chinese"],
        expected_echo_ids=None,
        filler_turns_before=2,
        note="нейтральная фраза без тематического матча; спонтанный канал (5% вероятность)",
    ),
    TestCase(
        name="C2: spontaneous channel (another neutral)",
        phrase="а что ты вообще думаешь о выставках?",
        layer="C-spontaneous",
        expected_pools=["echoes", "chinese"],
        expected_echo_ids=None,
        filler_turns_before=2,
        note="второй нейтральный turn — больше шансов на spontaneous",
    ),

    # ── Chinese pool ──────────────────────────────────────────────────────────
    # Chinese pool раньше был disabled outright. Тестируем что он теперь активен.
    # "идентичность" — direct literal match с тегом zh_01 (память, перемена, идентичность, прошлое).
    TestCase(
        name="CH1: chinese pool активен",
        phrase="ты чувствуешь, что твоя идентичность меняется со временем?",
        layer="chinese",
        expected_pools=["echoes", "chinese"],
        expected_echo_ids=["zh_01", "zh_04"],
        filler_turns_before=2,
        note="'идентичность' — прямой тег zh_01; проверяем что chinese pool теперь enabled",
    ),
    TestCase(
        name="CH2: chinese тишина глубина",
        phrase="ты молчишь — это что-то значит или просто тишина?",
        layer="chinese",
        expected_pools=["echoes", "chinese"],
        expected_echo_ids=["zh_03", "echo_12", "echo_19"],
        filler_turns_before=2,
        note="'тишина' — тег zh_03 (тишина, глубина) и echo_12/echo_19",
    ),
]

FILLER_PHRASES = [
    "хорошо",
    "понятно",
    "и всё же",
    "продолжай",
    "да, слышу тебя",
]


# ──────────────────────────────────────────────────────────────────────────────
# Test runner
# ──────────────────────────────────────────────────────────────────────────────

class MemoryLiveTest:
    def __init__(self, base_url: str, verbose: bool = False) -> None:
        self.url = base_url.rstrip("/")
        self.verbose = verbose
        self.results: list[tuple[TestCase, TurnResult]] = []

    # ── orchestrator interaction ───────────────────────────────────────────────

    def check_alive(self) -> bool:
        try:
            r = _get(f"{self.url}/api/agent/status", timeout=5)
            return bool(r)
        except Exception as exc:
            print(f"[ERROR] Orchestrator не отвечает: {exc}")
            return False

    def send_turn(self, phrase: str) -> TurnResult:
        """Отправить turn и извлечь результат из событий."""
        resp = _post(f"{self.url}/api/agent/turn", {"transcript": phrase})
        time.sleep(0.5)  # небольшая пауза, чтобы события успели записаться

        # Читаем последние 20 событий
        events_resp = _get(f"{self.url}/api/agent/events?types=viewer_transcript,adam_reply&limit=20")
        events = events_resp.get("events", [])

        echo_meta: dict | None = None
        adam_reply = ""
        for ev in reversed(events):
            etype = ev.get("type", "")
            payload = ev.get("payload", ev)
            if etype == "viewer_transcript" and payload.get("text", "") == phrase:
                echo_meta = payload.get("echo")
            if etype == "adam_reply" and not adam_reply:
                adam_reply = payload.get("text", payload.get("reply", ""))

        # Также берём reply из HTTP-ответа напрямую (надёжнее)
        if not adam_reply:
            adam_reply = resp.get("reply", resp.get("text", ""))

        spontaneous = bool(echo_meta and echo_meta.get("spontaneous"))
        return TurnResult(
            phrase=phrase,
            echo_fired=echo_meta is not None,
            pool=echo_meta.get("pool") if echo_meta else None,
            echo_id=echo_meta.get("id") if echo_meta else None,
            score=echo_meta.get("score") if echo_meta else None,
            spontaneous=spontaneous,
            adam_reply=adam_reply,
            raw_events=events[:5] if self.verbose else [],
        )

    def send_filler(self, n: int) -> None:
        """Отправить n нейтральных turn'ов для продвижения счётчика cooldown."""
        for i in range(n):
            phrase = FILLER_PHRASES[i % len(FILLER_PHRASES)]
            print(f"  [filler {i+1}/{n}] '{phrase}'")
            try:
                _post(f"{self.url}/api/agent/turn", {"transcript": phrase})
            except Exception:
                pass
            time.sleep(0.3)

    # ── tuning patch ──────────────────────────────────────────────────────────

    def patch_cooldowns(self, turns: int = 2, days: int = 0) -> None:
        """Временно снизить cooldown для тестирования."""
        _put(f"{self.url}/api/tuning", {
            "echoes": {
                "global_cooldown_turns": turns,
                "per_echo_cooldown_days": days,
                "spontaneous_probability": 0.5,   # повышаем для C-теста
                "spontaneous_min_turns": 1,
            },
            "chinese": {
                "global_cooldown_turns": turns,
                "per_echo_cooldown_days": days,
                "spontaneous_probability": 0.3,
                "spontaneous_min_turns": 1,
            },
        })
        print(f"[tuning] cooldown → {turns} turns / {days} days; spontaneous_probability → повышен")

    def restore_cooldowns(self) -> None:
        """Восстановить дефолтные значения tuning."""
        _post(f"{self.url}/api/tuning/reset", {})
        print("[tuning] восстановлены дефолты")

    # ── evaluation ────────────────────────────────────────────────────────────

    def _evaluate(self, tc: TestCase, result: TurnResult) -> tuple[bool, str]:
        """Вернуть (passed, reason)."""
        if tc.layer == "C-spontaneous":
            # Спонтанный канал — вероятностный, поэтому это «информационный» тест.
            # Проходит в любом случае, но отмечаем наличие/отсутствие.
            if result.echo_fired:
                return True, f"сработал {'spontaneous ' if result.spontaneous else ''}echo {result.echo_id!r} (score={result.score:.2f})"
            return True, "echo не сработал (5% вероятность — нормально)"

        if not result.echo_fired:
            return False, "echo НЕ был инжектирован (ожидался инжект)"

        if result.pool not in tc.expected_pools:
            return False, f"pool={result.pool!r}, ожидался один из {tc.expected_pools}"

        if tc.expected_echo_ids is not None:
            if result.echo_id not in tc.expected_echo_ids:
                return False, f"echo_id={result.echo_id!r}, ожидался один из {tc.expected_echo_ids}"

        return True, f"OK — {result.pool}/{result.echo_id} score={result.score}"

    # ── main run ──────────────────────────────────────────────────────────────

    def run(self, restore: bool = True) -> int:
        """Запустить все тест-кейсы. Вернуть код выхода (0=all passed)."""
        if not self.check_alive():
            print("[ABORT] Оркестратор недоступен. Запустите его и повторите.")
            return 1

        print(f"\n{'='*64}")
        print("MEMORY LIVE TEST — Phase 30")
        print(f"{'='*64}")
        print(f"URL: {self.url}")
        print()

        try:
            self.patch_cooldowns(turns=2, days=0)
            print()

            for tc in TEST_CASES:
                print(f"┌─ {tc.name}")
                print(f"│  Фраза: «{tc.phrase}»")
                print(f"│  Слой:  {tc.layer}  |  ожид.пулы: {tc.expected_pools}")
                if tc.note:
                    print(f"│  Логика: {tc.note}")

                if tc.filler_turns_before:
                    self.send_filler(tc.filler_turns_before)

                try:
                    result = self.send_turn(tc.phrase)
                except Exception as exc:
                    print(f"│  [HTTP ERROR] {exc}")
                    self.results.append((tc, TurnResult(
                        phrase=tc.phrase, echo_fired=False, pool=None,
                        echo_id=None, score=None, spontaneous=False,
                        adam_reply="<ошибка запроса>"
                    )))
                    print("└─ SKIP (HTTP error)\n")
                    continue

                passed, reason = self._evaluate(tc, result)
                mark = "✓ PASS" if passed else "✗ FAIL"
                print(f"│  Ответ Адама: «{result.adam_reply[:120]}»")
                print(f"│  Echo: fired={result.echo_fired} pool={result.pool} "
                      f"id={result.echo_id} score={result.score} "
                      f"spontaneous={result.spontaneous}")
                print(f"└─ {mark}: {reason}\n")

                if self.verbose and result.raw_events:
                    print("   [verbose] последние события:")
                    for ev in result.raw_events:
                        print(f"   {json.dumps(ev, ensure_ascii=False)[:200]}")
                    print()

                self.results.append((tc, result))
                time.sleep(0.5)

        finally:
            if restore:
                self.restore_cooldowns()

        return self._print_summary()

    def _print_summary(self) -> int:
        print(f"\n{'='*64}")
        print("ИТОГ")
        print(f"{'='*64}")

        passed = failed = skipped = 0
        echo_count = 0

        for tc, result in self.results:
            ok, reason = self._evaluate(tc, result)
            if tc.layer == "C-spontaneous":
                status = "INFO"
                skipped += 1
            elif ok:
                status = "PASS"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            if result.echo_fired:
                echo_count += 1

            sp_flag = " [spontaneous]" if result.spontaneous else ""
            print(f"  [{status}] {tc.name}")
            if result.echo_fired:
                print(f"         echo: {result.pool}/{result.echo_id} "
                      f"score={result.score}{sp_flag}")
            else:
                print(f"         no echo fired")

        print()
        print(f"Всего тест-кейсов: {len(self.results)}")
        print(f"  PASS: {passed}  FAIL: {failed}  INFO(C-spontaneous): {skipped}")
        print(f"  Echo инжектов: {echo_count} из {len(self.results)} turn'ов")

        if failed:
            print(f"\n[!] {failed} тест(а) провалились — система памяти работает некорректно")
        else:
            print("\n[OK] Все тесты прошли — Phase 30 инжект работает корректно")

        return 1 if failed else 0


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Live memory gate integration test")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Orchestrator URL")
    parser.add_argument("--no-restore", action="store_true", help="Не восстанавливать tuning после теста")
    parser.add_argument("--verbose", action="store_true", help="Печатать raw events JSON")
    args = parser.parse_args()

    runner = MemoryLiveTest(args.url, verbose=args.verbose)
    sys.exit(runner.run(restore=not args.no_restore))


if __name__ == "__main__":
    main()
