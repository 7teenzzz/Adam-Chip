# System Requirements — что обязано существовать в коде

Требования, выводимые из главы 3. Для каждого: theoretical basis, expected impl, verification method.

---

## R1: Modular orchestration

- **Requirement.** Центральный orchestrator управляет потоком событий.
- **Theoretical basis.** 3.2.1 — событийная архитектура, не линейный конвейер.
- **Expected impl.** `System/Orchestrator.py` + asyncio event loop.
- **Verification.** Code graph: god-node Orchestrator с ≥40 edges.

---

## R2: Hierarchical prompt assembly

- **Requirement.** Запрос к LLM собирается из 4+1 слоёв (system + bio + memory + perception + stimulus).
- **Theoretical basis.** 3.2.3 — иерархическая сборка.
- **Expected impl.** `System/adam/prompt.py` (PromptBuilder).
- **Verification.** Чтение prompt.py: должны быть отдельные секции для system / persona / history / scene / stimulus.

---

## R3: Multi-layer memory

- **Requirement.** Память имеет ≥3 уровня: working / summaries / permanent.
- **Theoretical basis.** 3.2.4 — многоуровневая система отбора.
- **Expected impl.** `System/adam/episodic.py` + `System/adam/memory.py` + персона-файлы.
- **Verification.** SQLite schema + JSONL events + Agent/About/*.md files.

---

## R4: AIIM-style identity configuration

- **Requirement.** Идентичность задаётся через структурированную конфигурацию (формулу или эквивалент).
- **Theoretical basis.** 3.1.1 + 3.2.3 — AIIM formula.
- **Expected impl.** `Agent Adam Chip/Tuning.json` или эквивалент.
- **Verification.** Чтение Tuning.json: должны быть параметры персоны (тон, ограничения).

---

## R5: State markers (not commands) from LLM

- **Requirement.** LLM не генерирует технические команды, только короткие теги состояния.
- **Theoretical basis.** 3.2.6 — separation концепции.
- **Expected impl.** `System/adam/action.py` — парсер тегов, action whitelist.
- **Verification.** action.py содержит валидацию, action layer reject любую non-whitelisted команду.

---

## R6: VAD + ASR + Wake Word

- **Requirement.** Речевой вход через VAD → ASR.
- **Theoretical basis.** 3.2.5 — перцептивный контур.
- **Expected impl.** WebRTC VAD + WhisperX + OpenWakeWord.
- **Verification.** Существование `webrtc_vad.py`, `ASR_WhisperX.py`, `wake_word.py`.

---

## R7: TTS output + MCU command parallel paths

- **Requirement.** После LLM ответ разделяется на два канала.
- **Theoretical basis.** 3.2.6 — командный контур.
- **Expected impl.** `Orchestrator.py` orchestrates: TTS HTTP call + MCUClient HTTP call.
- **Verification.** Воспроизводимый turn: текст в TTS + scene в action layer.

---

## R8: Multi-modal MCU (light + sound + vibration)

- **Requirement.** Технофлора управляется через 3 канала.
- **Theoretical basis.** 3.3.2 — светофлора + аудиофлора + виброфлора.
- **Expected impl.** ESP32 firmware с тремя контурами.
- **Verification.** `Subsystem/AdamsServer/` содержит light/sound/vibration handlers.

---

## R9: Proactive mode

- **Requirement.** Система инициирует действия без внешнего стимула.
- **Theoretical basis.** 3.3.4 — четыре режима поведения (явный/фоновый/ожидание/проактивный).
- **Expected impl.** Idle scheduler в orchestrator OR background workers.
- **Verification.** Stage 2 — проверить наличие periodic tasks. **Под вопросом.**

---

## R10: Memory continuity across sessions

- **Requirement.** Долговременная память сохраняется между сессиями.
- **Theoretical basis.** 3.2.4 — Bio.md + Summarized.json + Notes.json.
- **Expected impl.** SQLite persistence + JSONL + summaries в data/adam/.
- **Verification.** `data/adam/memory.sqlite3` exists; consolidator runs.

---

## R11: Metrics tracking (3.4)

- **Requirement.** Логирование удержания роли, длительности сессии, задержки, etc.
- **Theoretical basis.** 3.4.1 — методика апробации.
- **Expected impl.** `System/adam/metrics.py` + events.jsonl + log viewer.
- **Verification.** Метрики per turn_id видны через `/api/agent/turns`.

---

## R12: Safety constraints

- **Requirement.** Motor max duration, cooldown, half-duplex mute.
- **Theoretical basis.** 3.3.3 — программирование МК (whitelisted scenes).
- **Expected impl.** `System/adam/action.py` + Config.json `safety` block.
- **Verification.** Config.schema.json содержит safety параметры, action.py их использует.

---

## R13: Power gate (Jetson exhibition mode)

- **Requirement.** Exhibition mode требует MAXN + jetson_clocks.
- **Theoretical basis.** 3.2.2 — программный стек (Jetson, ресурсоёмкость).
- **Expected impl.** `System/adam/power.py`.
- **Verification.** Power gate проверяется в Orchestrator startup.
