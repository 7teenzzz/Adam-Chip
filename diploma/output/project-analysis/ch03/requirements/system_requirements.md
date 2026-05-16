<!--
GENERATED: 2026-05-16T17:35:06Z
STAGE: 1
SOURCE: diploma/Diploma.md (Chapter 3)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# System Requirements вЂ” С‡С‚Рѕ РѕР±СЏР·Р°РЅРѕ СЃСѓС‰РµСЃС‚РІРѕРІР°С‚СЊ РІ РєРѕРґРµ

РўСЂРµР±РѕРІР°РЅРёСЏ, РІС‹РІРѕРґРёРјС‹Рµ РёР· РіР»Р°РІС‹ 3. Р”Р»СЏ РєР°Р¶РґРѕРіРѕ: theoretical basis, expected impl, verification method.

---

## R1: Modular orchestration

- **Requirement.** Р¦РµРЅС‚СЂР°Р»СЊРЅС‹Р№ orchestrator СѓРїСЂР°РІР»СЏРµС‚ РїРѕС‚РѕРєРѕРј СЃРѕР±С‹С‚РёР№.
- **Theoretical basis.** 3.2.1 вЂ” СЃРѕР±С‹С‚РёР№РЅР°СЏ Р°СЂС…РёС‚РµРєС‚СѓСЂР°, РЅРµ Р»РёРЅРµР№РЅС‹Р№ РєРѕРЅРІРµР№РµСЂ.
- **Expected impl.** `System/Orchestrator.py` + asyncio event loop.
- **Verification.** Code graph: god-node Orchestrator СЃ в‰Ґ40 edges.

---

## R2: Hierarchical prompt assembly

- **Requirement.** Р—Р°РїСЂРѕСЃ Рє LLM СЃРѕР±РёСЂР°РµС‚СЃСЏ РёР· 4+1 СЃР»РѕС‘РІ (system + bio + memory + perception + stimulus).
- **Theoretical basis.** 3.2.3 вЂ” РёРµСЂР°СЂС…РёС‡РµСЃРєР°СЏ СЃР±РѕСЂРєР°.
- **Expected impl.** `System/adam/prompt.py` (PromptBuilder).
- **Verification.** Р§С‚РµРЅРёРµ prompt.py: РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РѕС‚РґРµР»СЊРЅС‹Рµ СЃРµРєС†РёРё РґР»СЏ system / persona / history / scene / stimulus.

---

## R3: Multi-layer memory

