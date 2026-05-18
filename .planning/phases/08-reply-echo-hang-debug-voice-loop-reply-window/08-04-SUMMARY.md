# 08-04 — UAT tooling ✓ (manual UAT pending)

**Дата:** 2026-05-17
**Plan:** 08-04-PLAN.md

## Что сделано

### `scripts/adam_test_reply_hang.py` (новый, исполняемый, Python 3 stdlib only)

- CLI: `--events-file`, `--last-minutes N` (default 5), `--follow` (live tail),
  `--warn-gap-sec` (6.0), `--error-gap-sec` (30.0), `--verbose`.
- Snapshot mode: парсит events.jsonl за последние N минут, считает gap между `voice_loop_heartbeat`, печатает OK/WARN/ERROR с последним `voice_state_change` перед худшим gap.
- Follow mode: tail новых heartbeat events с пометками OK/WARN/ERROR в реальном времени.
- Exit codes: 0 (ok/warn), 1 (error / loop frozen), 2 (events не найдены).
- Stdlib only (argparse, json, time, pathlib, datetime, sys, os).

### `docs/RUNBOOK_JETSON_EXHIBITION.md` — раздел "Reply hang diagnosis"

- Описание симптома и базовая команда `python3 scripts/adam_test_reply_hang.py --last-minutes 5`.
- Интерпретация результатов (OK / WARN / ERROR).
- Чек-лист действий при ERROR: сохранить tail/journalctl, остановить service, завести follow-up фазу под SIGUSR1.
- Что Phase 8 уже устранил vs что осталось как риск.

## Verify (Task 1 + Task 2)

```
$ python3 scripts/adam_test_reply_hang.py --help    → prints Russian help
$ python3 scripts/adam_test_reply_hang.py --events-file /nonexistent.jsonl  → exit 2
$ test -x scripts/adam_test_reply_hang.py           → executable
$ python3 -c "import ast; ast.parse(...)"           → AST OK
$ grep -c "^## Reply hang diagnosis" docs/RUNBOOK_JETSON_EXHIBITION.md   → 1
$ grep -c "adam_test_reply_hang.py" docs/RUNBOOK_JETSON_EXHIBITION.md    → 2
$ grep -c "SIGUSR1" docs/RUNBOOK_JETSON_EXHIBITION.md                     → 2
```

## Task 3 — Manual UAT: **PENDING**

Требует живой Jetson + ESP32 + микрофон + 5 минут активного использования
(минимум 3 wake → reply → silence циклов). Не выполнено в этой сессии — оператор
должен сделать вручную перед закрытием Phase 8.

**Чек-лист manual UAT** (выполнить на Jetson после деплоя ветки):

1. `sudo systemctl restart adam-orchestrator.service adam-tts-silero.service adam-asr-whisperx.service`
2. Минимум 5 минут активного использования — wake → запрос → reply → молчание; повторить ≥ 3 раза.
3. Дополнительно 2-3 минуты idle после последнего reply.
4. `python3 scripts/adam_test_reply_hang.py --last-minutes 8` → ожидаемо `OK`.
5. Подтвердить наличие новых событий:

   ```bash
   grep -c '"name": *"voice_loop_heartbeat"' data/adam/events.jsonl   # ≥ 80 за 8 мин
   grep -c '"name": *"voice_state_change"' data/adam/events.jsonl     # ≥ 6
   grep -c '"reason": *"reply_silence_timeout"' data/adam/events.jsonl  # ≥ 3
   ```

6. Если UAT прошёл — Phase 8 готова к verification + close.
   Если UAT упал (gap > 30 sec) — сохранить `/tmp/hang-tail.jsonl`,
   обновить CONTEXT.md §Deferred что SIGUSR1 фаза становится приоритетной,
   завести follow-up фазу.

## Wave & deps

- Wave 3, depends_on: [08-02, 08-03].
- Завершает Phase 8 (с оговоркой про manual UAT).
