---
phase: 21A
plan: 07
type: execute
wave: 5
depends_on: [03, 04, 05, 06]
files_modified:
  - .planning/phases/21A-chat-eq-real-spectrum-fft/21A-SMOKE-RESULTS.md
autonomous: false
requirements:
  - UI-EQ-01
  - UI-EQ-02
  - UI-EQ-03
  - UI-EQ-04
  - UI-EQ-05
must_haves:
  truths:
    - "Maintenance-mode Orchestrator boots cleanly with all 8 spectrum_* keys loaded"
    - "audio_level events arrive at ~25/s on the SSE stream with bands[24] in [0..1]"
    - "Browser equalizer: bars track real voice, color goes green→yellow→red by level, silence = flat floor"
    - "DevTools Network tab: single EventSource per page even after 5× Chat ↔ Settings toggle"
    - "Hot-reload of spectrum_floor_db via PATCH /api/config changes bar dynamic range without Orchestrator restart"
  artifacts:
    - path: ".planning/phases/21A-chat-eq-real-spectrum-fft/21A-SMOKE-RESULTS.md"
      provides: "Recorded smoke-test outcomes for M-1..M-4 from VALIDATION.md plus the RESEARCH §11 steps"
      contains: "M-1"
  key_links:
    - from: "manual browser smoke test"
      to: "VALIDATION.md M-1..M-4 + RESEARCH §11 Steps 1-5"
      via: "operator runs each step and records pass/fail"
      pattern: "PASS|FAIL"
---

<objective>
Run the full Phase 21A smoke test against a live Maintenance-mode Orchestrator and a live browser. Record results in a single SMOKE-RESULTS.md file so `/gsd-verify-work` has a deterministic phase-gate artefact. This is the only blocking-checkpoint task in the phase.

Purpose: VALIDATION.md mandates manual verification of UI-EQ-03 / UI-EQ-04 / UI-EQ-05 (no programmatic API for visual perception or DevTools network inspection). RESEARCH §11 provides the recipe.
Output: One Markdown file with per-step PASS/FAIL annotations. Operator-driven; cannot be automated.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-CONTEXT.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-RESEARCH.md
@.planning/phases/21A-chat-eq-real-spectrum-fft/21A-VALIDATION.md
</context>

