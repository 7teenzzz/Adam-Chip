# Phase 29 — Deferred Items

Out-of-scope discoveries logged during execution (not fixed — unrelated to the current plan's changes).

## Pre-existing test failure (plan 29-02)

- **Test:** `tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip`
- **Error:** `AttributeError: 'EpisodicMemory' object has no attribute 'write_semantic'`
- **Discovered during:** 29-02 Task 2 full-suite run
- **Scope:** memory module API drift — the test calls `EpisodicMemory.write_semantic` which no longer exists. Unrelated to the flora config section (this plan touched only Config.json / Config.schema.json / config.py / tests/test_flora.py).
- **Action:** NOT fixed (out of scope). Belongs to a memory-module maintenance pass.

## Pre-existing DeprecationWarning

- `System/adam/inference.py:4` — `audioop` deprecated, slated for removal in Python 3.13 (PEP 594). Documented in 29-RESEARCH.md §Environment as a known, project-wide, no-new-risk item. Out of scope here.
