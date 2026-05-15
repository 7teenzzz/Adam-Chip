# REVIEW CHECKPOINT: Theory ↔ Implementation

**Статус:** ⬛ pending review · ⬜ partial · ⬜ approved

**Инструкция:** проставь ✓/✗ в колонке `Верно?` для каждой строки. Добавь комментарии в случае ✗. После того как все строки получили отметку и нет открытых ✗ — Stage 3 (writing) можно запускать.

---

## Section A: 8 критериев квазисубъектности

| Crit | Концепт | Статус Stage 2 | Graphify evidence | Верно? | Комментарий |
|---|---|---|---|---|---|
| 1 | Степень автономизации | PARTIAL | VoiceLoopController (42), SessionWatcher (30), SceneWorker (30) / Orchestrator.py | ⬜ | proactive speech отсутствует |
| 2 | Тип агентности | FULL (модульная) | Orchestrator.py (85), 25+ адресных модулей | ⬜ | |
| 3 | Устойчивость идентичности | FULL (динамическая) | TuningStore (17), PromptBuilder, EchoGate (15), persona files | ⬜ | AIIM-формула буквально не реализована, но functional eq |
| 4 | Режим нормативности | FULL (ограниченно-внутренняя) | ActionLayer, EchoGate, salience rules / action.py | ⬜ | |
| 5 | Темпоральная связность | FULL (нарративная) | EpisodicMemory (29), SessionAccumulator (23), consolidator.py / memory.py | ⬜ | |
| 6 | Интеракционность | PARTIAL (диалоговое) | VoiceLoopController (42), WakeWordEngine / wake_word.py | ⬜ | кооперативный/координационный отсутствуют |
| 7 | Воплощённость | FULL (физическая) | MCUClient (25), CameraReader (23), TTS+ALSA / device.py | ⬜ | |
| 8 | Уровень эмерджентности | PARTIAL | EventLog (13), 47 communities / events.py | ⬜ | системный уровень частично |

## Section B: Архитектурные модули (из главы 3)

| Концепт | Раздел 3 | Статус | Graphify evidence | Верно? | Комментарий |
|---|---|---|---|---|---|
| Общая архитектура приложения | 3.2.1 | FULL | Orchestrator.py (85) | ⬜ | |
| Программный стек | 3.2.2 | PARTIAL | Config.json | ⬜ | LLM = Gemma 4 E4B (не Cosmos из диплома) |
| Системный промпт и идентичность | 3.2.3 | FULL | PromptBuilder, TuningStore | ⬜ | AIIM как Tuning.json |
| Память и контекст | 3.2.4 | FULL | EpisodicMemory + SessionAccumulator + persona | ⬜ | |
| Перцептивный/речевой контуры | 3.2.5 | FULL | WhisperASR, TTSClient, VAD, WakeWord | ⬜ | |
| Командный контур | 3.2.6 | FULL | ActionLayer + MCUClient | ⬜ | Commander.py → action.py |
| Техническая реализация инсталляции | 3.3.1 | FULL | Subsystem/AdamsServer/, Config.json | ⬜ | |
| Перцептивный/моторный слои | 3.3.2 | FULL | MCUClient, CameraReader | ⬜ | |
| Программирование МК | 3.3.3 | FULL | Subsystem/AdamsServer/ | ⬜ | |

## Section C: Open Tensions

Расхождения между теоретическим текстом диплома и реальной кодовой базой:

- [ ] **tension #1:** LLM модель — диплом заявляет «Cosmos Reasoning 2 2B», production использует `gemma-4-E4B-it-UD-Q4_K_XL`. → Решение: обновить раздел 3.2.2.
- [ ] **tension #2:** AIIM-формула — диплом описывает буквальную формулу `wi(B 4 Ac-Or)Δ0.90;...`, код использует Tuning.json. → Решение: описать AIIM как теоретический фундамент, Tuning.json как операционализацию.
- [ ] **tension #3:** Названия модулей — диплом: PromtBuilder.py (опечатка), Commander.py, Communication.py; код: prompt.py, action.py, device.py. → Решение: в главе 3 использовать корректные имена кода.
- [ ] **tension #4:** Proactive speech — диплом описывает спонтанные реплики, код имеет только proactive perception. → Решение: честно описать как ограничение в 3.4.4.
- [ ] **tension #5:** TUI.py — диплом упоминает CLI интерфейс, код имеет полноценный web UI (FastAPI + WebUI/ + Log Viewer на 8083). → Решение: обновить раздел 3.2.2 — упомянуть web UI вместо TUI.
- [ ] **tension #6:** AIIM «рефлексивный уровень» (обучение, изменение уровней зрелости) — НЕ реализован. → Решение: обозначить как направление дальнейшего развития.

## Section D: Готовность к Stage 3

- ⬜ Все строки Section A имеют отметку ✓ (нет ✗)
- ⬜ Все строки Section B имеют отметку ✓ (нет ✗)
- ⬜ Section C: все tension разрешены или явно отнесены к «архитектурным компромиссам» в blueprint
- ⬜ `final_chapter_blueprint.md` обновлён с учётом проверки

**Sign-off:** _дата + имя_ → когда заполнено, можно запускать `03_write_chapter3.md`.

---

## Сводная оценка

| Уровень | Количество |
|---|---|
| FULL | 5 критериев + 7 модулей |
| PARTIAL | 3 критерия (1, 6, 8) + 1 модуль (3.2.2) |
| MISSING | 0 |
| EMERGENT | 4 эффекта (см. crit_08) |
| CONTRADICTIONS | 6 tensions (см. Section C) |

**Общий вердикт:** Архитектура реализует ~85% заявленного. Расхождения концентрируются в (a) выборе LLM модели, (b) представлении AIIM, (c) proactive speech, (d) переименовании модулей. Все расхождения объяснимы инженерными решениями и могут быть честно описаны в Главе 3.
