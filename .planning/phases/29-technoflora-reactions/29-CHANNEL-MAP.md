# Phase 29 — Channel ↔ Line Calibration (context for agents)

**Status:** ⏳ PENDING hardware results (test script ready, mapping not yet filled)
**Owner artifact:** consumed by 29-01 (firmware presets), 29-02 (Config), 29-03 (event layer)
**Created:** 2026-06-07

> Read this before touching `flora.states.think_pulse`, the `flora.light_channels` /
> `flora.vibro_channels` masks, or any "group"/"line"/directional animation logic.
> The physical channel→line mapping is a HARDWARE FACT that must be measured, not
> assumed. Until the Results table below is filled, treat per-line grouping as TBD.

---

## Why this exists

Locked decision **D-01** (29-CONTEXT.md) says the светофлора is a **cluster without
spatial order** → directional effects (wave / running light / bloom 0→10) were
dropped in favor of collective + random-group effects.

**This was revised on 2026-06-07.** The user described `think_pulse` (раздумье) as
*"very fast breathing waves on SOME lines, fast flickers on OTHER lines"* — i.e.
there IS some grouping/line structure among channels 0–10. Two open questions
follow, both answerable only on hardware:

1. **Grouping:** which channel indices belong to which physical line/group? The
   heterogeneous `think_pulse` (waves-vs-flickers split) needs this assignment.
2. **Order within a line:** are the lamps on a single line wired in physical order
   (so a wave can travel *along* the line), or are they unordered? If ordered,
   limited directional micro-effects come back onto the table — but ONLY along a
   line, never globally.

**Channel masks (confirmed 2026-06-07 by hardware — REVERSES the original D-02):**
vibro motors = channels **0–3** (first 4), светофлора light = channels **4–14**
(next 11). Config (`light_channels`/`vibro_channels`) + firmware
(`kFloraLightChannelLo/Hi=4/14`, `kFloraVibroChannelLo/Hi=0/3`) updated to match.
The light max_duty ceiling applies ONLY to light (4–14); vibro (0–3) is exempt and
runs up to its own ~95% cap. The line test still maps which physical lamp = each of
channels 4–14.

---

## The test

**Script:** [`scripts/diagnostics/flora_line_identify.py`](../../../scripts/diagnostics/flora_line_identify.py)

For each channel it (a) announces the index aloud via Silero TTS ("Линия ноль",
"Линия один", …) and (b) plays a fast breathing pulse on **that channel only**
(all others forced off), so the operator can see/feel which physical line responds.

**Run (from repo root, on the Jetson):**
```bash
python scripts/diagnostics/flora_line_identify.py                 # channels 0-14
python scripts/diagnostics/flora_line_identify.py --channels 4-14 # light only
python scripts/diagnostics/flora_line_identify.py --channels 0-3 --no-tts  # vibro
```

**Invariants honored (do not regress when extending the script):**
- ESP HTTP goes through `_NO_PROXY_OPENER` (`ProxyHandler({})`) — v2ray on the
  Jetson otherwise leaks sockets into ESP32:81's 4-slot pool (CLAUDE.md gotcha,
  mirrors `System/adam/device.py`).
- Config-First: URLs, channel range, gamma are read from `System/Config.json`
  (`mcu.base_url`, `services.tts.base_url`, `mcu.channels`, `flora.gamma`).
- PWM is 12-bit (0–4095); gamma ~2.2 applied so the breath looks linear.

**Pre-run caveats:**
- Run with the orchestrator's flora controller **idle** (maintenance mode or
  orchestrator stopped) — otherwise it fights the script for the channels.
- ESP IP: Config `mcu.base_url` = `http://10.10.10.171`, but project notes record
  the static IP as `192.168.0.171`. If no response, pass
  `--base-url http://192.168.0.171` and reconcile Config afterward.

---

## Results (FILL THIS IN — operator + agent)

Record what each channel physically drove. `kind` = light | vibro | dead.
`line/group` = the operator's label for the physical line (e.g. "L1", "left strip",
"center"). `order` = position within that line if the line is ordered (else "—").

| Channel | kind | line/group | order in line | notes |
|--------:|------|-----------|--------------:|-------|
| 0  | ? | ? | ? | |
| 1  | ? | ? | ? | |
| 2  | ? | ? | ? | |
| 3  | ? | ? | ? | |
| 4  | ? | ? | ? | |
| 5  | ? | ? | ? | |
| 6  | ? | ? | ? | |
| 7  | ? | ? | ? | |
| 8  | ? | ? | ? | |
| 9  | ? | ? | ? | |
| 10 | ? | ? | ? | |
| 11 | ? | ? | ? | (expected vibro) |
| 12 | ? | ? | ? | (expected vibro) |
| 13 | ? | ? | ? | (expected vibro) |
| 14 | ? | ? | ? | (expected vibro) |

**Derived once filled:**
- Confirm/correct `flora.light_channels` and `flora.vibro_channels` in Config.
- Define line/group sets (e.g. `flora.lines = [[0,2,4], [1,3,5], …]`) — NEW Config
  key, document in `Config.schema.json`.
- Are any lines ordered? (yes/no per line) → decides whether directional
  micro-waves along a line are available for `think_pulse`.

---

## How results feed the design (downstream actions)

Once the table is filled, the following are unblocked (do them, in order):

1. **Config (29-02):** verify `flora.light_channels`/`flora.vibro_channels`; add a
   `flora.lines`/`flora.groups` structure describing the line membership; document
   in `Config.schema.json`. Config-First — no hardcoded channel lists in firmware
   beyond the structural defaults in `AdamsConfig.h` (kept in sync with Config).
2. **Firmware `think_pulse` (29-01):** implement the heterogeneous texture — assign
   each line/group to either "fast breathing wave" (`wave_period_ms`, ~400–600 ms)
   or "fast flicker" (`flicker_ms`, ~120 ms). Current Config start values:
   `flash_ms=500, wave_period_ms=500, flicker_ms=120, base_pct=20, peak_pct=71`.
3. **Directional option:** if (and only if) a line is ordered, a wave may travel
   along it. Global 0→10 direction stays banned (D-01 cluster). Update D-01 with
   the measured nuance ("cluster of N lines; intra-line order = …").

---

## Cross-references

- Decisions: 29-CONTEXT.md → **D-01** (cluster), **D-02** (channel masks),
  **D-07b** (RMS in listening from mic), Specifics §"Калибровка линий".
- Research: 29-RESEARCH.md → firmware animation engine = FreeRTOS task writing
  `writeAllChannelsRaw`; I2C contention with sensor task (Pitfall 3).
- Patterns: 29-PATTERNS.md → `Pca9685Module.cpp` channel-write analogs.
- Config: `System/Config.json` → `flora.*`; `mcu.base_url`, `mcu.channels`.
- Script: `scripts/diagnostics/flora_line_identify.py`.