<tasks>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 1: Run live smoke test (M-1, M-2, M-3, M-4 + RESEARCH §11 Steps 1-5) and record outcomes</name>
  <what-built>
    Phases 21A-01 through 21A-06 have shipped:
    - Wave 0 test stubs (Plan 01)
    - Config keys + schema (Plan 02)
    - MicReader FFT pipeline + cadence change to 25 Hz + apply_config hot-reload (Plan 03)
    - events.jsonl writing-side sampler (Plan 04)
    - wakeMeter.js refactor: real bands[24] render + color gradient + idempotent dispose (Plan 05)
    - chat.js hint update + settings.js draggable audit (Plan 06)

    Full Python test suite green (`./.venv/bin/python -m pytest tests/ -x -q`).
  </what-built>
  <read_first>
    - 21A-VALIDATION.md "Manual-Only Verifications" table (M-1, M-2, M-3, M-4)
    - 21A-RESEARCH.md §11 "Smoke-Test Recipe" (Steps 1-5)
    - 21A-CONTEXT.md decisions D-10 (no smoothing), D-11 (color), D-12 (OWW preserved), D-14 (dispose)
  </read_first>
  <how-to-verify>
    1. Launch Orchestrator in maintenance mode (terminal A):
       ```
       cd /home/i17jet/Agents/Adam-Chip
       ./scripts/adam_bootstrap_venv.sh   # if not already done
       ./scripts/adam_power_maxn.sh
       PYTHONPATH=System ADAM_MODE=maintenance ./.venv/bin/python System/Orchestrator.py
       ```
       Wait for boot to complete. Confirm via `curl --noproxy '*' -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool | head -20` showing voice_state != "boot_warmup".

    2. **Step 1 (RESEARCH §11) — Backend cadence + bands shape (terminal B):**
       ```
       curl --noproxy '*' -N -fsS http://127.0.0.1:8080/api/agent/stream \
         | grep --line-buffered '"type":"audio_level"' | head -125
       ```
       Time the output: should take ~5 seconds (125 events / 25 Hz). Verify each line contains `"bands":[`. Sample one line, parse JSON, confirm `len(bands) == 24` and `min(bands) >= 0.0 and max(bands) <= 1.0`. **Record cadence and bands shape PASS/FAIL.**

    3. **Step 2 (RESEARCH §11) — Spectrum sanity via /api/agent/events:**
       Run the Python one-liner from RESEARCH §11 Step 2 (already in that section verbatim). Verify `len range: 24 24` and `val range` within `[0.0, 1.0]`. **Record PASS/FAIL.**

    4. **M-1 + M-2 (VALIDATION.md) — Browser visual smoke test:**
       Open `http://<JETSON_IP>:8080` in a desktop browser. Navigate to Chat panel.
       - Speak "адам, проверка" into the ESP32 microphone. Bars should follow voice formants with no inertia. **Record PASS/FAIL for M-1.**
       - Speak a loud sustained "а-а-а-а" from ~1m away. Verify the loudest bars transition through yellow to red at the peak. At normal speaking volume, mostly green. On silence, bars sit at floor. **Record PASS/FAIL for M-2.**

    5. **M-3 (VALIDATION.md) — DevTools EventSource leak check:**
       Open DevTools → Network tab. Filter by "eventsource". Note the count of active EventSource connections.
       Toggle Chat → Settings → Chat 5 times. After each toggle, recount active EventSource rows.
       Expected: count remains ≤ 1 per page (no accumulation; opening Settings adds 1 for its own meter, closing it removes 1). **Record PASS/FAIL for M-3.** Capture a screenshot of the final state.

    6. **M-4 (VALIDATION.md) — Synthetic backfill graceful degradation (optional, hard to simulate cleanly):**
       If easily reproducible, temporarily stop ESP32 audio stream (power-cycle ESP32 or use `tc qdisc add dev <iface> root netem loss 100%` on the Jetson Ethernet). MicReader._level_emit_loop will start emitting synthetic audio_level events without `bands`. Verify in browser: bars freeze on their last snapshot — they do NOT fall to zero, do NOT show NaN, do NOT throw JS errors in DevTools console. **Record PASS/FAIL for M-4.** If too hard to simulate, mark as SKIPPED with reason; not blocking.

    7. **Step 4 (RESEARCH §11) — Cadence visibly snappier:**
       Subjective check: bars update at 25 Hz vs. the previous 10 Hz. Should feel ~2.5× more responsive. **Record PASS/FAIL.**

    8. **Step 5 (RESEARCH §11) — Hot-reload:**
       ```
       curl --noproxy '*' -X PATCH -H 'Content-Type: application/json' \
         -d '{"section":"media","patch":{"audio":{"spectrum_floor_db":-40}}}' \
         http://127.0.0.1:8080/api/config | python3 -m json.tool
       ```
       Observe browser bars become "louder" (lower dynamic range collapsed to [0..1] means quieter input maps higher). No Orchestrator restart, no error in journalctl. `config_patched` event arrives on SSE. **Record PASS/FAIL.** Restore default `-60` afterward.

    9. **events.jsonl growth check (Plan 04 deliverable):**
       ```
       tail -n 1000 data/adam/events.jsonl | grep -c '"type":"audio_level"'
       wc -l data/adam/events.jsonl
       ```
       Compare growth rate before and after (use file size at two timestamps 30 seconds apart while audio is active). Expected disk-write rate ~5 audio_level lines/second (one every 5 with sampler default=5), even though SSE shows 25/sec. **Record PASS/FAIL.**

    10. **Write `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-SMOKE-RESULTS.md`** with:
        - Date + Orchestrator boot timestamp
        - Each step (1, 2, M-1, M-2, M-3, M-4, RESEARCH §11 Steps 4-5, jsonl growth) marked PASS / FAIL / SKIPPED with one-line note
        - If any FAIL: a short root-cause note and which plan needs revisiting
        - Final verdict line: `## Smoke Verdict: PASS` or `FAIL`

    11. Stop the Orchestrator (Ctrl+C in terminal A).

    Failure-handling rules (per RESEARCH §11):
    - Bars all flat red regardless of input → dBFS reference calibration wrong (Plan 03 Task 2 — check MAG_REF math)
    - Bars all at zero on speech → bin DC leak or band table boundaries off (Plan 03 Task 1 — `_build_log_band_table` lo/hi clamping)
    - Bars only on left half → bin indexing inverted or log-edges mis-built (Plan 03 Task 1)
    - Multiple EventSource rows → dispose path not running (Plan 05 Task 2)
  </how-to-verify>
  <resume-signal>
    Type "approved" to mark the phase smoke-verified, OR describe any FAIL outcomes so the orchestrator can route them to a gap-closure plan.
  </resume-signal>
</task>

</tasks>

<verification>
- `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-SMOKE-RESULTS.md` exists
- Final verdict line present and equals `## Smoke Verdict: PASS`
- All blocking steps (Steps 1-2, M-1, M-2, M-3, hot-reload) recorded PASS (M-4 may be SKIPPED with reason)
</verification>

<success_criteria>
- All five UI-EQ-* requirements have evidence of working in a live system
- Phase 21A is ready for `/gsd-verify-work` and `/gsd-extract-learnings`
- Any FAIL outcomes are documented and routed via gap-closure
</success_criteria>

<output>
After completion, create `.planning/phases/21A-chat-eq-real-spectrum-fft/21A-07-SUMMARY.md` referencing the SMOKE-RESULTS.md file as evidence.
</output>
