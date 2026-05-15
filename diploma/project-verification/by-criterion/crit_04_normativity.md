# Criterion 4 — Режим нормативности

## Theoretical Definition

Из раздела 2.1.4: источник правил действия. Четыре типа: внешняя → ограниченно-внутренняя → гибридная → внутренняя.

## Implementation Status: **FULL** (ограниченно-внутренняя)

Adam Chip — **ограниченно-внутренняя нормативность**: правила заданы извне (Config.json, action whitelist, persona), но система адаптирует поведение в пределах рамок.

## Graphify Evidence

| Node | File | Role |
|---|---|---|
| `ActionLayer` | System/adam/action.py | Whitelist scenes + safety constraints |
| `EchoGate` | System/adam/echoes_gate.py | Правила фильтрации реплик |
| `LeadingNoiseFilter` | System/adam/prompt.py | Правила чистки контекста |
| Salience scoring | System/adam/episodic.py | Правила приоритизации памяти |
| `safety` block | Config.json | motor_max_duration_ms, cooldown, half_duplex_mute |

## Verification Trace

1. `Config.json` → `mcu.allowed_scenes: ["boot_idle", "all_on", "alternating"]` — whitelist.
2. `Config.json` → `safety`: motor constraints явно заданы.
3. `Config.schema.json` → safety documented: `half_duplex_mute: MUST remain true`.
4. `action.py` (ActionLayer) — валидация против whitelist; reject не-whitelisted команд.
5. `echoes_gate.py` (EchoGate, 15 edges) — правила выбора реплик из пула.
6. `prompt.py` (LeadingNoiseFilter) — правила очистки текста.
7. `episodic.py` — salience rules для отбора что писать в долговременную память.

## Findings

**Соответствует «ограниченно-внутренней нормативности» (таблица 6):**

- ✅ Action whitelist (внешние правила)
- ✅ Safety constraints (внешние ограничения)
- ✅ EchoGate (внутренняя стратегия в пределах рамок)
- ✅ Salience scoring (внутренняя приоритизация)
- ✅ LLM не пишет команды, только теги — жёсткая нормативная редукция
- ❌ Не «гибридная» — нет случаев пересмотра ограничений изнутри
- ❌ Не «внутренняя» — система не вырабатывает свои правила

## Связь с главой 3

- **Раздел 3.2.6** (командный контур) — описывает редукцию: LLM теги → Commander → whitelisted command.
- **Раздел 3.3.3** (программирование МК) — описывает «ограниченный словарь сигналов».
- **Метрика 3.4.2** (нормативная устойчивость) — операционализирует.

## Recommendations for Chapter 3

В разделе 3.2.6 явно показать как нормативная редукция: длинный LLM-ответ → краткий тег `[грусть]` → конкретный motor scene → ESP32 pattern. Это yields жёсткую нормативную предсказуемость при сохранении вербальной вариативности.
