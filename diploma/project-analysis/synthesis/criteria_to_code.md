<!--
GENERATED: 2026-05-16T17:35:06Z
STAGE: 1
SOURCE: graphify-out/ (code graph analysis)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# 8 Criteria в†’ Code Mapping

РњР°РїРїРёРЅРі 8 РєСЂРёС‚РµСЂРёРµРІ РєРІР°Р·РёСЃСѓР±СЉРµРєС‚РЅРѕСЃС‚Рё (СЂР°Р·РґРµР» 2.1) РЅР° РєРѕРЅРєСЂРµС‚РЅС‹Рµ СѓР·Р»С‹ РєРѕРґРѕРІРѕРіРѕ РіСЂР°С„Р°.

---

## Crit 1: РЎС‚РµРїРµРЅСЊ Р°РІС‚РѕРЅРѕРјРёР·Р°С†РёРё

- **code_nodes:** `VoiceLoopController`, `SessionWatcher`, `SceneWorker`, `EspAudioHealthMonitor`
- **evidence_files:** System/Orchestrator.py, System/adam/inference.py
- **coverage_estimate:** PARTIAL
- **reasoning:** Р•СЃС‚СЊ voice loop + scene worker + session watcher (background tasks), РЅРѕ РїСЂРѕР°РєС‚РёРІРЅР°СЏ РёРЅРёС†РёР°С†РёСЏ СЂРµРїР»РёРє Р±РµР· РІРЅРµС€РЅРµРіРѕ С‚СЂРёРіРіРµСЂР° РЅРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅР°. Cycle РІСЃС‘ РµС‰С‘ РёРЅРёС†РёРёСЂСѓРµС‚СЃСЏ wake word РёР»Рё С‚Р°Р№РјРµСЂРѕРј.

---

## Crit 2: РўРёРї Р°РіРµРЅС‚РЅРѕСЃС‚Рё

