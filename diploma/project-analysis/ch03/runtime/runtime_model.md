# Runtime Model — Главы 3.2.1 + 3.3 (как заявлено)

## Event Loop (одна итерация)

```text
1. PERCEPTION
   - VAD detects speech segment
   - ASR transcribes to text
   - Camera + VLM produce scene description (conditional)
   - Sensor state updated

2. ORCHESTRATOR DECISION
   - Event significant? → full cycle
   - Event minor? → background update only

3. CONTEXT ASSEMBLY (PromtBuilder)
   - System prompt (AIIM)
   - Bio.md persona
   - Working history (recent N turns)
   - Summarized.json (if relevant)
   - Notes.json (if relevant)
   - State memory
   - Scene description
   - User utterance

4. LLM INFERENCE (llama.cpp)
   - Single unified response: text + [state markers]

5. POSTPROCESSING (Commander)
   - Split text vs markers
   - TTS synthesis for text
   - Marker → MCU packet via Communication.py

6. EXECUTION
   - TTS audio out (HDMI)
   - MCU receives packet → light/sound/vibration

7. MEMORY UPDATE
   - Append to working history
   - Compute state delta
   - (Conditional) summarize, add note

8. STANDBY / BACKGROUND
   - Wait for new event OR
   - Background scan (proactive mode)
```

---

## Lifecycle Phases (initialization)

1. **Boot.** Загрузка AIIM конфигурации → системный промпт.
2. **Service start.** llama.cpp, VLM (контейнер), TTS, ASR в отдельных сервисах.
3. **MCU handshake.** Connection check, idle scene установка.
4. **Power gate (exhibition mode).** Verify MAXN + jetson_clocks.
5. **Ready.** Voice loop активен, ожидает wake word или внутреннего триггера.

---

## Timing Constraints (заявлено)

- **LLM inference:** ~65 tok/s (Cosmos Reasoning 2 2B заявлено)
- **VLM:** короткое описание сцены, отдельный контейнер
- **TTS:** не должно создавать долгого ожидания
- **Cycle as unified time process:** ASR + prompt build + generation + TTS должны быть согласованы

---

## Proactive vs Reactive Modes

| Режим | Trigger | Behavior |
|---|---|---|
| Reactive | Wake word + speech | Full cycle: ASR → LLM → TTS + MCU |
| Proactive | Idle timeout, scene change, internal state | Skip ASR; LLM may generate spontaneous reply OR MCU-only fallback |
| Background | Always | Periodic VLM scene update, memory consolidation |
| Standby | After cycle | Wait for trigger |
