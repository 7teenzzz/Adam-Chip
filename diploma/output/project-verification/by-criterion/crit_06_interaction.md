<!--
GENERATED: 2026-05-16T17:35:39Z
STAGE: 2
SOURCE: evaluation_criteria.md + graphify (crit-6)
STATUS: OK complete
RUN: Manual or CI-triggered
NEXT_UPDATE: manual trigger or when source changes
-->
# Criterion 6 вЂ” РРЅС‚РµСЂР°РєС†РёРѕРЅРЅРѕСЃС‚СЊ

## Theoretical Definition

РР· СЂР°Р·РґРµР»Р° 2.1.6: С…Р°СЂР°РєС‚РµСЂ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёСЏ. Р§РµС‚С‹СЂРµ С‚РёРїР°: СЂРµР°РєС‚РёРІРЅРѕРµ в†’ РґРёР°Р»РѕРіРѕРІРѕРµ в†’ РєРѕРѕРїРµСЂР°С‚РёРІРЅРѕРµ в†’ РєРѕРѕСЂРґРёРЅР°С†РёРѕРЅРЅРѕРµ.

## Implementation Status: **PARTIAL** (РґРёР°Р»РѕРіРѕРІРѕРµ, Р±РµР· РєРѕРѕРїРµСЂР°С†РёРё)

Adam Chip вЂ” **РґРёР°Р»РѕРіРѕРІРѕРµ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёРµ** СѓРІРµСЂРµРЅРЅРѕ; РєРѕРѕРїРµСЂР°С‚РёРІРЅРѕРµ Рё РєРѕРѕСЂРґРёРЅР°С†РёРѕРЅРЅРѕРµ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‚ (single-agent).

## Graphify Evidence

| Node | File | Role |
|---|---|---|
| `VoiceLoopController` | System/adam/webrtc_vad.py | 42 вЂ” voice loop |
| `WakeWordEngine` | System/adam/wake_word.py | Wake word detection |
| `WhisperASRClient` | System/adam/inference.py | 15 вЂ” ASR |
| `TTSClient` | System/adam/inference.py | 15 вЂ” TTS |
| `webrtc_vad.py` | System/adam/webrtc_vad.py | VAD |
| `SessionAccumulator` | System/adam/episodic.py | 23 вЂ” context retention |

## Verification Trace

1. Voice pipeline: WakeWord в†’ VAD в†’ ASR в†’ LLM в†’ TTS + MCU. РџРѕРґС‚РІРµСЂР¶РґРµРЅРѕ РІ `Orchestrator.py`.
2. `Config.json` в†’ `agent.history_turns: 2` вЂ” РєРѕРЅС‚РµРєСЃС‚ РґРёР°Р»РѕРіР° СѓРґРµСЂР¶РёРІР°РµС‚СЃСЏ.
3. `Config.json` в†’ `services.asr.reply_window_sec: 3.75` вЂ” СЃРёСЃС‚РµРјР° Р¶РґС‘С‚ РїСЂРѕРґРѕР»Р¶РµРЅРёСЏ СЂРµС‡Рё.
4. `Config.json` в†’ `safety.half_duplex_mute: true` вЂ” mic Р·Р°РіР»СѓС€Р°РµС‚СЃСЏ РІРѕ РІСЂРµРјСЏ TTS.
5. `Config.json` в†’ `services.tts.filler_enabled: true` + `filler_phrase: "РҐРј..."` вЂ” СЃРЅРёР¶РµРЅРёРµ perceived latency.
6. Wake word required РІ exhibition mode в†’ СЂРµР°РєС‚РёРІРЅРѕРµ Р°РєС‚РёРІРёСЂРѕРІР°РЅРёРµ.

## Findings

**РЎРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚ В«РґРёР°Р»РѕРіРѕРІРѕРјСѓ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёСЋВ» (С‚Р°Р±Р»РёС†Р° 8):**

- вњ… РЈРґРµСЂР¶Р°РЅРёРµ РєРѕРЅС‚РµРєСЃС‚Р° (SessionAccumulator + history_turns)
- вњ… РћР±РјРµРЅ СЂРµРїР»РёРєР°РјРё (full voice loop)
- вњ… Half-duplex (Р·Р°С‰РёС‚Р° РѕС‚ echo feedback)
- вњ… Filler phrases (snРёР¶Р°СЋС‚ В«РјС‘СЂС‚РІРѕРµВ» РѕР¶РёРґР°РЅРёРµ)
- вќЊ РљРѕРѕРїРµСЂР°С‚РёРІРЅРѕРµ вЂ” РЅРµС‚ (РЅРµС‚ СЃРѕРІРјРµСЃС‚РЅС‹С… Р·Р°РґР°С‡)
- вќЊ РљРѕРѕСЂРґРёРЅР°С†РёРѕРЅРЅРѕРµ вЂ” РЅРµС‚ (single-agent)
- вљ пёЏ Р РµР°РєС‚РёРІРЅС‹Р№ СЂРµР¶РёРј вЂ” wake word required РІ exhibition

## РЎРІСЏР·СЊ СЃ РіР»Р°РІРѕР№ 3

- **Р Р°Р·РґРµР» 3.2.5** (РїРµСЂС†РµРїС‚РёРІРЅС‹Р№/СЂРµС‡РµРІРѕР№ РєРѕРЅС‚СѓСЂС‹) вЂ” РїРѕР»РЅРѕСЃС‚СЊСЋ СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓРµС‚.
- **Р Р°Р·РґРµР» 3.3.4** (СЃС†РµРЅР°СЂРёР№ РІР·Р°РёРјРѕРґРµР№СЃС‚РІРёСЏ) вЂ” РѕРїРёСЃС‹РІР°РµС‚ 4 СЂРµР¶РёРјР°.
- **РњРµС‚СЂРёРєР° 3.4.4** (РёРЅС‚РµСЂР°РєС†РёРѕРЅРЅРѕСЃС‚СЊ Рё РёРЅРёС†РёР°С‚РёРІР°) вЂ” РѕРїРµСЂР°С†РёРѕРЅР°Р»РёР·РёСЂСѓРµС‚.

## Recommendations for Chapter 3

Р’ СЂР°Р·РґРµР»Рµ 3.2.5 СЏРІРЅРѕ РѕРїРёСЃР°С‚СЊ pipeline: WakeWord в†’ VAD в†’ ASR в†’ LLM в†’ TTS + MCU, СЃ СѓРєР°Р·Р°РЅРёРµРј Config-РїР°СЂР°РјРµС‚СЂРѕРІ. Р’ СЂР°Р·РґРµР»Рµ 3.4.4 вЂ” РјРµС‚СЂРёРєРё: average dialogue length, response latency, wake_word_accuracy, half_duplex_violations.


