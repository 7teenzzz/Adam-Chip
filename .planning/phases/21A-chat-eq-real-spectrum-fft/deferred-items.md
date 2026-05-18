# Phase 21A — Deferred Items

Pre-existing failures observed during execution but NOT caused by Phase 21A changes. These are out-of-scope per executor SCOPE BOUNDARY rule.

## Pre-existing test failures on baseline (verified via `git stash`)

1. **tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip**
   - `AttributeError: 'EpisodicMemory' object has no attribute 'write_semantic'`
   - Test references a method that has not been implemented (or was removed) in `System/adam/episodic.py`.
   - Unrelated to Phase 21A (chat-panel EQ); belongs to backlog for the memory subsystem.
   - Confirmed failing pre-Phase 21A via `git stash` baseline check.

2. **tests/test_mic_reader_spectrum.py::test_payload_shape** *(RESOLVED by 21A-03)*
   - Observed during 21A-04 execution because 21A-03 was running in parallel and had not yet merged.
   - Turned GREEN after 21A-03's `_compute_bands` integration into `_emit_audio_level`.
