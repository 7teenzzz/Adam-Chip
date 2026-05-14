"""Unit tests for EspAudioHealthMonitor._check() state machine logic.

Runs standalone (no Jetson, no ESP32). Tests all 12 branch scenarios.
"""
import asyncio
import sys

MONO_L = "inmp441_philips32_left"
MONO_R = "inmp441_philips32_right"
STEREO = "inmp441_philips32_stereo"


class FakeResult:
    def __init__(self, data):
        self.ok = True
        self.data = data
        self.status = 200
        self.error = None


class FakeVoiceLoop:
    def __init__(self, profile):
        self.esp32_mic_profile = profile
        self.running = True
        self.restarted = 0

    async def restart(self):
        self.restarted += 1


class FakeEventLog:
    def __init__(self):
        self.events = []

    def append(self, name, data):
        self.events.append((name, data))


class FakeMCU:
    def __init__(self, cap):
        self.cap = cap

    async def request(self, method, path, data=None):
        return FakeResult({"capture": self.cap})


async def do_check(
    voice_loop,
    event_log,
    mcu,
    silence_threshold=24,
    ratio_threshold=6.0,
    clip_burst_threshold=20,
    restore_threshold_polls=5,
    last_clip_count_box=None,
    healthy_mono_polls_box=None,
):
    if last_clip_count_box is None:
        last_clip_count_box = [0]
    if healthy_mono_polls_box is None:
        healthy_mono_polls_box = [0]

    result = await mcu.request("GET", "/api/audio")
    cap = result.data.get("capture", {})
    L = int(cap.get("left_peak", 0))
    R = int(cap.get("right_peak", 0))
    clip_count = int(cap.get("clip_count", 0))
    signal_state = str(cap.get("signal_state", ""))
    dc_offset = int(cap.get("dc_offset", 0))
    detected = int(cap.get("detected_channels", 0))

    clip_delta = max(0, clip_count - last_clip_count_box[0])
    last_clip_count_box[0] = clip_count

    metrics = {
        "profile": cap.get("profile"),
        "left_peak": L,
        "right_peak": R,
        "signal_state": signal_state,
        "clip_delta": clip_delta,
        "clip_count_total": clip_count,
        "dc_offset": dc_offset,
        "detected_channels": detected,
    }

    warn_reasons = []
    if signal_state == "clipped":
        warn_reasons.append("signal_state_clipped")
    if clip_delta >= clip_burst_threshold:
        warn_reasons.append(f"clip_burst:{clip_delta}")

    current = voice_loop.esp32_mic_profile

    # ── Stereo mode ──
    if current.endswith("stereo"):
        left_ok, right_ok, bad_reasons = True, True, []

        if L < silence_threshold and R >= silence_threshold:
            left_ok = False
            bad_reasons.append("left_channel_silent")
        elif R < silence_threshold and L >= silence_threshold:
            right_ok = False
            bad_reasons.append("right_channel_silent")
        elif L < silence_threshold and R < silence_threshold:
            left_ok = False
            right_ok = False
            bad_reasons.append("both_channels_below_threshold")

        if left_ok and right_ok and L > 0 and R > 0:
            ratio = max(L, R) / min(L, R)
            if ratio >= ratio_threshold:
                if L > R:
                    right_ok = False
                    bad_reasons.append(f"right_peak_weak:ratio={ratio:.1f}")
                else:
                    left_ok = False
                    bad_reasons.append(f"left_peak_weak:ratio={ratio:.1f}")

        if not bad_reasons:
            entry = {"status": "ok", **metrics}
            if warn_reasons:
                entry = {"status": "warning", "reason": "|".join(warn_reasons), "action": "no_switch", **metrics}
            event_log.append("esp32_audio_health", entry)
            return

        all_reasons = bad_reasons + warn_reasons
        if left_ok and not right_ok:
            target, verdict = MONO_L, "left_healthy_right_bad"
        elif right_ok and not left_ok:
            target, verdict = MONO_R, "right_healthy_left_bad"
        else:
            event_log.append("esp32_audio_health", {
                "status": "warning", "reason": "|".join(all_reasons), "action": "no_switch", **metrics
            })
            return

        healthy_mono_polls_box[0] = 0
        entry = {
            "status": "auto_switch",
            "from_profile": current,
            "to_profile": target,
            "reason": "|".join(all_reasons),
            "channel_verdict": verdict,
            **metrics,
        }
        event_log.append("esp32_audio_health_auto_switch", entry)
        voice_loop.esp32_mic_profile = target
        asyncio.ensure_future(voice_loop.restart())
        return

    # ── Mono mode ──
    both_ok = L >= silence_threshold and R >= silence_threshold

    if both_ok:
        healthy_mono_polls_box[0] += 1
        if healthy_mono_polls_box[0] >= restore_threshold_polls:
            healthy_mono_polls_box[0] = 0
            entry = {
                "status": "auto_switch",
                "from_profile": current,
                "to_profile": STEREO,
                "reason": f"both_channels_recovered:{restore_threshold_polls}_consecutive_polls",
                **metrics,
            }
            event_log.append("esp32_audio_health_auto_switch", entry)
            voice_loop.esp32_mic_profile = STEREO
            asyncio.ensure_future(voice_loop.restart())
        else:
            event_log.append("esp32_audio_health", {
                "status": "ok",
                "action": f"waiting_restore:{healthy_mono_polls_box[0]}/{restore_threshold_polls}",
                **metrics,
            })
        return

    # Not both OK — check active channel
    healthy_mono_polls_box[0] = 0
    if current == MONO_L:
        active_ok = L >= silence_threshold
        fallback = MONO_R if R >= silence_threshold else None
        bad_ch_reason = "left_channel_silent_while_in_mono_L"
    else:
        active_ok = R >= silence_threshold
        fallback = MONO_L if L >= silence_threshold else None
        bad_ch_reason = "right_channel_silent_while_in_mono_R"

    if active_ok:
        entry = {"status": "ok", **metrics}
        if warn_reasons:
            entry = {"status": "warning", "reason": "|".join(warn_reasons), "action": "no_switch", **metrics}
        event_log.append("esp32_audio_health", entry)
        return

    if fallback is None:
        event_log.append("esp32_audio_health", {
            "status": "degraded",
            "reason": bad_ch_reason,
            "action": "no_fallback_both_channels_silent",
            **metrics,
        })
        return

    event_log.append("esp32_audio_health_auto_switch", {
        "status": "auto_switch",
        "from_profile": current,
        "to_profile": fallback,
        "reason": bad_ch_reason,
        **metrics,
    })
    voice_loop.esp32_mic_profile = fallback
    asyncio.ensure_future(voice_loop.restart())


