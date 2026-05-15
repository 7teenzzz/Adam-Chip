# Final Chapter 3 Blueprint

Каркас третьей главы для Stage 3 (writing).

## Структура

| # | Раздел | Источник материала | Статус |
|---|---|---|---|
| 3.1.1 | Концептуальная основа | by-section/3.1_concept.md + ch03/identity/identity_model.md | FULL |
| 3.1.2 | Логика поведения | by-section/3.1_concept.md + crit_01_autonomy.md | PARTIAL |
| 3.1.3 | Функции нейроагента | by-section/3.1_concept.md (5 функций) | FULL |
| 3.2.1 | Общая архитектура | by-section/3.2_application.md + ch03/architecture/system_map.md | FULL |
| 3.2.2 | Программный стек | by-section/3.2_application.md + Config.json | PARTIAL |
| 3.2.3 | Системный промпт | crit_03_identity.md + ch03/identity/identity_model.md | FULL |
| 3.2.4 | Память и контекст | crit_05_temporal.md + ch03/memory/memory_model.md | FULL |
| 3.2.5 | Перцептивный/речевой | crit_06_interaction.md + ch03/interaction/interaction_model.md | FULL |
| 3.2.6 | Командный контур | crit_04_normativity.md + crit_07_embodiment.md | FULL |
| 3.3.1 | Техническая реализация | by-section/3.3_installation.md | FULL |
| 3.3.2 | Перцептивный/моторный слои | crit_07_embodiment.md | FULL |
| 3.3.3 | Программирование МК | by-section/3.3_installation.md | FULL |
| 3.3.4 | Сценарий взаимодействия | crit_06_interaction.md + crit_01_autonomy.md | PARTIAL |
| 3.3.5 | Тестирование инсталляции | by-section/3.3_installation.md + scripts/ | FULL |
| 3.4.1 | Задачи и методика | by-section/3.4_testing.md | FULL |
| 3.4.2 | Метрики удержания роли | crit_03 + crit_04 | FULL |
| 3.4.3 | Метрики памяти/темпоральности | crit_05_temporal.md | FULL |
| 3.4.4 | Метрики интеракционности | crit_01 + crit_06 | PARTIAL |
| 3.4.5 | Интерпретация и ограничения | crit_08_emergence.md + REVIEW_CHECKPOINT.md (Section C) | FULL |

## Архитектурные компромиссы (Section C tensions)

Описать в 3.2.2 + 3.4.5:

1. **LLM swap.** Заявление о Cosmos заменить на Gemma 4 E4B с обоснованием (доступность Q4_K_XL квантизации, ~65 tok/s на Jetson).
2. **AIIM operationalization.** AIIM-формула — теоретический фундамент. Реализация через структурированный JSON (Tuning.json) для удобства hot-reload.
3. **Module naming.** В тексте использовать code-side имена (`prompt.py`, `action.py`, `device.py`), упомянуть упрощённые имена из проектирования как ранние варианты.
4. **Proactive speech absence.** Честно описать в 3.4.4 как inženernый компромисс: cost LLM inference vs benefit спонтанных реплик.
5. **Web UI вместо TUI.** Кратко упомянуть в 3.2.2: вместо CLI собран FastAPI + Web UI + Log Viewer (порт 8083 always-on).
6. **AIIM рефлексивный уровень.** Обозначить в 3.4.5 как направление дальнейшего развития.

## Стилистические напоминания (из 03_write_chapter3.md)

- Пассивный залог, прошедшее время для описания реализации
- Без личных местоимений
- ≥1500 знаков на раздел
- Ссылки на исходники в формате ГОСТ `[N]`
- При первом упоминании термина — определение + источник
- В разделах 3.2–3.4 — обязательные ссылки на конкретные модули кода
