<!--
GENERATED: 2026-05-16T17:35:06Z
STAGE: 1
SOURCE: diploma/graphify-out/ + graphify-out/
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Cross-Graph Map вЂ” Theory в†” Code

РўР°Р±Р»РёС†Р° СЃРѕРѕС‚РІРµС‚СЃС‚РІРёР№: РєРѕРЅС†РµРїС‚ РґРёРїР»РѕРјР° в†’ СѓР·РµР» РєРѕРґРѕРІРѕРіРѕ РіСЂР°С„Р° (`graphify-out/`).

| # | РўРµРѕСЂРёСЏ (РєРѕРЅС†РµРїС‚ РґРёРїР»РѕРјР°) | РљРѕРґ (node) | Source file | Degree | Confidence |
|---|---|---|---|---|---|
| 1 | РљРѕРіРЅРёС‚РёРІРЅС‹Р№ С†РёРєР» | `VoiceLoopController` | System/Orchestrator.py | 42 | HIGH |
| 2 | Р­РїРёР·РѕРґРёС‡РµСЃРєР°СЏ РїР°РјСЏС‚СЊ | `EpisodicMemory` | System/adam/memory.py | 29 | HIGH |
| 3 | РЎРµСЃСЃРёРѕРЅРЅР°СЏ РїР°РјСЏС‚СЊ | `SessionAccumulator` | System/adam/episodic.py | 23 | HIGH |
| 4 | Anti-drift / echo РіРµР№С‚ | `EchoGate` | System/adam/echoes_gate.py | 15 | HIGH |
| 5 | Р”РѕР»РіРѕРІСЂРµРјРµРЅРЅР°СЏ РїР°РјСЏС‚СЊ (Bio.md) | `TuningStore` + persona files | System/adam/tuning.py | 17 | HIGH |
| 6 | РљРѕРјР°РЅРґРЅС‹Р№ РєРѕРЅС‚СѓСЂ (Commander) | `ActionLayer` (action.py) | System/adam/action.py | вЂ” | HIGH |
| 7 | РЎРІСЏР·СЊ СЃ РњРљ (Communication) | `MCUClient` | System/adam/device.py | 25 | HIGH |
| 8 | Р’РёР·СѓР°Р»СЊРЅР°СЏ СЂР°Р·РІРµРґРєР° (VLM) | `SceneWorker` + `VLMClient` | System/Orchestrator.py + System/adam/inference.py | 30 + 14 | HIGH |
| 9 | РљР°РјРµСЂР° | `CameraReader` | System/adam/camera.py | 23 | HIGH |
| 10 | ASR | `WhisperASRClient` | System/adam/inference.py | 15 | HIGH |
| 11 | TTS | `TTSClient` | System/adam/inference.py | 15 | HIGH |
| 12 | РџР°РјСЏС‚СЊ (С…СЂР°РЅРёР»РёС‰Рµ) | `MemoryStore` | System/adam/memory.py | 14 | HIGH |
| 13 | Event bus / JSONL | `EventLog` | System/adam/events.py | 13 | HIGH |
| 14 | Health monitoring (ESP32 mic) | `EspAudioHealthMonitor` | System/Orchestrator.py | 32 | MEDIUM |
| 15 | Session watcher (proactive) | `SessionWatcher` | System/Orchestrator.py | 30 | MEDIUM |
| 16 | РЎРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚ / PromtBuilder | `prompt.py` PromptBuilder | System/adam/prompt.py | вЂ” | HIGH |
| 17 | РњРµС‚СЂРёРєРё (3.4) | `metrics.py` | System/adam/metrics.py | вЂ” | MEDIUM |
| 18 | Power gate (exhibition) | `power.py` | System/adam/power.py | вЂ” | EMERGENT (РЅРµ РІ РґРёРїР»РѕРјРµ СЏРІРЅРѕ) |
| 19 | AIIM РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ | `Tuning.json` + persona graph | Agent Adam Chip/Tuning.json | вЂ” | MEDIUM (functional eq, not formula) |
| 20 | Wake word | wake_word config | System/adam/wake_word.py (?) | вЂ” | MEDIUM |

**РљРѕРЅС„РёРґРµРЅСЃ:**
- HIGH вЂ” СѓР·РµР» СЃСѓС‰РµСЃС‚РІСѓРµС‚, РёРјСЏ СЃРѕРІРїР°РґР°РµС‚ РїРѕ СЃРјС‹СЃР»Сѓ, в‰Ґ10 edges.
- MEDIUM вЂ” СѓР·РµР» СЃСѓС‰РµСЃС‚РІСѓРµС‚, РЅРѕ СЃРІСЏР·СЊ РЅРµ РѕС‡РµРІРёРґРЅР° РёР»Рё РёРјСЏ СЂР°СЃС…РѕРґРёС‚СЃСЏ.
- EMERGENT вЂ” РєРѕРЅС†РµРїС‚ СЂРµР°Р»РёР·РѕРІР°РЅ, РЅРѕ РІ РґРёРїР»РѕРјРµ РЅРµ Р·Р°СЏРІР»РµРЅ.

---

## Communities РІ graphify-out/ (47 total, С‚СЂРµР±СѓСЋС‚ СЂСѓС‡РЅРѕР№ СЂР°Р·РјРµС‚РєРё)

РћР±С‰РёРµ РіСЂСѓРїРїС‹ (РЅР° РѕСЃРЅРѕРІРµ god-nodes):
- **Voice loop community** (Orchestrator, VoiceLoopController, SessionWatcher, EspAudioHealthMonitor)
- **Memory community** (EpisodicMemory, SessionAccumulator, MemoryStore)
- **Perception community** (CameraReader, SceneWorker, VLMClient, WhisperASRClient)
- **MCU community** (MCUClient, ActionLayer, device.py)
- **Identity/Persona community** (TuningStore, PromptBuilder, EchoGate)
- **Events community** (EventLog, api_runtime)

