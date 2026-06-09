---
phase: 35
name: ultimate-integration
status: planned
branch: ultimate-integration
base: vlr-main-integrated
created: 2026-06-09
---

# Phase 35 — Ultimate Integration

## Цель

Слить четыре параллельные ветки разработки в одну интеграционную ветку `ultimate-integration`, которая станет кандидатом для мёржа в `main`.

## Базовая ветка

`vlr-main-integrated` (коммит `43b7f2f`) — уже содержит:
- Флора (Phase 29-30, main)
- Голосовой пайплайн Phase 30-31 (barge-in, InputDSP, singleton lock, _read_exact)
- Phase 34: четырёхслойный ASR-фильтр галлюцинаций

## Вливаемые ветки (в порядке выполнения)

| Волна | Ветка | Коммитов | Ключевое содержание |
|-------|-------|----------|---------------------|
| 1 | `LuxFlora-modes_V1.2` | 1 | Ремап каналов железа (вибро 0-3 / свет 4-14) |
| 2 | `origin/MemoryFixes` | 5 | Фикс Echoes/Chinese gate + тесты памяти |
| 3 | `origin/Extra` | 3 | Skills: шутки + погода (pre-LLM провайдеры) |

## Решения по конфликтам (зафиксировано в обсуждении 2026-06-09)

| Параметр | Берём | Обоснование |
|----------|-------|-------------|
| `input_device` | `pulse` (vlr) | PipeWire Phase 32, системный стандарт |
| `scene_worker_enabled` | `false` (vlr) | VILA контейнер не запущен по умолчанию |
| `light_channels` / `vibro_channels` | LuxFlora (4-14 / 0-3) | Реальная физическая разводка железа |
| `AdamsConfig.h` channel constants | LuxFlora | Прошивка должна соответствовать Config.json |
| `kFloraVibroIntensityCeiling` | LuxFlora (3890 ≈ 95%) | Вибро без потолка света, по требованию |
| `silence_rms_threshold` | LuxFlora (2100) | Откалибровано на выставочном зале |
| Поля VLR которых нет в LuxFlora | Оставить (vlr) | `pre_wake_buffer_ms`, `silence_keywords`, `asr_pre_send_min_rms` |
| `echoes_gate.py` | MemoryFixes | Критический баг: gate никогда не срабатывал |
| `skills.py`, `prompt.py` weather_ctx | Extra | Новая функциональность, не конфликтует с VLR |
