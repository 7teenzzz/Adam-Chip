<!--
GENERATED: 2026-05-16T17:35:06Z
STAGE: 1
SOURCE: diploma/Diploma.md (Chapter 3)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Runtime Model вЂ” Р“Р»Р°РІС‹ 3.2.1 + 3.3 (РєР°Рє Р·Р°СЏРІР»РµРЅРѕ)

## Event Loop (РѕРґРЅР° РёС‚РµСЂР°С†РёСЏ)

```text
1. PERCEPTION
   - VAD detects speech segment
   - ASR transcribes to text
   - Camera + VLM produce scene description (conditional)
   - Sensor state updated

2. ORCHESTRATOR DECISION
   - Event significant? в†’ full cycle
   - Event minor? в†’ background update only

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
   - Marker в†’ MCU packet via Communication.py

6. EXECUTION
   - TTS audio out (HDMI)
   - MCU receives packet в†’ light/sound/vibration

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

1. **Boot.** Р—Р°РіСЂСѓР·РєР° AIIM РєРѕРЅС„РёРіСѓСЂР°С†РёРё в†’ СЃРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚.
2. **Service start.** llama.cpp, VLM (РєРѕРЅС‚РµР№РЅРµСЂ), TTS, ASR РІ РѕС‚РґРµР»СЊРЅС‹С… СЃРµСЂРІРёСЃР°С….
3. **MCU handshake.** Connection check, idle scene СѓСЃС‚Р°РЅРѕРІРєР°.
4. **Power gate (exhibition mode).** Verify MAXN + jetson_clocks.
5. **Ready.** Voice loop Р°РєС‚РёРІРµРЅ, РѕР¶РёРґР°РµС‚ wake word РёР»Рё РІРЅСѓС‚СЂРµРЅРЅРµРіРѕ С‚СЂРёРіРіРµСЂР°.

---

## Timing Constraints (Р·Р°СЏРІР»РµРЅРѕ)

- **LLM inference:** ~65 tok/s (Cosmos Reasoning 2 2B Р·Р°СЏРІР»РµРЅРѕ)
- **VLM:** РєРѕСЂРѕС‚РєРѕРµ РѕРїРёСЃР°РЅРёРµ СЃС†РµРЅС‹, РѕС‚РґРµР»СЊРЅС‹Р№ РєРѕРЅС‚РµР№РЅРµСЂ
- **TTS:** РЅРµ РґРѕР»Р¶РЅРѕ СЃРѕР·РґР°РІР°С‚СЊ РґРѕР»РіРѕРіРѕ РѕР¶РёРґР°РЅРёСЏ
- **Cycle as unified time process:** ASR + prompt build + generation + TTS РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ СЃРѕРіР»Р°СЃРѕРІР°РЅС‹

---

## Proactive vs Reactive Modes

| Р РµР¶РёРј | Trigger | Behavior |
|---|---|---|
| Reactive | Wake word + speech | Full cycle: ASR в†’ LLM в†’ TTS + MCU |
| Proactive | Idle timeout, scene change, internal state | Skip ASR; LLM may generate spontaneous reply OR MCU-only fallback |
| Background | Always | Periodic VLM scene update, memory consolidation |
| Standby | After cycle | Wait for trigger |

