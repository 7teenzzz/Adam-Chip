# Phase 43: Boot Autostart Switch — CONTEXT

**Date:** 2026-10-15 · **Branch:** main · **Status:** implemented, awaiting Jetson verification

## Goal

Одна кнопка «Адам стартует при загрузке Jetson: да/нет» — в терминале (TUI) и в вебе (Настройки).

## Decisions

- **D-01 Источник истины — systemd + Docker, не Config.json.** Состояние = `systemctl is-enabled` юнитов
  + restart policy контейнера ASR. В Config.json (`system.autostart`) только *список* того, что переключать.
  Иначе две правды расходятся после ручного `systemctl enable`.
- **D-02 Набор:** `adam-llm`, `adam-tts-silero`, `adam-orchestrator`, `adam-exhibition.target` +
  Docker `adam-asr-whisperx` (`unless-stopped` ↔ `no`). VLM уже выключен отдельно.
- **D-03 Логвьюер вне переключателя.** Переведён на `WantedBy=multi-user.target` и убран `PartOf` —
  раньше он стартовал только через exhibition.target, выключение target убило бы диагностику.
- **D-04 Переключение влияет только на следующую загрузку.** Ничего не стартует/не останавливается сразу.
- **D-05 Права:** точные NOPASSWD-правила `systemctl enable|disable <unit>` (без wildcard) генерирует
  `adam_install_systemd.sh` в `/etc/sudoers.d/adam-autostart` из списка в конфиге, проверка `visudo -c`.
  `can_manage` парсит `sudo -n -l` по NOPASSWD-строкам (`sudo -l <cmd>` даёт ложное «да» из-за `(ALL) ALL`).
- **D-06 Переустановка сохраняет выбор:** установщик не включает автозапуск, если orchestrator был disabled.
- **D-07 Фикс попутно:** `adam-exhibition.target` требовал замаскированный `adam-asr-whisperx.service` →
  падал с `dependency` на каждой загрузке. Убран из Requires/After; убран и `Wants=adam-vlm` (VLM выключен по OOM).
- **D-08 Ограничение:** если автозапуск выключен, веб-UI (:8080) после ребута недоступен — включать
  через TUI или `scripts/adam_start.sh`. Тумблер в логвьюере (:8083) — возможное продолжение.

## Files

- `System/adam/autostart.py` — ядро (status / set_enabled / can_manage)
- `System/Orchestrator.py` — `GET/POST /api/system/autostart`, событие `autostart_changed`
- `System/Config.json`, `System/Config.schema.json` — `system.autostart`
- `scripts/adam_autostart.py` — curses TUI + `--status/--on/--off`
- `scripts/adam_install_systemd.sh` — sudoers, сохранение состояния, reenable логвьюера
- `deploy/systemd/adam-logviewer.service`, `deploy/systemd/adam-exhibition.target`
- `System/WebUI/static/js/panels/settings.js`, `System/WebUI/static/css/components.css` — карточка с тумблером

## Verify on Jetson

1. `sudo scripts/adam_install_systemd.sh` → `scripts/adam_autostart.py --status` без предупреждения о правах
2. Веб → Настройки → выключить → `--status` = ВЫКЛЮЧЕН, `docker inspect` policy = `no`
3. `sudo reboot` → Адам не поднялся, :8083 живой; TUI → включить → reboot → всё поднялось, target active
