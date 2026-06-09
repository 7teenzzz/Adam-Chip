# Phase 35 — Wave 1 Evidence (Bring-up & smoke)

**Run:** 2026-06-09 | **Branch under test:** ultimate-integration @ 95f2b92 | **Mode:** maintenance

## Task 1 — Branch load
- return_branch (restore after phase) = `voice-loop-recovery`
- main dir status before checkout = clean (all work committed; no stash needed)
- `git worktree remove /tmp/adam-ult` → removed
- `git checkout ultimate-integration` in `/home/i17jet/Agents/Adam-Chip` → `Switched to branch 'ultimate-integration'`
- HEAD = `95f2b92` (merge bringing Phase 35 planning artifacts onto ultimate-integration)
- 10 commits ahead of origin/ultimate-integration — **NOT pushed** (per D-04)
- worktree list: only main dir remains

## Task 2 — Restart + health + ESP probe (W2)
- `sudo systemctl restart adam-orchestrator.service` → up after 4 polls (~8s, Gemma prefill)
- services active: adam-orchestrator, adam-llm, adam-tts-silero
- TTS :8082/health OK · ASR :8095/health OK
- `which ollama` → absent (OK, D-04)
- loaded `mcu.base_url` = `http://10.10.10.171`
- ESP `http://10.10.10.171/api/status` → **OK** (control plane reachable; predicts ESP audio path live)

## Task 3 — Live config validation + maintenance text-turn smoke
LIVE `/api/config` (running process, not on-disk file):
- `flora` block present, `flora.enabled = True`
- `skills` = ['weather', 'jokes']
- `services.asr.wake_words = адам`  ← **de-mojibake confirmed on running orchestrator** (was «Р°РґР°Рj» on ult before merge 15d23ca)
- `agent.name = Адам Чип` · `agent.mode = maintenance`
- `services.tts.output_target = esp32_speaker`
- `tuning.voice.volume = 0.45`
- assertion script printed `CONFIG OK`, exit 0

Maintenance text turn (`POST /api/agent/turn {"transcript":"Адам, ты меня слышишь?"}`):
- reply = `Слышу. Вы здесь.` (clean Russian, in-persona)
- turn_id = `2bdd5d91`, skill = None (general LLM turn)
- dialogue_turns: 2041 → 2043 (delta +2 = viewer + adam) → MEMORY WRITE OK
- trace (via /api/agent/events): llm_thinking_started → scene_context_injected → viewer_transcript → tts_started → tts_finished → adam_reply → llm_thinking_finished (has llm ✓, has tts ✓)

## Verdict
**Wave 1 GREEN (REQ-INT-CONFIG-LIVE).** Integrated branch is what the live orchestrator runs; de-mojibaked config valid on hardware; ESP reachable; full text pipeline (LLM→TTS→memory) completes. Ready for Wave 2 (live voice, exhibition mode).
