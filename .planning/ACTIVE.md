# ACTIVE.md — Активные ветки репозитория

Обновляется только при создании ветки или её закрытии/мёрже. Не обновляется в середине работы.

Верифицировано через `git branch -a` на 2026-05-15.

| Branch | Status | Modified areas | Merge blocker |
| ------ | ------ | -------------- | ------------- |
| `main` | stable | — | — |
| `audio-pipeline-restoration` | done, ready to merge | deploy/systemd/adam-orchestrator.service (PULSE_SOURCE), wireplumber config (вне git) | нет — оба merge condition выполнены, см. Phase 36 CONTEXT/BRANCH.md |
| `V-S06.3-opt_voice_pipe_3wave` | experimenting | System/adam/inference.py, deploy/systemd/adam-llm.service | Perf tests T1–T9 not passed |
| `ESP32-sound-out` | stale | Subsystem/AdamsServer, data/sounds | Unknown — needs triage |
| `Migration-to-ESP-mics&cam` | stale | System/Config.json, System/adam/media.py | Unknown — needs triage |
| `V_R003.2--esp32-fixes` | stale | Subsystem/AdamsServer | Unknown — needs triage |

## Как обновлять

- **При создании ветки:** добавить строку в таблицу с начальным статусом `experimenting`
- **При закрытии/мёрже:** удалить строку из таблицы (и выполнить `git rm BRANCH.md` на ветке)
