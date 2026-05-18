## Pre-existing test failure (not in 21A-03 scope)

- `tests/test_memory.py::EpisodicMemoryTests::test_semantic_roundtrip` —
  AttributeError: 'EpisodicMemory' object has no attribute 'write_semantic'.
  Confirmed failing pre-21A-03 (verified via `git stash` before edits).
  Belongs to memory subsystem, out of scope for FFT spectrum work.
