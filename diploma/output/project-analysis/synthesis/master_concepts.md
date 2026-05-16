<!--
GENERATED: 2026-05-16T17:35:06Z
STAGE: 1
SOURCE: diploma/Diploma.md (synthesis)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Master Concepts вЂ” Diploma Architecture Registry

Р”РµРґСѓРїР»РёС†РёСЂРѕРІР°РЅРЅС‹Р№ СЂРµРµСЃС‚СЂ РєРѕРЅС†РµРїС‚РѕРІ РёР· РіР»Р°РІ 1вЂ“3 РґРёРїР»РѕРјР°, СЃ РїСЂРёРІСЏР·РєРѕР№ Рє РєРѕРґСѓ System/.

---

## Concept: QuasiSubjectivity
- **chapters:** [1.1.5, 2.1, 3.1, 3.4]
- **definition:** Р”РѕСЃС‚Р°С‚РѕС‡РЅС‹Рµ СѓСЃР»РѕРІРёСЏ РґР»СЏ СЃСѓР±СЉРµРєС‚РѕРїРѕРґРѕР±РЅРѕРіРѕ СЂРµР¶РёРјР° РїРѕРІРµРґРµРЅРёСЏ Р±РµР· РїРѕР»РЅРѕРіРѕ СЃРѕР·РЅР°РЅРёСЏ. Р­С„С„РµРєС‚ СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚Рё + РІРєР»СЋС‡С‘РЅРЅРѕСЃС‚Рё + РЅР°СЂСЂР°С‚РёРІРЅРѕР№ СЃРІСЏР·РЅРѕСЃС‚Рё + РЅРѕСЂРјР°С‚РёРІРЅРѕР№ РѕСЂРіР°РЅРёР·Р°С†РёРё + РІРѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚Рё.
- **theoretical_role:** РРЅР¶РµРЅРµСЂРЅР°СЏ РїР»Р°РЅРєР° СЃСѓР±СЉРµРєС‚РѕРїРѕРґРѕР±РЅРѕРіРѕ СЂРµР¶РёРјР°. Backbone РІРµСЂРёС„РёРєР°С†РёРё.
- **code_correspondence:** Р­С„С„РµРєС‚ РІСЃРµР№ СЃРёСЃС‚РµРјС‹ (composite); РЅРµ РѕРґРёРЅ СѓР·РµР».
- **evidence_file:** РІСЃРµ РєР»СЋС‡РµРІС‹Рµ РјРѕРґСѓР»Рё System/adam/
- **tension:** Р’ РґРёРїР»РѕРјРµ вЂ” РіСѓРјР°РЅРёС‚Р°СЂРЅС‹Р№ РєРѕРЅС†РµРїС‚; РІ РєРѕРґРµ вЂ” operational target Р±РµР· СЏРІРЅРѕР№ РјРµС‚СЂРёРєРё.

---

