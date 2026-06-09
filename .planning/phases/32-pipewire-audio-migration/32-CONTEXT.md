# Phase 32: PipeWire Audio Migration - Context

**Gathered:** 2026-06-08
**Status:** STUB — decisions deferred (обсудить перед планированием)

<domain>
## Phase Boundary

Перевести аудио-подсистему Jetson с PulseAudio на PipeWire (`pipewire-pulse` + `wireplumber`), чтобы получить нормальное системное распределение звука между агентом, AnyDesk и GNOME без костылей `PULSE_SOURCE`-pin и кооперативных хаков. Текущее состояние (Phase 30): кооперативный pulse-захват (`arecord -D pulse`, pinned source) — работает, но это «вариант C, шаг 1». Свап на PipeWire — «шаг 2», сознательно отложенный до стабилизации голосового цикла.

**Out of scope (предв.):** переделка входной DSP-панели (Phase 31 спроектирована независимой от звукового сервера — DSP в Python); смена устройств; ESP-аудио.

</domain>

<decisions>
## Implementation Decisions

**ОТЛОЖЕНО — обсудить перед /gsd-plan-phase 32.**

Предварительные направления (из обсуждения Phase 30, НЕ финал):
- apt `pipewire-pulse` + `wireplumber`, mask `pulseaudio`, re-login сессии
- проверить, что `pipewire-pulse` чтит те же env-переменные (`PULSE_SERVER`, `PULSE_SOURCE`) — оркестратор и `adam_audio_input_gain.sh` используют `pactl`/pulse-совместимый слой
- риск: AnyDesk/GNOME аудио-маршрутизация после свапа; нужен план отката
- durable mic gain (Phase 30) должен продолжить работать (`pactl set-source-volume` под pipewire-pulse)

### Open questions для обсуждения
- Делать свап ДО или ПОСЛЕ Phase 31 (панель)? (Phase 31 не зависит от звукового сервера, так что порядок гибкий.)
- Нужен ли откат-план/снапшот перед миграцией на живом выставочном Jetson?

</decisions>

<canonical_refs>
- `deploy/systemd/adam-orchestrator.service` — env `PULSE_SERVER`/`PULSE_SOURCE`, ExecStartPre pulse
- `scripts/adam_audio_input_gain.sh` — `pactl` source volume (должен пережить свап)
- `System/Config.json` `media.audio.input_device=pulse` — точка, которую может затронуть миграция
- Phase 30 `30-CONTEXT.md` — контекст «вариант C», почему pulse-кооператив был шагом 1
</canonical_refs>
