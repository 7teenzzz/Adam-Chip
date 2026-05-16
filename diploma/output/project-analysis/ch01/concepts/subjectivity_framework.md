<!--
GENERATED: 2026-05-16T17:35:06Z
STAGE: 1
SOURCE: diploma/Diploma.md (Chapter 1)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Subjectivity Framework вЂ” РљРѕРЅС†РµРїС‚С‹ РіР»Р°РІС‹ 1

РР·РІР»РµС‡РµРЅРёРµ РёР· РіР»Р°РІС‹ 1: С„РёР»РѕСЃРѕС„СЃРєРёРµ Рё С‚РµС…РЅРѕР»РѕРіРёС‡РµСЃРєРёРµ РѕСЃРЅРѕРІР°РЅРёСЏ С†РёС„СЂРѕРІРѕР№ СЃСѓР±СЉРµРєС‚РЅРѕСЃС‚Рё.

---

## РљРѕРЅС†РµРїС‚С‹ РѕС‚ РґРµРєРѕРЅСЃС‚СЂСѓРєС†РёРё (1.1.2)

### IntentionalConsciousness (Husserl)
- **Theoretical origin.** В«Р’СЃСЏРєРѕРµ СЃРѕР·РЅР°РЅРёРµ РµСЃС‚СЊ СЃРѕР·РЅР°РЅРёРµ Рѕ С‡С‘Рј-С‚РѕВ» вЂ” Р“СѓСЃСЃРµСЂР»СЊ, 1913.
- **Computational interpretation.** РљРѕРЅС‚РµРєСЃС‚ РЅРµ РїСѓСЃС‚ вЂ” РєР°Р¶РґРѕРµ РІРЅСѓС‚СЂРµРЅРЅРµРµ СЃРѕСЃС‚РѕСЏРЅРёРµ Р°РіРµРЅС‚Р° РЅР°РїСЂР°РІР»РµРЅРѕ РЅР° РѕР±СЉРµРєС‚ (turn, СЃС†РµРЅСѓ, РїР°РјСЏС‚СЊ).
- **Runtime implication.** Prompt РІСЃРµРіРґР° СЃРѕРґРµСЂР¶РёС‚ scene + history + persona, РЅРµ РіРѕР»СѓСЋ РёРЅСЃС‚СЂСѓРєС†РёСЋ.
- **Architectural requirement.** РљРѕРЅС‚РµРєСЃС‚РЅР°СЏ СЃР±РѕСЂРєР° С‡РµСЂРµР· PromptBuilder.

### PerformativeIdentity (Goffman, Butler)
- **Theoretical origin.** РРґРµРЅС‚РёС‡РЅРѕСЃС‚СЊ вЂ” СЂРµР¶РёРј РёСЃРїРѕР»РЅРµРЅРёСЏ, РїРѕРґРґРµСЂР¶РёРІР°РµРјС‹Р№ РїРѕРІС‚РѕСЂРµРЅРёРµРј.
- **Computational interpretation.** Identity РЅРµ fixed entity, Р° pattern РїРѕРІРµРґРµРЅС‡РµСЃРєРёС… Р°РєС‚РѕРІ.
- **Runtime implication.** РљР°Р¶РґС‹Р№ turn вЂ” performative act, СѓРґРµСЂР¶РёРІР°РµРјС‹Р№ РїРµСЂСЃРѕРЅР°-С„Р°Р№Р»Р°РјРё + СЃРёСЃС‚РµРјРЅС‹Рј РїСЂРѕРјРїС‚РѕРј.
- **Architectural requirement.** Anti-drift mechanisms (echo gate, leading noise filter).

### Dispositif (Foucault)
- **Theoretical origin.** Р”РёСЃРєСѓСЂСЃ/РІР»Р°СЃС‚СЊ С„РѕСЂРјРёСЂСѓРµС‚ СЃСѓР±СЉРµРєС‚Р° С‡РµСЂРµР· РЅРѕСЂРјР°С‚РёРІРЅС‹Рµ РїСЂР°РєС‚РёРєРё.
- **Computational interpretation.** РЎРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚ + action whitelist + safety constraints С„РѕСЂРјРёСЂСѓСЋС‚ РїРѕРІРµРґРµРЅС‡РµСЃРєРёР№ СЂРµР¶РёРј.
- **Runtime implication.** Limit space РґРµР№СЃС‚РІРёСЏ РѕРїСЂРµРґРµР»С‘РЅ РєРѕРЅС„РёРіСѓСЂР°С†РёРµР№.
- **Architectural requirement.** Action layer РєР°Рє nominee РЅРѕСЂРјР°С‚РёРІРЅРѕР№ СЂР°РјРєРё.

