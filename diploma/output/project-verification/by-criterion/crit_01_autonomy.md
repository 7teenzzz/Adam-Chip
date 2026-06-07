<!--
GENERATED: 2026-05-16T17:35:39Z
STAGE: 2
SOURCE: evaluation_criteria.md + graphify (crit-1)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Criterion 1 вЂ” РЎС‚РµРїРµРЅСЊ Р°РІС‚РѕРЅРѕРјРёР·Р°С†РёРё

## Theoretical Definition

РР· СЂР°Р·РґРµР»Р° 2.1.1: СѓСЂРѕРІРµРЅСЊ РІРЅСѓС‚СЂРµРЅРЅРµР№ РѕСЂРіР°РЅРёР·Р°С†РёРѕРЅРЅРѕР№ РЅРµР·Р°РІРёСЃРёРјРѕСЃС‚Рё СЃРёСЃС‚РµРјС‹. РСЃС‚РѕС‡РЅРёРє С†РµР»РµРїРѕР»Р°РіР°РЅРёСЏ. Р§РµС‚С‹СЂРµ СѓСЂРѕРІРЅСЏ: СЂРµР°РєС‚РёРІРЅС‹Р№ в†’ РєРѕРЅС‚РµРєСЃС‚РЅРѕ-СѓРїСЂР°РІР»СЏРµРјС‹Р№ в†’ РїСЂРѕР°РєС‚РёРІРЅС‹Р№ в†’ Р°РІС‚РѕРіРµРЅРµСЂР°С‚РёРІРЅС‹Р№.

## Implementation Status: **PARTIAL**

Adam Chip РґРѕСЃС‚РёРіР°РµС‚ **СѓСЂРѕРІРЅСЏ 2 (РєРѕРЅС‚РµРєСЃС‚РЅРѕ-СѓРїСЂР°РІР»СЏРµРјС‹Р№)** СѓРІРµСЂРµРЅРЅРѕ Рё С‡Р°СЃС‚РёС‡РЅРѕ СѓСЂРѕРІРЅСЏ 3 (РїСЂРѕР°РєС‚РёРІРЅС‹Р№) С‡РµСЂРµР· С„РѕРЅРѕРІС‹Рµ worker'С‹.

## Graphify Evidence

| Node | File | Degree | Role |
|---|---|---|---|
| `VoiceLoopController` | System/adam/webrtc_vad.py | 42 | Р“Р»Р°РІРЅС‹Р№ voice loop |
| `SessionWatcher` | System/Orchestrator.py | 30 | Р¤РѕРЅРѕРІС‹Р№ watcher СЃРµСЃСЃРёР№ |
| `SceneWorker` | System/Orchestrator.py | 30 | РџРµСЂРёРѕРґРёС‡РµСЃРєРёР№ VLM-Р°РЅР°Р»РёР· |
| `EspAudioHealthMonitor` | System/Orchestrator.py | 32 | Health-monitoring background loop |

## Verification Trace

1. `graphify query "voice loop autonomy"` в†’ `VoiceLoopController` + `SessionWatcher` + `SceneWorker`.
2. Reading `System/Orchestrator.py`: РµСЃС‚СЊ `SessionWatcher` (С„РѕРЅРѕРІР°СЏ Р·Р°РґР°С‡Р°), `SceneWorker` (VLM РєР°Р¶РґС‹Рµ `scene_interval_sec`=4СЃ), `EspAudioHealthMonitor` (polling).
3. Reading `Config.json`: `scene_interval_sec: 4`, `scene_stale_after_sec: 8` вЂ” С„РѕРЅРѕРІР°СЏ Р°РєС‚РёРІРЅРѕСЃС‚СЊ РЅР°СЃС‚СЂРѕРµРЅР°.
4. Wake word detection (`wake_word_required: true` РІ exhibition) вЂ” СЃРёСЃС‚РµРјР° РќР• РёРЅРёС†РёРёСЂСѓРµС‚ turn Р±РµР· wake word.
5. РќРµС‚ idle scheduler, РіРµРЅРµСЂРёСЂСѓСЋС‰РµРіРѕ СЃРїРѕРЅС‚Р°РЅРЅС‹Рµ СЂРµРїР»РёРєРё Р±РµР· wake word.

