---
phase: 29
slug: technoflora-reactions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-04
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 29-RESEARCH.md §Validation Architecture. Firmware has no host test
> framework (PlatformIO native tests not present) — FLORA-01/02 validated
> on-hardware; FLORA-03/04/05/06 are Jetson-side pytest units.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Jetson Python side) |
| **Config file** | Wave 0: confirm `pytest.ini` / `pyproject.toml` + `tests/` layout |
| **Quick run command** | `pytest tests/test_flora.py -x` |
| **Full suite command** | `pytest tests/` |
| **Firmware check** | `curl --noproxy '*' -X POST http://10.10.10.171/api/flora/state -d '{"state":"breathe"}'` |
| **Estimated runtime** | ~5–15 seconds (Jetson units) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_flora.py -x`
- **After every plan wave:** Run `pytest tests/`
- **Before `/gsd-verify-work`:** Full suite green + on-hardware visual sign-off (6 states observed)
- **Max feedback latency:** ~15 seconds (Jetson units); on-HW visual is manual gate

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 29-XX-XX | XX | 1 | FLORA-05 | — | config section parses, defaults present, channel masks in 0–15 | unit | `pytest tests/test_flora.py::test_flora_config` | ❌ W0 | ⬜ pending |
| 29-XX-XX | XX | 1 | FLORA-03 | — | event→state mapping (voice_state_change/wake_word_detected/llm_thinking_started/tts_started/tts_finished → flora state) | unit | `pytest tests/test_flora.py::test_event_mapping` | ❌ W0 | ⬜ pending |
| 29-XX-XX | XX | 2 | FLORA-04 | — | WAV→RMS envelope shape (level count/range from known WAV) | unit | `pytest tests/test_flora.py::test_rms_envelope` | ❌ W0 | ⬜ pending |
| 29-XX-XX | XX | 2 | FLORA-06 | — | vibro muted during listening/attentive state | unit | `pytest tests/test_flora.py::test_vibro_silent_listening` | ❌ W0 | ⬜ pending |
| 29-XX-XX | XX | 1 | FLORA-02 | — | `/api/flora/state` accepts valid state → 200, rejects invalid → 400 | integration (on-HW) | `curl --noproxy '*' ... /api/flora/state` | ❌ W0 (manual) | ⬜ pending |
| 29-XX-XX | XX | 1 | FLORA-01 | — | animation smoothness + crossfade ~150–250ms, FreeRTOS task (no 4 Hz main-loop coupling) | manual (on-HW) | visual inspection + optional scope on one channel | N/A manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are placeholders — planner fills exact IDs.*

---

## Wave 0 Requirements

- [ ] `tests/test_flora.py` — stubs for FLORA-03 (event mapping), FLORA-04 (RMS envelope), FLORA-05 (config), FLORA-06 (vibro policy)
- [ ] Test fixture: small known WAV for RMS-envelope assertions (or synthesize in-test via stdlib `wave`)
- [ ] Confirm pytest config/location in repo (Wave 0 discovery)
- [ ] Firmware: no host unit framework — FLORA-01/02 validated on-hardware via curl + visual

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Animation smoothness + crossfade of all 6 states | FLORA-01 | Visual/aesthetic quality; firmware has no host test framework | On Jetson maintenance mode, trigger each state (wake word, speak, idle), observe светофлора/виброфлора; confirm no 4 Hz stutter, crossfade reads smooth |
| `/api/flora/state` on real ESP | FLORA-02 | Needs live ESP32 + PCA9685 hardware | `curl --noproxy '*' -X POST http://10.10.10.171/api/flora/state` with valid/invalid state; assert 200/400 + observed channel change |
| RMS speech-light sync alignment | FLORA-04 | HDMI/ALSA latency offset is hardware-calibrated | Speak a TTS reply; observe light tracks voice envelope; tune `flora.hdmi_latency_offset_ms` until aligned |
| Vibro→mic coupling absent in listening | FLORA-06 | Acoustic/mechanical coupling only observable on hardware | Confirm ASR unaffected while in listening (vibro silent) |

---

## Validation Sign-Off

- [ ] All Jetson-side tasks (FLORA-03/04/05/06) have `<automated>` pytest verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (firmware FLORA-01/02 are the documented manual exception)
- [ ] Wave 0 covers all MISSING references (`tests/test_flora.py` + WAV fixture)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s (Jetson units)
- [ ] On-hardware visual sign-off of 6 states recorded before verify
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