def mk(L=500, R=500, clips=0, sig="ok", profile=STEREO):
    vl = FakeVoiceLoop(profile)
    el = FakeEventLog()
    cap = {
        "left_peak": L, "right_peak": R, "clip_count": clips,
        "signal_state": sig, "dc_offset": 0, "detected_channels": 2, "profile": profile,
    }
    mcu = FakeMCU(cap)
    return vl, el, mcu


PASS_COUNT = 0
FAIL_COUNT = 0


def run_test(name, coro):
    global PASS_COUNT, FAIL_COUNT
    try:
        asyncio.run(coro)
        print(f"  PASS  {name}")
        PASS_COUNT += 1
    except AssertionError as e:
        print(f"  FAIL  {name}: {e}")
        FAIL_COUNT += 1


# ─────────────────────────────────────────────────────────────────────
# STEREO MODE TESTS
# ─────────────────────────────────────────────────────────────────────

async def t01():
    vl, el, mcu = mk(L=500, R=480)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == STEREO
    assert el.events[0][1]["status"] == "ok"

async def t02():
    vl, el, mcu = mk(L=5, R=500)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == MONO_R, f"got {vl.esp32_mic_profile}"
    assert el.events[0][0] == "esp32_audio_health_auto_switch"
    assert el.events[0][1]["channel_verdict"] == "right_healthy_left_bad"

async def t03():
    vl, el, mcu = mk(L=500, R=5)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == MONO_L, f"got {vl.esp32_mic_profile}"
    assert el.events[0][1]["channel_verdict"] == "left_healthy_right_bad"

async def t04():
    vl, el, mcu = mk(L=3000, R=100)  # ratio=30, >> 6.0
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == MONO_L, f"got {vl.esp32_mic_profile}"
    assert "right_peak_weak" in el.events[0][1]["reason"]

async def t05():
    vl, el, mcu = mk(L=5, R=5)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == STEREO  # can't determine which is bad
    assert el.events[0][1]["status"] == "warning"
    assert el.events[0][1]["action"] == "no_switch"
    assert "both_channels_below_threshold" in el.events[0][1]["reason"]

