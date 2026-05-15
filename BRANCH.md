# Branch: dynamic-aiim

**Diverged from:** Identity-tuning @ 5ef3413
**Goal:** Dynamic AIIM — runtime emotion/identity state machine for Adam Chip
**Status:** in-progress
**Merge target:** main
**Merge conditions:** все unit-тесты зелёные; [ctx.identity] инжектируется без эха меток в LLM-ответах; drift.json создаётся и обновляется при сессиях

**Modified areas:**
- `System/adam/identity.py` (новый) — AIIM runtime: parser, IdentityVector, EmotionMachine, IntentionTracker, AspectModulator
- `System/adam/identity_drift.py` (новый) — DriftAccumulator, cross-session persistence
- `System/adam/tuning.py` — IdentityTuning Pydantic-модели
- `System/adam/prompt.py` — identity_block param + noise filter patterns
- `Agent Adam Chip/Tuning.json` — секция "identity"
- `Agent Adam Chip/About/System.md` — [ctx.identity] sub-prompt rule
- `System/Orchestrator.py` — wiring AIIM в dialogue turn loop
- `tests/test_identity.py` (новый) — 16 unit-тестов
- `data/adam/identity/` (новый каталог) — drift.json, drift_log.jsonl

**Global changes:** yes — новый [ctx.identity] блок в каждом dialogue turn

**Includes from Identity-tuning:**
- `Agent Adam Chip/About/Identity.md` — 5 интенций персонажа
- `Agent Adam Chip/About/Abilities.md` — новые темы интересов

**Notes for agents:**
Ветка реализует Dynamic AIIM — живую идентичность Адама. Эмоциональное состояние (5 вариантов,
дефолт `curious`) вычисляется per-turn из transcript. Аспектные веса (12 аспектов) парсятся из
Identity.md при старте, накапливают cross-session drift через DriftAccumulator. Моторика
(techflora, scene_director) не затрагивается — это следующая фаза. [ctx.identity] содержит
сырые данные (emotion=, intention=), LLM интерпретирует сама.