- **Requirement.** РџР°РјСЏС‚СЊ РёРјРµРµС‚ в‰Ґ3 СѓСЂРѕРІРЅСЏ: working / summaries / permanent.
- **Theoretical basis.** 3.2.4 вЂ” РјРЅРѕРіРѕСѓСЂРѕРІРЅРµРІР°СЏ СЃРёСЃС‚РµРјР° РѕС‚Р±РѕСЂР°.
- **Expected impl.** `System/adam/episodic.py` + `System/adam/memory.py` + РїРµСЂСЃРѕРЅР°-С„Р°Р№Р»С‹.
- **Verification.** SQLite schema + JSONL events + Agent/About/*.md files.

---

## R4: AIIM-style identity configuration

- **Requirement.** РРґРµРЅС‚РёС‡РЅРѕСЃС‚СЊ Р·Р°РґР°С‘С‚СЃСЏ С‡РµСЂРµР· СЃС‚СЂСѓРєС‚СѓСЂРёСЂРѕРІР°РЅРЅСѓСЋ РєРѕРЅС„РёРіСѓСЂР°С†РёСЋ (С„РѕСЂРјСѓР»Сѓ РёР»Рё СЌРєРІРёРІР°Р»РµРЅС‚).
- **Theoretical basis.** 3.1.1 + 3.2.3 вЂ” AIIM formula.
- **Expected impl.** `Agent Adam Chip/Tuning.json` РёР»Рё СЌРєРІРёРІР°Р»РµРЅС‚.
- **Verification.** Р§С‚РµРЅРёРµ Tuning.json: РґРѕР»Р¶РЅС‹ Р±С‹С‚СЊ РїР°СЂР°РјРµС‚СЂС‹ РїРµСЂСЃРѕРЅС‹ (С‚РѕРЅ, РѕРіСЂР°РЅРёС‡РµРЅРёСЏ).

---

## R5: State markers (not commands) from LLM

- **Requirement.** LLM РЅРµ РіРµРЅРµСЂРёСЂСѓРµС‚ С‚РµС…РЅРёС‡РµСЃРєРёРµ РєРѕРјР°РЅРґС‹, С‚РѕР»СЊРєРѕ РєРѕСЂРѕС‚РєРёРµ С‚РµРіРё СЃРѕСЃС‚РѕСЏРЅРёСЏ.
- **Theoretical basis.** 3.2.6 вЂ” separation РєРѕРЅС†РµРїС†РёРё.
- **Expected impl.** `System/adam/action.py` вЂ” РїР°СЂСЃРµСЂ С‚РµРіРѕРІ, action whitelist.
- **Verification.** action.py СЃРѕРґРµСЂР¶РёС‚ РІР°Р»РёРґР°С†РёСЋ, action layer reject Р»СЋР±СѓСЋ non-whitelisted РєРѕРјР°РЅРґСѓ.

---

## R6: VAD + ASR + Wake Word

- **Requirement.** Р РµС‡РµРІРѕР№ РІС…РѕРґ С‡РµСЂРµР· VAD в†’ ASR.
- **Theoretical basis.** 3.2.5 вЂ” РїРµСЂС†РµРїС‚РёРІРЅС‹Р№ РєРѕРЅС‚СѓСЂ.
- **Expected impl.** WebRTC VAD + WhisperX + OpenWakeWord.
- **Verification.** РЎСѓС‰РµСЃС‚РІРѕРІР°РЅРёРµ `webrtc_vad.py`, `ASR_WhisperX.py`, `wake_word.py`.

---

## R7: TTS output + MCU command parallel paths

- **Requirement.** РџРѕСЃР»Рµ LLM РѕС‚РІРµС‚ СЂР°Р·РґРµР»СЏРµС‚СЃСЏ РЅР° РґРІР° РєР°РЅР°Р»Р°.
- **Theoretical basis.** 3.2.6 вЂ” РєРѕРјР°РЅРґРЅС‹Р№ РєРѕРЅС‚СѓСЂ.
- **Expected impl.** `Orchestrator.py` orchestrates: TTS HTTP call + MCUClient HTTP call.
- **Verification.** Р’РѕСЃРїСЂРѕРёР·РІРѕРґРёРјС‹Р№ turn: С‚РµРєСЃС‚ РІ TTS + scene РІ action layer.

---

## R8: Multi-modal MCU (light + sound + vibration)

- **Requirement.** РўРµС…РЅРѕС„Р»РѕСЂР° СѓРїСЂР°РІР»СЏРµС‚СЃСЏ С‡РµСЂРµР· 3 РєР°РЅР°Р»Р°.
- **Theoretical basis.** 3.3.2 вЂ” СЃРІРµС‚РѕС„Р»РѕСЂР° + Р°СѓРґРёРѕС„Р»РѕСЂР° + РІРёР±СЂРѕС„Р»РѕСЂР°.
- **Expected impl.** ESP32 firmware СЃ С‚СЂРµРјСЏ РєРѕРЅС‚СѓСЂР°РјРё.
- **Verification.** `Subsystem/AdamsServer/` СЃРѕРґРµСЂР¶РёС‚ light/sound/vibration handlers.

---

## R9: Proactive mode

- **Requirement.** РЎРёСЃС‚РµРјР° РёРЅРёС†РёРёСЂСѓРµС‚ РґРµР№СЃС‚РІРёСЏ Р±РµР· РІРЅРµС€РЅРµРіРѕ СЃС‚РёРјСѓР»Р°.
- **Theoretical basis.** 3.3.4 вЂ” С‡РµС‚С‹СЂРµ СЂРµР¶РёРјР° РїРѕРІРµРґРµРЅРёСЏ (СЏРІРЅС‹Р№/С„РѕРЅРѕРІС‹Р№/РѕР¶РёРґР°РЅРёРµ/РїСЂРѕР°РєС‚РёРІРЅС‹Р№).
- **Expected impl.** Idle scheduler РІ orchestrator OR background workers.
- **Verification.** Stage 2 вЂ” РїСЂРѕРІРµСЂРёС‚СЊ РЅР°Р»РёС‡РёРµ periodic tasks. **РџРѕРґ РІРѕРїСЂРѕСЃРѕРј.**

---

## R10: Memory continuity across sessions

- **Requirement.** Р”РѕР»РіРѕРІСЂРµРјРµРЅРЅР°СЏ РїР°РјСЏС‚СЊ СЃРѕС…СЂР°РЅСЏРµС‚СЃСЏ РјРµР¶РґСѓ СЃРµСЃСЃРёСЏРјРё.
- **Theoretical basis.** 3.2.4 вЂ” Bio.md + Summarized.json + Notes.json.
- **Expected impl.** SQLite persistence + JSONL + summaries РІ data/adam/.
- **Verification.** `data/adam/memory.sqlite3` exists; consolidator runs.

---

## R11: Metrics tracking (3.4)

- **Requirement.** Р›РѕРіРёСЂРѕРІР°РЅРёРµ СѓРґРµСЂР¶Р°РЅРёСЏ СЂРѕР»Рё, РґР»РёС‚РµР»СЊРЅРѕСЃС‚Рё СЃРµСЃСЃРёРё, Р·Р°РґРµСЂР¶РєРё, etc.
- **Theoretical basis.** 3.4.1 вЂ” РјРµС‚РѕРґРёРєР° Р°РїСЂРѕР±Р°С†РёРё.
- **Expected impl.** `System/adam/metrics.py` + events.jsonl + log viewer.
- **Verification.** РњРµС‚СЂРёРєРё per turn_id РІРёРґРЅС‹ С‡РµСЂРµР· `/api/agent/turns`.

---

## R12: Safety constraints

- **Requirement.** Motor max duration, cooldown, half-duplex mute.
- **Theoretical basis.** 3.3.3 вЂ” РїСЂРѕРіСЂР°РјРјРёСЂРѕРІР°РЅРёРµ РњРљ (whitelisted scenes).
- **Expected impl.** `System/adam/action.py` + Config.json `safety` block.
- **Verification.** Config.schema.json СЃРѕРґРµСЂР¶РёС‚ safety РїР°СЂР°РјРµС‚СЂС‹, action.py РёС… РёСЃРїРѕР»СЊР·СѓРµС‚.

---

## R13: Power gate (Jetson exhibition mode)

- **Requirement.** Exhibition mode С‚СЂРµР±СѓРµС‚ MAXN + jetson_clocks.
- **Theoretical basis.** 3.2.2 вЂ” РїСЂРѕРіСЂР°РјРјРЅС‹Р№ СЃС‚РµРє (Jetson, СЂРµСЃСѓСЂСЃРѕС‘РјРєРѕСЃС‚СЊ).
- **Expected impl.** `System/adam/power.py`.
- **Verification.** Power gate РїСЂРѕРІРµСЂСЏРµС‚СЃСЏ РІ Orchestrator startup.

