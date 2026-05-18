# Phase 21A — Deferred Items

Pre-existing failures observed during 21A-04 execution but NOT caused by this plan's changes. These are out-of-scope per executor SCOPE BOUNDARY rule.

## Pre-existing test failures on baseline (verified via `git stash`)

1. **tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip**
   - `AttributeError: 'EpisodicMemory' object has no attribute 'write_semantic'`
   - Test references a method that has not been implemented (or was removed) in `System/adam/episodic.py`.
   - Unrelated to Phase 21A (chat-panel EQ); belongs to backlog for the memory subsystem.

2. **tests/test_mic_reader_spectrum.py::test_payload_shape**
   - `AssertionError: audio_level payload missing 'bands' key`
   - This test ASSERTS the Plan 03 deliverable (FFT bands in `_emit_audio_level` payload). Plan 03 has not yet been executed in this wave — current `_emit_audio_level` still emits the legacy payload `{level, state, source, channels}` without `bands`.
   - Expected to turn green once Plan 03 lands.
