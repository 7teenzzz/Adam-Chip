# 08-01 — Config cleanup ✓

**Дата:** 2026-05-17
**Plan:** 08-01-PLAN.md

## Что сделано

| Файл | Изменение |
|------|-----------|
| `System/Config.json` | `services.asr.reply_silence_timeout_sec: 4.0` добавлен; `reply_absolute_deadline_sec` удалён |
| `System/Config.schema.json` | Schema-блок для `reply_silence_timeout_sec` (type=number, default=4.0, min=1.0, max=10.0, English description) добавлен; блок `reply_absolute_deadline_sec` удалён; описание `reply_window_sec` уточнено (отличается от нового) |
| `System/adam/config.py` | `DEFAULT_CONFIG["services"]["asr"]` синхронизирован |

## Verify

```
$ python3 -c '...' → Plan 08-01: OK
```

- `reply_silence_timeout_sec == 4.0` во всех трёх файлах.
- `reply_absolute_deadline_sec` отсутствует во всех трёх.
- `reply_window_sec == 3.75` нетронут.
- JSON оба валидны.

## Wave & deps

- Wave 1, depends_on: [].
- Plan 08-02 теперь может читать `asr_cfg.get("reply_silence_timeout_sec", 4.0)`.