### NarrativeIdentity (Ricoeur)
- **Theoretical origin.** РЎР°РјРѕСЃС‚СЊ (ipse) СѓРґРµСЂР¶РёРІР°РµС‚СЃСЏ С‡РµСЂРµР· СЃРІСЏР·РЅРѕСЃС‚СЊ РёСЃС‚РѕСЂРёРё, РЅРµ С‡РµСЂРµР· СЃСѓР±СЃС‚Р°РЅС†РёСЋ (idem).
- **Computational interpretation.** РРґРµРЅС‚РёС‡РЅРѕСЃС‚СЊ РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ РїР°РјСЏС‚СЊСЋ + РёСЃС‚РѕСЂРёРµР№ turn'РѕРІ.
- **Runtime implication.** Р‘РµР· РїР°РјСЏС‚Рё Р°РіРµРЅС‚ С‚РµСЂСЏРµС‚ СЃРµР±СЏ РјРµР¶РґСѓ СЃРµСЃСЃРёСЏРјРё.
- **Architectural requirement.** Episodic memory + session accumulator + long-term summaries.

---

## РљРѕРЅС†РµРїС‚С‹ РѕС‚ РїРѕСЃС‚РіСѓРјР°РЅРёР·РјР° (1.1.4)

### DistributedAgency (Latour)
- **Theoretical origin.** Р”РµР№СЃС‚РІРёРµ СЂР°СЃРїСЂРµРґРµР»РµРЅРѕ РїРѕ СЃРµС‚Рё Р°РєС‚РѕСЂРѕРІ, РЅРµ Р»РѕРєР°Р»РёР·РѕРІР°РЅРѕ РІ РѕРґРЅРѕР№ С‚РѕС‡РєРµ.
- **Computational interpretation.** Behavior вЂ” СЌС„С„РµРєС‚ РєРѕРѕСЂРґРёРЅР°С†РёРё orchestrator + memory + tools + persona + perception.
- **Runtime implication.** Single-agent СЃРёСЃС‚РµРјР° РјРѕР¶РµС‚ Р±С‹С‚СЊ Р°РєС‚РѕСЂ-СЃРµС‚СЊСЋ РІРЅСѓС‚СЂРё СЃРµР±СЏ.
- **Architectural requirement.** Event bus + multiple modules + observable coordination.

### EmbodiedCognition (Clark, Chalmers)
- **Theoretical origin.** РљРѕРіРЅРёС‚РёРІРЅС‹Рµ РїСЂРѕС†РµСЃСЃС‹ СЂР°СЃРїСЂРµРґРµР»РµРЅС‹ РїРѕ РІРЅРµС€РЅРёРј РєРѕРјРїРѕРЅРµРЅС‚Р°Рј (extended mind).
- **Computational interpretation.** РџР°РјСЏС‚СЊ РЅР° РґРёСЃРєРµ = СЂР°СЃС€РёСЂРµРЅРёРµ В«РјС‹С€Р»РµРЅРёСЏВ» Р°РіРµРЅС‚Р°.
- **Runtime implication.** Cognition outside the LLM (SQLite memory, JSONL events).
- **Architectural requirement.** External memory layer, persistent storage.

### MaterialityOfInformation (Hayles)
- **Theoretical origin.** РРЅС„РѕСЂРјР°С†РёСЏ РІСЃРµРіРґР° РІРѕРїР»РѕС‰РµРЅР° РІ РјР°С‚РµСЂРёР°Р»СЊРЅРѕРј РЅРѕСЃРёС‚РµР»Рµ.
- **Computational interpretation.** РРЅСЃС‚Р°Р»Р»СЏС†РёСЏ = РёРЅС„РѕСЂРјР°С†РёСЏ + С„РёР·РёС‡РµСЃРєРёР№ РЅРѕСЃРёС‚РµР»СЊ (Jetson + ESP32 + РјРѕС‚РѕСЂС‹).
- **Runtime implication.** РџРѕРІРµРґРµРЅРёРµ Р·Р°РІРёСЃРёС‚ РѕС‚ hardware constraints (power, latency, audio devices).
- **Architectural requirement.** Hardware-aware orchestrator (power gate, device detection).

---

## РљРІР°Р·РёСЃСѓР±СЉРµРєС‚РЅРѕСЃС‚СЊ (1.1.5)

### Quasisubjectivity
- **Definition.** Р”РѕСЃС‚Р°С‚РѕС‡РЅС‹Рµ СѓСЃР»РѕРІРёСЏ РґР»СЏ СЃСѓР±СЉРµРєС‚РѕРїРѕРґРѕР±РЅРѕРіРѕ РїРѕРІРµРґРµРЅРёСЏ Р±РµР· РїРѕР»РЅРѕРіРѕ СЃРѕР·РЅР°РЅРёСЏ.
- **Operationalization.** Р­С„С„РµРєС‚ СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚Рё + РІРєР»СЋС‡С‘РЅРЅРѕСЃС‚Рё + РЅР°СЂСЂР°С‚РёРІРЅРѕР№ СЃРІСЏР·РЅРѕСЃС‚Рё + РЅРѕСЂРјР°С‚РёРІРЅРѕР№ РѕСЂРіР°РЅРёР·Р°С†РёРё + РІРѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚Рё.
- **Engineering target.** РќРµ СЃРѕР·РЅР°РЅРёРµ, Р° РёРЅР¶РµРЅРµСЂРЅР°СЏ РїР»Р°РЅРєР° СЃСѓР±СЉРµРєС‚РѕРїРѕРґРѕР±РЅРѕРіРѕ СЂРµР¶РёРјР°.

