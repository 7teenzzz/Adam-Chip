<!--
GENERATED: 2026-05-16T17:35:06Z
STAGE: 1
SOURCE: graphify-out/GRAPH_REPORT.md
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Code Graph вЂ” Community Labels

Р Р°Р·РјРµС‚РєР° 47 communities РёР· `graphify-out/` РЅР° РѕСЃРЅРѕРІРµ РёС… god-nodes. РЎРѕРѕС‚РІРµС‚СЃС‚РІРёРµ РєРѕРЅС†РµРїС‚Р°Рј РґРёРїР»РѕРјР° СѓРєР°Р·Р°РЅРѕ РІ СЃРєРѕР±РєР°С….

## РђРєС‚РёРІРЅРѕ-РёСЃРїРѕР»СЊР·СѓРµРјС‹Рµ СЃРѕРѕР±С‰РµСЃС‚РІР° (10 РєР»СЋС‡РµРІС‹С…)

| ID (suggested) | Label | God-nodes | РЎРІСЏР·СЊ СЃ РґРёРїР»РѕРјРѕРј |
|---|---|---|---|
| C-Orchestration | Voice Loop Orchestration | Orchestrator.py (85), VoiceLoopController (42), SessionWatcher (30), EspAudioHealthMonitor (32) | 3.2.1 (РѕР±С‰Р°СЏ Р°СЂС…РёС‚РµРєС‚СѓСЂР°), Crit 1 |
| C-Memory | Episodic Memory Layer | EpisodicMemory (29), MemoryStore (14), SessionAccumulator (23) | 3.2.4 (РїР°РјСЏС‚СЊ), Crit 5 |
| C-Identity | Identity & Anti-drift | TuningStore (17), tuning.py (24), EchoGate (15) | 3.2.3 (СЃРёСЃС‚РµРјРЅС‹Р№ РїСЂРѕРјРїС‚), Crit 3, Crit 4 |
| C-MCU | Motor Control | MCUClient (25), device.py | 3.2.6 (РєРѕРјР°РЅРґРЅС‹Р№ РєРѕРЅС‚СѓСЂ), Crit 7 |
| C-Perception | Camera + Scene Worker | CameraReader (23), SceneWorker (30), VLMClient (14) | 3.2.5 (РІРёР·СѓР°Р»СЊРЅС‹Р№ РєРѕРЅС‚СѓСЂ), Crit 7 |
| C-ASR | Speech Recognition | WhisperASRClient (15), ASR_WhisperX.py (15) | 3.2.5 (СЂРµС‡РµРІРѕР№ РІС…РѕРґ), Crit 6 |
| C-TTS | Speech Synthesis | TTSClient (15) | 3.2.5 (СЂРµС‡РµРІРѕР№ РІС‹С…РѕРґ), Crit 7 |
| C-Events | Events & Metrics | EventLog (13), api_runtime.py (17), metrics.py | 3.4 (РјРµС‚СЂРёРєРё), Crit 8 |
| C-Prompt | Prompt Builder | prompt.py (PromptBuilder), LeadingNoiseFilter | 3.2.3, 3.2.4, Crit 3 |
| C-Inference | LLM Inference | inference.py (13), BaseModel (15) | 3.2.2 (РїСЂРѕРіСЂР°РјРјРЅС‹Р№ СЃС‚РµРє) |

## РњР°Р»С‹Рµ СЃРѕРѕР±С‰РµСЃС‚РІР° (11+ thin)

РћСЃС‚Р°Р»СЊРЅС‹Рµ СЃРѕРѕР±С‰РµСЃС‚РІР° РЅРёР·РєРѕР№ СЃРІСЏР·РЅРѕСЃС‚Рё вЂ” СЃР»СѓР¶РµР±РЅС‹Рµ РјРѕРґСѓР»Рё, РєРѕРЅС„РёРіСѓСЂР°С†РёРё, СѓС‚РёР»РёС‚С‹. РќРµ РёРјРµСЋС‚ РїСЂСЏРјС‹С… СЃРѕРѕС‚РІРµС‚СЃС‚РІРёР№ РІ РґРёРїР»РѕРјРµ РЅР° СѓСЂРѕРІРЅРµ РєРѕРЅС†РµРїС‚РѕРІ.

## Cross-community connections (СЌРјРµСЂРґР¶РµРЅС‚РЅРѕСЃС‚СЊ, Crit 8)

РЎРІСЏР·Рё РјРµР¶РґСѓ СЃРѕРѕР±С‰РµСЃС‚РІР°РјРё:
- `C-Orchestration в†’ C-Memory` (С‡РµСЂРµР· _run_dialogue_turn_locked)
- `C-Orchestration в†’ C-Perception` (С‡РµСЂРµР· SceneWorker)
- `C-Orchestration в†’ C-ASR / C-TTS` (С‡РµСЂРµР· voice loop)
- `C-Prompt в†’ C-Identity` (С‡РµСЂРµР· TuningStore С‡С‚РµРЅРёРµ)
- `C-Prompt в†’ C-Memory` (С‡РµСЂРµР· retrieval)
- `C-Events в†’ РІСЃРµ` (event bus СЃРѕР±РёСЂР°РµС‚ СЃРѕР±С‹С‚РёСЏ РёР· РІСЃРµС… РјРѕРґСѓР»РµР№)

**Р­С‚Рѕ Рё РµСЃС‚СЊ СЌРјРµСЂРґР¶РµРЅС‚РЅС‹Р№ СѓСЂРѕРІРµРЅСЊ РёР· РєСЂРёС‚РµСЂРёСЏ 8**: РїРѕРІРµРґРµРЅРёРµ РЅРµ Р»РѕРєР°Р»СЊРЅРѕ РІ РѕРґРЅРѕРј РјРѕРґСѓР»Рµ, Р° РІРѕР·РЅРёРєР°РµС‚ РЅР° РїРµСЂРµСЃРµС‡РµРЅРёСЏС….

