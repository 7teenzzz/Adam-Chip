---
phase: 29
plan: 01
wave: 0
status: complete
completed_at: 2026-05-18
requirements_satisfied:
  - AUDIO-OUT-01  # Software volume cap опущен до 1.0 на всех трёх уровнях
  - AUDIO-OUT-02  # Стартовый tuning.voice.volume = 0.5
---

# Wave 0 — Pre-flight safety — SUMMARY

## Result

**3/3 tasks ✓. Software volume cap синхронно опущен до 1.0 на всех трёх уровнях. Стартовое значение Config.json = 0.5. Pydantic enforced.**

## Tasks completed

### Task 1 — `System/Config.schema.json`

`tuning.voice.volume.maximum`: `2.0` → `1.0`. Description расширен — теперь упоминает PCM5102A → делитель 1:6 → PAM8403 × 16 gain → 4Ω 1W rating цепочку и почему cap опущен (defense-in-depth с hardware делителем).

Verify (pass):

- `jq '.properties.tuning.properties.voice.properties.volume.maximum'` → `1.0`
- description содержит `PCM5102A`, `PAM8403`, `1W`

### Task 2 — `System/adam/tuning.py:148`

`VoiceTuning.volume`: `Field(1.0, ge=0, le=2.0)` → `Field(0.5, ge=0, le=1.0)`. Default 0.5 — безопасный fallback на случай, если ключ удалён из Config.json. `le=1.0` enforced.

Verify (pass):

- `VoiceTuning().volume` == `0.5`
- `VoiceTuning(volume=1.5)` → `ValidationError` ✓
- `VoiceTuning(volume=1.0)` принят (boundary inclusive)
- `VoiceTuning(volume=0.5)` принят

### Task 3 — `System/Config.json:337`

`tuning.voice.volume`: `1.1` → `0.5`. Никаких других ключей не тронуто (`speaker`, `speed_multiplier` остались).

Verify (pass):

- `jq '.tuning.voice.volume'` → `0.5`
- `Settings.load()` отрабатывает без exceptions
- `VoiceTuning(**voice)` принимает загруженное значение

## Что это нам дало (safety invariant achieved)

Теперь любая попытка установить `tuning.voice.volume > 1.0` падает с ValidationError на трёх уровнях:

1. **UI tuning slider / `/api/tuning` PATCH** — Config.schema.json `maximum: 1.0` блокирует
2. **Прямой edit Config.json + restart** — Pydantic `le=1.0` блокирует на `Settings.load()`, orchestrator не стартует
3. **Hot-reload Config.json runtime** — Pydantic снова блокирует, hot-reload отклоняет невалидное значение

Если оператор перезапустит orchestrator во время Wave 1 пайки (потенциально с уже-подключёнными динамиками и подачей 5V) — Адам **физически не сможет** выкрутить громкость в опасную зону. Динамики 1W в безопасности.

## Note про текущее состояние

Сейчас на HDMI target (`output_target = "jetson_hdmi"`) Адам будет звучать **тише обычного** — `volume = 0.5` вместо привычных 1.1. Это ожидаемая pre-flight цена. Wave 3 (target flip + ramp) восстановит комфортный уровень после переключения на ESP-динамики.

## Next

Wave 1 (`29-02-PLAN.md`) — физическая сборка hardware (делитель 1:6 + PAM8403 + динамики + BTL pre-power omметр test). Это работа оператора **вне Claude Code**.