---

## РўРµС…РЅРёС‡РµСЃРєРёРµ РїР°СЂР°РґРёРіРјС‹ (1.2)

### TransformerCore (1.2.1)
- **Role.** Р‘Р°Р·РѕРІС‹Р№ СЏР·С‹РєРѕРІРѕР№ РјРѕРґСѓР»СЊ (LLM).
- **Implementation.** Gemma-4-E4B (llama.cpp) РІ Adam Chip.

### CognitiveLoop (1.2.2)
- **Role.** Cycle perception в†’ memory в†’ planning в†’ action в†’ reflection в†’ update.
- **Implementation.** VoiceLoopController РІ Orchestrator.py.

### CompositionalArchitecture (1.2.3)
- **Role.** РђРіРµРЅС‚ СЃРѕР±СЂР°РЅ РёР· РЅРµСЃРєРѕР»СЊРєРёС… Р»РѕРіРёРє: model + memory + tools + reflection + affective layer.
- **Implementation.** System/adam/ РјРѕРґСѓР»Рё (inference, memory, action, tuning, prompt, echoes_gate).

### AgentIdentityBehavior (1.2.4)
- **Role.** РРґРµРЅС‚РёС‡РЅРѕСЃС‚СЊ С‡РµСЂРµР· СЃРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚ + РїР°РјСЏС‚Рё + РѕРіСЂР°РЅРёС‡РµРЅРёСЏ.
- **Implementation.** Persona files + TuningStore + PromptBuilder.

### MultiAgentSystems (1.2.5)
- **Role.** Р Р°СЃРїСЂРµРґРµР»С‘РЅРЅР°СЏ РєРѕРѕСЂРґРёРЅР°С†РёСЏ.
- **Adam Chip status.** Single-agent (РЅРѕ СЃ РјРѕРґСѓР»СЊРЅРѕР№ composition).

---

## 8 cognitive cycle stages (1.2.2)

РР· ch01:

1. **Р’РѕСЃРїСЂРёСЏС‚РёРµ** вЂ” input acquisition.
2. **РђС„С„РµРєС‚РёРІРЅР°СЏ** РѕС†РµРЅРєР° вЂ” emotional/salience weighting.
3. **РР·РІР»РµС‡РµРЅРёРµ** РїР°РјСЏС‚Рё вЂ” retrieval.
4. **РРЅС‚РµСЂРїСЂРµС‚Р°С†РёСЏ** вЂ” semantic parsing.
5. **РџР»Р°РЅРёСЂРѕРІР°РЅРёРµ** вЂ” action selection.
6. **Р”РµР№СЃС‚РІРёРµ** вЂ” motor/speech execution.
7. **Р РµС„Р»РµРєСЃРёСЏ** вЂ” post-action evaluation.
8. **РћР±РЅРѕРІР»РµРЅРёРµ** вЂ” memory write + state update.

**РњР°РїРїРёРЅРі РЅР° Adam Chip:**
| Stage | Adam Chip РєРѕРјРїРѕРЅРµРЅС‚ |
|---|---|
| Р’РѕСЃРїСЂРёСЏС‚РёРµ | CameraReader + WhisperX ASR + WebRTC VAD |
| РђС„С„РµРєС‚РёРІРЅР°СЏ | (РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РєР°Рє РѕС‚РґРµР»СЊРЅС‹Р№ РјРѕРґСѓР»СЊ вЂ” embedded РІ LLM) |
| РР·РІР»РµС‡РµРЅРёРµ | EpisodicMemory.retrieve() + recent turns |
| РРЅС‚РµСЂРїСЂРµС‚Р°С†РёСЏ | LLM (prefill РІ Gemma) |
| РџР»Р°РЅРёСЂРѕРІР°РЅРёРµ | LLM (РіРµРЅРµСЂР°С†РёСЏ РѕС‚РІРµС‚Р° + action) |
| Р”РµР№СЃС‚РІРёРµ | TTS + MCUClient + ActionLayer |
| Р РµС„Р»РµРєСЃРёСЏ | (С‡Р°СЃС‚РёС‡РЅРѕ вЂ” С‡РµСЂРµР· consolidator) |
| РћР±РЅРѕРІР»РµРЅРёРµ | EpisodicMemory.append() + JSONL event log |