## Findings

**Р РµР°Р»РёР·РѕРІР°РЅРѕ:**
- Voice loop СЃ Р°СЃРёРЅС…СЂРѕРЅРЅРѕР№ РѕР±СЂР°Р±РѕС‚РєРѕР№
- Periodic scene analysis (proactive perception)
- Background health monitoring
- Session accumulator (РЅР°РєРѕРїР»РµРЅРёРµ СЃРѕСЃС‚РѕСЏРЅРёСЏ)

**РћС‚СЃСѓС‚СЃС‚РІСѓРµС‚/С‡Р°СЃС‚РёС‡РЅРѕ:**
- РЎРїРѕРЅС‚Р°РЅРЅР°СЏ РёРЅРёС†РёР°С†РёСЏ СЂРµРїР»РёРє Р±РµР· wake word (proactive speech)
- РђРІС‚РѕРіРµРЅРµСЂР°С‚РёРІРЅР°СЏ РїРѕСЃС‚Р°РЅРѕРІРєР° Р·Р°РґР°С‡ (РЅРµС‚ РїР»Р°РЅРёСЂРѕРІС‰РёРєР° С†РµР»РµР№)
- LLM РЅРµ РІС‹Р·С‹РІР°РµС‚СЃСЏ Р±РµР· РІРЅРµС€РЅРµРіРѕ С‚СЂРёРіРіРµСЂР°

## РЎРІСЏР·СЊ СЃ РіР»Р°РІРѕР№ 3 РґРёРїР»РѕРјР°

- **Р Р°Р·РґРµР» 3.1.2** Р·Р°СЏРІР»СЏРµС‚ В«СЃРѕС‡РµС‚Р°РЅРёРµ СЂРµР°РєС‚РёРІРЅРѕРіРѕ Рё РїСЂРѕР°РєС‚РёРІРЅРѕРіРѕ СЂРµР¶РёРјРѕРІВ» вЂ” СЂРµР°Р»РёР·РѕРІР°РЅРѕ С‡Р°СЃС‚РёС‡РЅРѕ С‡РµСЂРµР· perception, РЅРµ С‡РµСЂРµР· speech.
- **Р Р°Р·РґРµР» 3.3.4** РѕРїРёСЃС‹РІР°РµС‚ В«РїСЂРѕР°РєС‚РёРІРЅРѕРµ РїСЂРѕСЏРІР»РµРЅРёРµВ» вЂ” СЂРµР°Р»РёР·РѕРІР°РЅРѕ РєР°Рє scene monitoring, РЅРѕ РЅРµ РєР°Рє СЃРїРѕРЅС‚Р°РЅРЅР°СЏ СЂРµС‡СЊ.
- **РњРµС‚СЂРёРєР° 3.4.4** (РёРЅС‚РµСЂР°РєС†РёРѕРЅРЅРѕСЃС‚СЊ Рё РёРЅРёС†РёР°С‚РёРІР°) вЂ” РѕРїРµСЂР°С†РёРѕРЅР°Р»РёР·РёСЂСѓРµС‚ СЌС‚РѕС‚ РєСЂРёС‚РµСЂРёР№.

## Recommendations for Chapter 3 Writing

Р’ СЂР°Р·РґРµР»Рµ 3.4.4 С‡РµСЃС‚РЅРѕ РѕРїРёСЃР°С‚СЊ: РїСЂРѕР°РєС‚РёРІРЅРѕСЃС‚СЊ СЂРµР°Р»РёР·РѕРІР°РЅР° РЅР° СѓСЂРѕРІРЅРµ perception (SceneWorker, SessionWatcher), РЅРѕ РЅРµ РЅР° СѓСЂРѕРІРЅРµ speech (РЅРµС‚ idle reply generator). Р­С‚Рѕ РёРЅР¶РµРЅРµСЂРЅС‹Р№ РєРѕРјРїСЂРѕРјРёСЃСЃ РёР·-Р·Р° СЃС‚РѕРёРјРѕСЃС‚Рё LLM inference РЅР° Jetson.