## Concept: NarrativeIdentity
- **chapters:** [1.1.2, 1.1.5, 2.1.3]
- **definition:** РРґРµРЅС‚РёС‡РЅРѕСЃС‚СЊ С‡РµСЂРµР· СЃРІСЏР·РЅРѕСЃС‚СЊ РёСЃС‚РѕСЂРёРё РІРѕ РІСЂРµРјРµРЅРё (Р РёРєС‘СЂ, ipse). РџРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ РїР°РјСЏС‚СЊСЋ Рё РїРѕРІС‚РѕСЂРµРЅРёРµРј.
- **theoretical_role:** РСЃС‚РѕС‡РЅРёРє СѓСЃС‚РѕР№С‡РёРІРѕСЃС‚Рё РїРѕРІРµРґРµРЅРёСЏ.
- **code_correspondence:** `EpisodicMemory` + `SessionAccumulator` + persona files
- **evidence_file:** System/adam/memory.py, System/adam/episodic.py, Agent Adam Chip/About/*.md

---

## Concept: PerformativeIdentity
- **chapters:** [1.1.2, 2.1.3]
- **definition:** РРґРµРЅС‚РёС‡РЅРѕСЃС‚СЊ РєР°Рє СЂРµР¶РёРј РёСЃРїРѕР»РЅРµРЅРёСЏ (Р“РѕС„С„РјР°РЅ, Р‘Р°С‚Р»РµСЂ). РџРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ РїРѕРІС‚РѕСЂСЏРµРјРѕСЃС‚СЊСЋ Р°РєС‚РѕРІ.
- **theoretical_role:** Anti-drift С‡РµСЂРµР· РїРѕРІС‚РѕСЂСЏСЋС‰РёРµСЃСЏ РїР°С‚С‚РµСЂРЅС‹.
- **code_correspondence:** `TuningStore` + `PromptBuilder` + СЃРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚
- **evidence_file:** System/adam/tuning.py, System/adam/prompt.py

---

## Concept: CognitiveLoop
- **chapters:** [1.2.2, 3.2.1, 3.3.4]
- **definition:** Cycle perception в†’ memory в†’ planning в†’ action в†’ reflection в†’ update.
- **theoretical_role:** Runtime backbone Р°РіРµРЅС‚Р°.
- **code_correspondence:** `VoiceLoopController` (42 edges)
- **evidence_file:** System/Orchestrator.py

---

## Concept: EpisodicMemory (РєРѕРЅС†РµРїС‚)
- **chapters:** [1.2.3, 3.2.4]
- **definition:** РџР°РјСЏС‚СЊ РѕС‚РґРµР»СЊРЅС‹С… СЌРїРёР·РѕРґРѕРІ (turn'РѕРІ, СЃРѕР±С‹С‚РёР№). Salience-based retrieval.
- **theoretical_role:** РўРµРјРїРѕСЂР°Р»СЊРЅР°СЏ СЃРІСЏР·РЅРѕСЃС‚СЊ.
- **code_correspondence:** `EpisodicMemory` (29 edges)
- **evidence_file:** System/adam/memory.py + System/adam/episodic.py

---

## Concept: AIIM_Framework
- **chapters:** [3.1.1, 3.2.3]
- **definition:** Artificially Integrated Identity Matrix (Р’РµСЂРµСЃРѕРІР°). 12 Р°СЃРїРµРєС‚РѕРІ Г— 5 РїР»РѕСЃРєРѕСЃС‚РµР№ Г— 4 СѓСЂРѕРІРЅСЏ Р·СЂРµР»РѕСЃС‚Рё. Р¤РѕСЂРјСѓР»Р° `[Р°СЃРїРµРєС‚](РїР»РѕСЃРєРѕСЃС‚СЊ СѓСЂРѕРІРµРЅСЊ СЃРѕСЃС‚РѕСЏРЅРёРµ)О”РїСЂРёРѕСЂРёС‚РµС‚`.
- **theoretical_role:** Р¤РѕСЂРјР°Р»РёР·Р°С†РёСЏ РєРѕРЅС„РёРіСѓСЂР°С†РёРё РёРґРµРЅС‚РёС‡РЅРѕСЃС‚Рё.
- **code_correspondence:** `TuningStore` + persona files (РєРѕСЃРІРµРЅРЅРѕ вЂ” AIIM-С„РѕСЂРјСѓР»Р° РЅРµ СЂРµР°Р»РёР·РѕРІР°РЅР° Р±СѓРєРІР°Р»СЊРЅРѕ, РЅРѕ РµС‘ СЂРѕР»СЊ РІС‹РїРѕР»РЅСЏРµС‚ Tuning.json + РїРµСЂСЃРѕРЅР°)
- **evidence_file:** Agent Adam Chip/Tuning.json + persona graph (graphify-out-persona/)
- **tension:** Р”РёРїР»РѕРј РѕРїРёСЃС‹РІР°РµС‚ AIIM-С„РѕСЂРјСѓР»Сѓ СЏРІРЅРѕ, РєРѕРґ СЂРµР°Р»РёР·СѓРµС‚ С„СѓРЅРєС†РёРѕРЅР°Р»СЊРЅРѕ-СЌРєРІРёРІР°Р»РµРЅС‚РЅСѓСЋ РєРѕРЅС„РёРіСѓСЂР°С†РёСЋ Р±РµР· Р±СѓРєРІР°Р»СЊРЅРѕРіРѕ СЃРёРЅС‚Р°РєСЃРёСЃР° С„РѕСЂРјСѓР»С‹.

---

## Concept: PromptAssembly (PromtBuilder)
- **chapters:** [3.2.3]
- **definition:** РРµСЂР°СЂС…РёС‡РµСЃРєР°СЏ СЃР±РѕСЂРєР° Р·Р°РїСЂРѕСЃР° Рє LLM РёР· 4+1 СЃР»РѕС‘РІ: system + persona + memory + perception + stimulus.
- **theoretical_role:** Balance РјРµР¶РґСѓ context richness Рё latency.
- **code_correspondence:** `PromptBuilder` (in prompt.py)
- **evidence_file:** System/adam/prompt.py

---

## Concept: ActionLayer (Commander)
- **chapters:** [3.2.6]
- **definition:** РџРѕСЃС‚РїСЂРѕС†РµСЃСЃРёРЅРі LLM-РѕС‚РІРµС‚Р°: РёР·РІР»РµС‡РµРЅРёРµ state markers ([СЂР°РґРѕСЃС‚СЊ], [РіСЂСѓСЃС‚СЊ]), РІР°Р»РёРґР°С†РёСЏ РїСЂРѕС‚РёРІ whitelist, РїРµСЂРµРІРѕРґ РІ РєРѕРјР°РЅРґС‹ РњРљ.
- **theoretical_role:** Р–С‘СЃС‚РєР°СЏ СЂРµРґСѓРєС†РёСЏ РјРµР¶РґСѓ СЏР·С‹РєРѕРІС‹Рј СѓСЂРѕРІРЅРµРј Рё С„РёР·РёС‡РµСЃРєРёРј РёСЃРїРѕР»РЅРµРЅРёРµРј.
- **code_correspondence:** `ActionLayer` (in action.py) + `MCUClient` (device.py)
- **evidence_file:** System/adam/action.py, System/adam/device.py

---

## Concept: Embodiment / Technoflora
- **chapters:** [3.1.2, 3.3.2]
- **definition:** Р Р°СЃРїСЂРµРґРµР»С‘РЅРЅРѕРµ С‚РµР»Рѕ Р°РіРµРЅС‚Р°: СЃРІРµС‚РѕС„Р»РѕСЂР° + Р°СѓРґРёРѕС„Р»РѕСЂР° + РІРёР±СЂРѕС„Р»РѕСЂР°.
- **theoretical_role:** Р’РѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚СЊ РєР°Рє РєСЂРёС‚РµСЂРёР№ РєРІР°Р·РёСЃСѓР±СЉРµРєС‚РЅРѕСЃС‚Рё.
- **code_correspondence:** `MCUClient` (25) + ESP32 firmware + TTS playback
- **evidence_file:** System/adam/device.py + Subsystem/AdamsServer/

---

## Concept: SceneWorker (VLM)
- **chapters:** [3.2.2, 3.2.5]
- **definition:** Р‘С‹СЃС‚СЂР°СЏ РІРёР·СѓР°Р»СЊРЅР°СЏ СЂР°Р·РІРµРґРєР° С‡РµСЂРµР· VLM (VILA1.5-3B). РЈСЃР»РѕРІРЅС‹Р№ РІС‹Р·РѕРІ.
- **theoretical_role:** Р’РёР·СѓР°Р»СЊРЅС‹Р№ perception channel.
- **code_correspondence:** `SceneWorker` (30 edges) + `CameraReader` (23)
- **evidence_file:** System/Orchestrator.py + System/adam/camera.py + System/adam/inference.py

---

## Concept: WakeWord + VAD
- **chapters:** [3.2.5]
- **definition:** РўСЂРёРіРіРµСЂ Р°РєС‚РёРІР°С†РёРё РіРѕР»РѕСЃРѕРІРѕРіРѕ РєРѕРЅС‚СѓСЂР°. VAD РѕС‚СЃРµРєР°РµС‚ С€СѓРј.
- **theoretical_role:** Р“СЂР°РЅРёС†Р° СЃРѕР±С‹С‚РёСЏ (perception в†’ cognition).
- **code_correspondence:** OpenWakeWord ONNX + WebRTC VAD
- **evidence_file:** System/adam/wake_word.py (?) + System/adam/webrtc_vad.py

---

## Concept: ProactiveMode
- **chapters:** [3.1.2, 3.3.4]
- **definition:** РЎРёСЃС‚РµРјР° РёРЅРёС†РёРёСЂСѓРµС‚ РґРµР№СЃС‚РІРёСЏ Р±РµР· РІРЅРµС€РЅРµРіРѕ СЃС‚РёРјСѓР»Р°. РЎРЅРёРјР°РµС‚ С‡РёСЃС‚Рѕ СЂРµР°РєС‚РёРІРЅСѓСЋ РїСЂРёСЂРѕРґСѓ.
- **theoretical_role:** РЈСЂРѕРІРµРЅСЊ Р°РІС‚РѕРЅРѕРјРёР·Р°С†РёРё (crit 1).
- **code_correspondence:** `SessionWatcher` (30) + background workers
- **evidence_file:** System/Orchestrator.py
- **tension:** Р”РёРїР»РѕРј РѕРїРёСЃС‹РІР°РµС‚ proactive mode СЂР°Р·РІС‘СЂРЅСѓС‚Рѕ (4 СЂРµР¶РёРјР° РїРѕРІРµРґРµРЅРёСЏ); РєРѕРґ РёРјРµРµС‚ SessionWatcher Рё SceneWorker, РЅРѕ В«СЃРїРѕРЅС‚Р°РЅРЅС‹Рµ СЂРµРїР»РёРєРё Р±РµР· С‚СЂРёРіРіРµСЂР°В» РїРѕРґ РІРѕРїСЂРѕСЃРѕРј.

---

## Concept: AntiDrift / EchoGate
- **chapters:** [2.1.3, 3.2.3, 3.4.2]
- **definition:** РњРµС…Р°РЅРёР·РјС‹ СѓРґРµСЂР¶Р°РЅРёСЏ СЂРѕР»Рё: С„РёР»СЊС‚СЂР°С†РёСЏ РїРѕРІС‚РѕСЂРѕРІ, РЅРѕСЂРјР°С‚РёРІРЅС‹Рµ РѕРіСЂР°РЅРёС‡РµРЅРёСЏ.
- **theoretical_role:** РЈСЃС‚РѕР№С‡РёРІРѕСЃС‚СЊ РёРґРµРЅС‚РёС‡РЅРѕСЃС‚Рё (crit 3).
- **code_correspondence:** `EchoGate` (15) + `LeadingNoiseFilter`
- **evidence_file:** System/adam/echoes_gate.py + System/adam/prompt.py

---

## Concept: PowerGate
- **chapters:** [3.2.2, 3.3.1]
- **definition:** Hardware constraint: exhibition mode С‚СЂРµР±СѓРµС‚ MAXN + jetson_clocks.
- **theoretical_role:** РњР°С‚РµСЂРёР°Р»СЊРЅР°СЏ РІРѕРїР»РѕС‰С‘РЅРЅРѕСЃС‚СЊ (РҐРµР№Р»Р·) вЂ” hardware shapes behavior.
- **code_correspondence:** `power.py`
- **evidence_file:** System/adam/power.py
- **tension:** Р’ РґРёРїР»РѕРјРµ СЏРІРЅРѕ РЅРµ СѓРїРѕРјРёРЅР°РµС‚СЃСЏ; emerges РёР· РёРЅР¶РµРЅРµСЂРЅРѕР№ РїСЂР°РєС‚РёРєРё.

---

## Concept: MetricsAndEvents
- **chapters:** [3.4.1, 3.4.2вЂ“3.4.5]
- **definition:** Р›РѕРіРёСЂРѕРІР°РЅРёРµ СѓРґРµСЂР¶Р°РЅРёСЏ СЂРѕР»Рё, РґР»РёС‚РµР»СЊРЅРѕСЃС‚Рё, Р·Р°РґРµСЂР¶РєРё, РёРЅС‚РµСЂР°РєС†РёРѕРЅРЅРѕСЃС‚Рё.
- **theoretical_role:** Р­РјРїРёСЂРёС‡РµСЃРєР°СЏ Р±Р°Р·Р° РґР»СЏ РѕС†РµРЅРєРё РєРІР°Р·РёСЃСѓР±СЉРµРєС‚РЅРѕСЃС‚Рё.
- **code_correspondence:** `metrics.py` + `EventLog` (13) + JSONL + `/api/agent/turns`
- **evidence_file:** System/adam/metrics.py, System/adam/events.py