- **code_nodes:** `Orchestrator`, `VoiceLoopController`, `ActionLayer`, `PromptBuilder`, `EpisodicMemory`, `MCUClient`
- **evidence_files:** System/Orchestrator.py, System/adam/*.py, Subsystem/AdamsServer/
- **coverage_estimate:** FULL
- **reasoning:** РђСЂС…РёС‚РµРєС‚СѓСЂР° РјРѕРґСѓР»СЊРЅР°СЏ: РµРґРёРЅС‹Р№ orchestrator + СЂР°СЃРїСЂРµРґРµР»С‘РЅРЅР°СЏ РёРЅС„СЂР°СЃС‚СЂСѓРєС‚СѓСЂР° (memory, persona, tools). РЎРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ С‚РёРїСѓ В«РјРѕРґСѓР»СЊРЅР°СЏ Р°РіРµРЅС‚РЅРѕСЃС‚СЊВ» РёР· С‚Р°Р±Р»РёС†С‹ 4.

---

## Crit 3: РЈСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ РёРґРµРЅС‚РёС‡РЅРѕСЃС‚Рё

- **code_nodes:** `TuningStore`, `PromptBuilder`, `EchoGate`, persona graph
- **evidence_files:** System/adam/tuning.py, System/adam/prompt.py, System/adam/echoes_gate.py, Agent Adam Chip/About/
- **coverage_estimate:** FULL
- **reasoning:** РќРµСЃРєРѕР»СЊРєРѕ СѓСЂРѕРІРЅРµР№ СѓРґРµСЂР¶Р°РЅРёСЏ СЂРѕР»Рё: СЃРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚ + РїРµСЂСЃРѕРЅР°-С„Р°Р№Р»С‹ (Identity, Lore, Abilities) + TuningStore (hot-reload РїР°СЂР°РјРµС‚СЂРѕРІ) + EchoGate (anti-repeat). AIIM-С„РѕСЂРјСѓР»Р° Р±СѓРєРІР°Р»СЊРЅРѕ РЅРµ СЂРµР°Р»РёР·РѕРІР°РЅР°, РЅРѕ С„СѓРЅРєС†РёРѕРЅР°Р»СЊРЅР°СЏ СЌРєРІРёРІР°Р»РµРЅС‚РЅРѕСЃС‚СЊ С‡РµСЂРµР· Tuning.json.

---

## Crit 4: Р РµР¶РёРј РЅРѕСЂРјР°С‚РёРІРЅРѕСЃС‚Рё

- **code_nodes:** `ActionLayer`, `EchoGate`, `LeadingNoiseFilter`, salience rules РІ `episodic.py`
- **evidence_files:** System/adam/action.py, System/adam/echoes_gate.py, System/adam/prompt.py, System/adam/episodic.py
- **coverage_estimate:** FULL
- **reasoning:** РќРѕСЂРјР°С‚РёРІРЅРѕСЃС‚СЊ С‡РµСЂРµР· action whitelist (`allowed_scenes`), safety constraints (motor_max_duration_ms, cooldown, half_duplex_mute), echo gate (С„РёР»СЊС‚СЂР°С†РёСЏ РїРѕРІС‚РѕСЂРѕРІ), salience scoring (РїСЂР°РІРёР»Р° РїСЂРёРѕСЂРёС‚РёР·Р°С†РёРё РїР°РјСЏС‚Рё). РЎРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ В«РѕРіСЂР°РЅРёС‡РµРЅРЅРѕ-РІРЅСѓС‚СЂРµРЅРЅРёР№В» С‚РёРї РЅРѕСЂРјР°С‚РёРІРЅРѕСЃС‚Рё.

---

## Crit 5: РўРµРјРїРѕСЂР°Р»СЊРЅР°СЏ СЃРІСЏР·РЅРѕСЃС‚СЊ

- **code_nodes:** `EpisodicMemory`, `SessionAccumulator`, `MemoryStore`, `consolidator.py`
- **evidence_files:** System/adam/episodic.py, System/adam/memory.py, Engineering/consolidator.py
- **coverage_estimate:** FULL
- **reasoning:** РњРЅРѕРіРѕСѓСЂРѕРІРЅРµРІР°СЏ РїР°РјСЏС‚СЊ: working history + episodic SQLite + JSONL events + persona files + daily consolidation. РџРѕРґРґРµСЂР¶РёРІР°РµС‚ СѓСЂРѕРІРЅРё В«РЅР°СЂСЂР°С‚РёРІРЅР°СЏ СЃРІСЏР·РЅРѕСЃС‚СЊВ» Рё СЃС‚СЂРµРјРёС‚СЃСЏ Рє В«РїСЂРѕС†РµСЃСЃСѓР°Р»СЊРЅР°СЏ СЃРІСЏР·РЅРѕСЃС‚СЊВ».

---

## Crit 6: РРЅС‚РµСЂР°РєС†РёРѕРЅРЅРѕСЃС‚СЊ

- **code_nodes:** `VoiceLoopController`, wake word engine, WebRTC VAD, `EspAudioHealthMonitor`
- **evidence_files:** System/Orchestrator.py, System/adam/webrtc_vad.py, System/adam/wake_word.py
- **coverage_estimate:** PARTIAL
- **reasoning:** Р”РёР°Р»РѕРіРѕРІРѕРµ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёРµ СЂРµР°Р»РёР·РѕРІР°РЅРѕ (turn-based СЃ РєРѕРЅС‚РµРєСЃС‚РѕРј). РљРѕРѕРїРµСЂР°С‚РёРІРЅРѕРµ/РєРѕРѕСЂРґРёРЅР°С†РёРѕРЅРЅРѕРµ вЂ” РЅРµС‚ (single-agent). Half-duplex muting Р·Р°С‰РёС‰Р°РµС‚ РѕС‚ echo feedback. Filler phrases СЃРЅРёР¶Р°СЋС‚ perceived latency.

---

## Crit 7: Р’РѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚СЊ

- **code_nodes:** `MCUClient`, `ActionLayer`, `CameraReader`, `SceneWorker`, TTS playback (ALSA HDMI)
- **evidence_files:** System/adam/device.py, System/adam/action.py, System/adam/camera.py, Subsystem/AdamsServer/
- **coverage_estimate:** FULL
- **reasoning:** Р¤РёР·РёС‡РµСЃРєРёР№ СѓСЂРѕРІРµРЅСЊ РІРѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚Рё (С‚Р°Р±Р»РёС†Р° 9): РєР°РјРµСЂР° + Р°СѓРґРёРѕ РІС…РѕРґ + TTS РІС‹РІРѕРґ + ESP32 motor layer + СЃРµРЅСЃРѕСЂС‹. РЎРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ В«С„РёР·РёС‡РµСЃРєР°СЏВ» РІРѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚СЊ.

---

## Crit 8: РЈСЂРѕРІРµРЅСЊ СЌРјРµСЂРґР¶РµРЅС‚РЅРѕСЃС‚Рё

- **code_nodes:** Cross-community connections (47 communities РІ graphify) + Event bus
- **evidence_files:** graphify-out/GRAPH_REPORT.md, System/adam/events.py
- **coverage_estimate:** PARTIAL
- **reasoning:** Р›РѕРєР°Р»СЊРЅС‹Р№ СѓСЂРѕРІРµРЅСЊ вЂ” РѕС‚С‡С‘С‚Р»РёРІРѕ (РєР°Р¶РґС‹Р№ РјРѕРґСѓР»СЊ РѕРїСЂРµРґРµР»СЏРµС‚ СЃРІРѕС‘ РїРѕРІРµРґРµРЅРёРµ). РРЅС‚РµСЂР°РєС†РёРѕРЅРЅС‹Р№ вЂ” РµСЃС‚СЊ (LLM + memory + scene + tuning composition). РЎРёСЃС‚РµРјРЅС‹Р№ вЂ” С‡Р°СЃС‚РёС‡РЅРѕ (event bus, async coordination). Р­РјРµСЂРґР¶РµРЅС‚РЅС‹Рµ СЌС„С„РµРєС‚С‹ (РЅР°РїСЂРёРјРµСЂ, В«РіРѕР»РѕСЃ СЃС‚Р°РЅРѕРІРёС‚СЃСЏ С‚РёС€Рµ РїСЂРё РѕС‚СЃСѓС‚СЃС‚РІРёРё Р·СЂРёС‚РµР»СЏВ») Р·Р°РІРёСЃСЏС‚ РѕС‚ РјРЅРѕР¶РµСЃС‚РІР° РјРѕРґСѓР»РµР№.