async def t06():
    vl, el, mcu = mk(L=500, R=480, sig="clipped")
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == STEREO
    assert el.events[0][1]["status"] == "warning"
    assert "signal_state_clipped" in el.events[0][1]["reason"]


# ─────────────────────────────────────────────────────────────────────
# MONO MODE TESTS
# ─────────────────────────────────────────────────────────────────────

async def t07():
    # 4 polls below threshold → still mono; 5th → restore stereo
    vl, el, mcu = mk(L=400, R=350, profile=MONO_L)
    box, hbox = [0], [0]
    for i in range(4):
        el.events.clear()
        await do_check(vl, el, mcu, restore_threshold_polls=5,
                       last_clip_count_box=box, healthy_mono_polls_box=hbox)
        assert vl.esp32_mic_profile == MONO_L, f"switched too early at poll {i+1}"
        assert el.events[0][1]["status"] == "ok"
    el.events.clear()
    await do_check(vl, el, mcu, restore_threshold_polls=5,
                   last_clip_count_box=box, healthy_mono_polls_box=hbox)
    assert vl.esp32_mic_profile == STEREO, f"expected stereo, got {vl.esp32_mic_profile}"
    assert el.events[0][0] == "esp32_audio_health_auto_switch"
    assert "both_channels_recovered" in el.events[0][1]["reason"]
    assert hbox[0] == 0, "counter should reset after restore"

async def t08():
    # 3 good polls accumulate counter, then L dies → switch to mono_R + counter reset
    vl, el, mcu = mk(L=400, R=350, profile=MONO_L)
    box, hbox = [0], [0]
    for _ in range(3):
        await do_check(vl, el, mcu, restore_threshold_polls=5,
                       last_clip_count_box=box, healthy_mono_polls_box=hbox)
    assert hbox[0] == 3
    mcu.cap["left_peak"] = 5
    el.events.clear()
    await do_check(vl, el, mcu, restore_threshold_polls=5,
                   last_clip_count_box=box, healthy_mono_polls_box=hbox)
    assert vl.esp32_mic_profile == MONO_R, f"expected mono_R, got {vl.esp32_mic_profile}"
    assert hbox[0] == 0, f"counter should reset, got {hbox[0]}"

async def t09():
    # mono_L, L active and ok, R silent → no switch (R is inactive)
    vl, el, mcu = mk(L=400, R=5, profile=MONO_L)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == MONO_L
    assert el.events[0][1]["status"] == "ok"

async def t10():
    # mono_L, both dead → degraded, nowhere to switch
    vl, el, mcu = mk(L=5, R=5, profile=MONO_L)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == MONO_L
    assert el.events[0][1]["action"] == "no_fallback_both_channels_silent"

async def t11():
    # mono_R, R active and ok, L silent → no switch (L is inactive)
    vl, el, mcu = mk(L=5, R=400, profile=MONO_R)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == MONO_R
    assert el.events[0][1]["status"] == "ok"

async def t12():
    # mono_R, active R dies, L ok → switch to mono_L
    vl, el, mcu = mk(L=400, R=5, profile=MONO_R)
    await do_check(vl, el, mcu)
    assert vl.esp32_mic_profile == MONO_L, f"got {vl.esp32_mic_profile}"
    assert el.events[0][0] == "esp32_audio_health_auto_switch"


# ─────────────────────────────────────────────────────────────────────

print()
print("=== STEREO MODE ===")
run_test("stereo + both ok -> status:ok, no switch", t01())
run_test("stereo + L silent -> switch to mono_R", t02())
run_test("stereo + R silent -> switch to mono_L", t03())
run_test("stereo + R weak (ratio>6) -> switch to mono_L", t04())
run_test("stereo + both silent -> warning, no switch", t05())
run_test("stereo + clipping -> log warning, no switch", t06())

print()
print("=== MONO MODE ===")
run_test("mono_L + both ok x5 -> restore to stereo", t07())
run_test("mono_L: 3 good polls then L dies -> switch mono_R + counter reset", t08())
run_test("mono_L + inactive R silent -> ok, no switch", t09())
run_test("mono_L + both dead -> degraded, no fallback", t10())
run_test("mono_R + inactive L silent -> ok, no switch", t11())
run_test("mono_R + active R dies, L ok -> switch to mono_L", t12())

print()
print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
sys.exit(FAIL_COUNT)
