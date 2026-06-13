# Phase 36 — Audio Pipeline Restoration

**Branch:** `audio-pipeline-restoration` (diverged from `main @ 37830af`)
**Status:** done — root cause найден и устранён (смена USB-порта), voice-loop подтверждён, находка перенесена на SmartFlora (Phase 41)
**Created:** 2026-06-13

## Цель фазы

Восстановить аудиотракт захвата микрофона (WebCamera USB / INMP441 via Philips32)
до модулей OWW/VAD/ASR на максимальном качестве и со стабильным потоком —
непрерывные 16kHz/20ms фреймы на каденсе ~12.5Hz (`oww_score` должен регулярно
обновляться, не застывать на ~0.001).

## Почему отдельная ветка от main, не продолжение Phase 41 (SmartFlora)

Phase 41 (ветка SmartFlora) диагностировала проблему через архитектуру
`LocalMicReader` (`System/adam/local_mic_reader.py`) — модуль, добавленный ПОСЛЕ
расхождения SmartFlora от main. На `main@37830af` этого модуля нет: захват идёт
через `VoiceLoopController._run_local` + `_start_arecord` (`System/Orchestrator.py`),
архитектурно проще (прямой subprocess `arecord`, без отдельного ридер-класса).

Пользователь определил `main@37830af` как точку "стабильной работы аудио" и
попросил восстанавливать аудиотракт именно от неё, а не продолжать
SmartFlora-ветку.

## Перенесённые из Phase 41 диагностические находки

См. `BRANCH.md` (раздел "Notes for agents") — полная сводка:

1. PipeWire 0.3.48 ALSA SPA для `alsa_card.usb-WebCamera_*` хардкодит
   `node.max-latency=48000/48000` (1с период IO-таймера), не переопределяется
   через WirePlumber `apply_properties`.
2. Текущее (вне-git) состояние системы: WebCamera исключена из PipeWire
   (`device.disabled=true` в `~/.config/wireplumber/main.lua.d/51-webcamera-latency.lua`),
   ALSA-устройство `plughw:0,0`/`hw:0,0` свободно для прямого доступа.
3. **Нерешённая аномалия**: WebCamera отдаёт аудио на ~6-11% от заявленного
   sample rate НЕЗАВИСИМО от метода доступа (PipeWire-pulse, pw-cat, raw ALSA
   48kHz, raw ALSA 16kHz). USB Packet Size=104 bytes, full-speed. Подозрение —
   деградированная USB-энумерация (связано с прошлым инцидентом bus1-port2,
   решённым `sudo reboot`).
4. Старый BRANCH.md этой ветки (от merge-коммита `ultimate-integration`, Phase 35)
   явно фиксирует: `input_device = "pulse" (PipeWire, Phase 32) — НЕ менять на plughw`.
   Это исходный intended-state архитектуры main — на нём и нужно проверять
   "максимальное качество и стабильный поток" сначала.

## Инварианты для этой фазы

- Sample rate 16kHz сохраняется (ASR ceiling) — см. CLAUDE.md.
- ESP32 mic/camera НЕ используются (физически недоступны) — только локальный
  USB-микрофон WebCamera.
- Любые правки `Config.json` на этой ветке (`input_device`, `mic_source`) —
  Global change, координация с SmartFlora перед мёржем (см. BRANCH.md).

## Следующий шаг

**ВЫПОЛНЕНО (2026-06-13) и ПОДТВЕРЖДЕНО — аномалия #3 это и есть корневая причина.**

Минимальный тест `arecord -D pulse -f S16_LE -r <rate> -c 1 -t raw` (Python,
неблокирующее чтение, 3с) воспроизвёл аномалию #3 на 16kHz, 16kHz с
`PULSE_LATENCY_MSEC=20`, и на нативных 48kHz (без ресемплинга) — во всех трёх
случаях ровно ~125мс аудио прибывает раз в ~1.15-1.19с (~8-11% от номинала).
Это происходит ПОВЕРХ уже применённого Attempt 3 (WirePlumber period-size
override, `node.max-latency` 48000/48000→384/48000) — т.е. п.1 (max-latency)
был реальной, но ВТОРИЧНОЙ проблемой; истинное бутылочное горлышко лежит ниже
PipeWire/Pulse — на уровне USB-аудио устройства WebCamera (hardware/firmware).
Подробности и таблица измерений — `BRANCH.md` п.7.

**РЕШЕНО (2026-06-13 18:14):** пользователь переподключил кабель WebCamera в
другой физический USB-порт. Устройство переэнумерировалось как High-Speed
(480M) вместо Full-Speed (12M) — `/proc/asound/card0/stream0` теперь
показывает `high speed`, `Data packet interval: 1000 us`. Throughput
8.3% → 91.7-95.8%. Живой каденс `oww_score` 12.64 Hz (было ~1.1Hz пачками) —
практически точное совпадение с целью ~12.5Hz. `score=0.001` у всех событий —
ожидаемо (тишина, "адам" не произносилось). Подробности — `BRANCH.md` п.9.

**Корневая причина (эмпирически, на сегодня):** USB-порт `1-2.2` негоциировал
Full-Speed вместо High-Speed для устройства WebCamera — физическое
ограничение шины, не ОС/PipeWire/код. Никакой software-фикс (пп.1, 7, 8) не
мог это решить. Смена на порт `1-2.4` → High-Speed → throughput восстановлен.

**ОГОВОРКА:** пользователь сообщил, что ранее уже пробовал менять порт без
эффекта — kernel-журнал не хранит историю дальше текущего boot, сравнить с
теми попытками нельзя. Функциональный результат (12.64Hz, voice-loop работает)
подтверждён живьём и не зависит от точного механизма; но "любой High-Speed
порт = гарантированный фикс" — неподтверждённая теория. При регрессии:
`cat /proc/asound/card0/stream0` → если `full speed`, пробовать другой порт.
Подробности — `BRANCH.md` п.9.

**ЗАКРЫТО (2026-06-13):** пользователь подтвердил полный цикл wake→listen→reply
на живом железе — вторая часть merge condition выполнена. Оба условия фазы
выполнены, ветка готова к мёржу в `main`.

**Кросс-референс SmartFlora (Phase 41):** их `local_mic_reader.py` диагностировал
тот же `node.max-latency=48000/48000`, но застрял на 3.5Hz — узкое место было
тем же USB Full-Speed дефектом (п.9 BRANCH.md), решённым физической сменой порта.
Прямая проверка их точного `_start_process()` на текущем железе дала 95.2%
throughput / 128мс каденс — идентично этой ветке. Phase 41 разблокирована без
изменений кода. Подробности и итоговый вывод — `BRANCH.md` п.10,
`41-03-SUMMARY.md` на ветке SmartFlora.
