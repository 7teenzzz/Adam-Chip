#include "FloraModule.h"

#include <cmath>
#include <cstring>

#include "../../config/AdamsConfig.h"
#include "../core/RuntimeState.h"
#include "Pca9685Module.h"

// Technoflora animation engine (Phase 29, FLORA-01; Phase 30 R5/R6/R3/R4/D-03).
//
// A static FreeRTOS task ticks at ~50 Hz (kFloraTickMs), runs a preset state
// machine, crossfades from the last-written duties to the new preset over
// crossfade_ms, and writes one atomic 16-channel frame per tick via
// writeAllChannelsRaw. Light = ch 0-10, vibro = ch 11-14.
// Phase 30 R5 (decision A): raw PWM, no perceptual gamma. The Jetson already
// sends raw pct->duty values (linear), so gammaApply is now an identity pass-
// through. The gamma LUT (sGammaLut/buildGammaLut) is retained but unused.
// Vibro is hard-zeroed whenever the active preset is `attentive` (D-11:
// protects the INMP441 mic from motor->mic acoustic coupling during listening).

namespace {

// --- FreeRTOS task storage (mirrors SensorModule.cpp static-task pattern) ---
StaticTask_t sFloraTaskBuffer;
StackType_t  sFloraTaskStack[4096];
bool         sFloraTaskStarted = false;
// C7: honor flora.enabled. Set via setFloraState params.enabled. When false the
// animation task does not drive the channels at all (external/manual control wins).
volatile bool sFloraEnabled = true;

// --- Preset identifiers --------------------------------------------------
enum class FloraPreset : uint8_t {
  Idle = 0,     // firmware boot default: quiet, never dark, never test_all glare
  Breathe,      // покой — slow collective sine
  Accent,       // детекция — single fast attack to peak then settle
  Attentive,    // слушание — bright plateau, vibro forced 0 (D-11)
  ThinkPulse,   // раздумье — low base + wandering random-subset flashes (D-01)
  WakeBloom,    // пробуждение — random sprout from dark -> collective inhale -> breathe
  External,     // ответ/calibration — animation suppressed; floraTask yields to
                // external /api/pca9685/* writes (RMS stream). Watchdog -> attentive (Phase 30 R3).
};

struct PresetDefaults {
  const char *name;
  uint16_t    baseDuty;
  uint16_t    peakDuty;
  uint32_t    periodMs;
  bool        vibroEnabled;
};

// In-code preset defaults (Jetson params override per-call). Duties are raw
// 0-4095 12-bit PWM values (Phase 30 R5/decision A: no gamma shaping — linear
// pct->duty mapping, identical to what the Jetson sends). The base/peak anchors
// are the direct animation floor/ceiling in raw PWM.
// Brightness ceiling: 71% of 4095 = 2908. No preset peak exceeds this.
constexpr uint16_t kFlora71PctDuty = 2908u;

constexpr PresetDefaults kPresetDefaults[] = {
  // name           base  peak          periodMs  vibro
  // Phase 30 R6/D-08: idle base raised to 400 (~10%) so the resting state is
  // clearly lit even without gamma. Was 120 (~3%) which read as nearly off.
  {"idle",          400,   900,          9000,    false},
  {"breathe",       287,  2908,          4000,    false},  // base=7%, peak=71%, 4s (matches Config flora.states.breathe)
  {"accent",        400,  kFlora71PctDuty, 1400,  true },  // peak capped at 71%
  {"attentive",    1228,  kFlora71PctDuty,  450,  false},  // base=30%, peak=71%, wave period 450ms
  {"think_pulse",   819,  2600,          1750,    true },  // base=20%
  {"wake_bloom",    0,    kFlora71PctDuty, 3000,  true },  // peak capped at 71%
  {"external",      0,    0,               1000,  false},  // suppressed; floraTick yields to HTTP writes
};
constexpr size_t kPresetCount = sizeof(kPresetDefaults) / sizeof(kPresetDefaults[0]);

// --- Gamma LUT (retained but UNUSED by the light path, Phase 30 R5/decision A) ---
// The LUT was used to apply a perceptual gamma correction (kFloraGamma=2.2) to
// the raw duty values. As of Phase 30, the Jetson already sends raw pct->duty
// values (linear), so applying gamma again would halve the perceived brightness.
// gammaApply is now an identity pass-through at full 12-bit resolution.
// buildGammaLut is still called at init to keep the code path consistent, but
// the table is not read in any per-frame operation.
uint16_t sGammaLut[256];
bool     sGammaLutReady = false;

void buildGammaLut() {
  for (int level = 0; level < 256; ++level) {
    const float norm = static_cast<float>(level) / 255.0f;
    const float duty = roundf(4095.0f * powf(norm, kFloraGamma));
    sGammaLut[level] = static_cast<uint16_t>(constrain(duty, 0.0f, 4095.0f));
  }
  sGammaLutReady = true;
}

// Phase 30 R5 (decision A): raw PWM, no perceptual gamma.
// gammaApply is now a full 12-bit identity: it clamps to 4095 and returns the
// input unchanged. The old LUT lookup (which quantised to 8-bit and applied
// gamma-2.2) is removed. This eliminates the double-gamma that was halving
// apparent brightness (Jetson pct->duty is already linear).
// kFloraGamma in AdamsConfig.h is now unused by the light path.
inline uint16_t gammaApply(uint16_t linearDuty) {
  return min<uint16_t>(4095, linearDuty);
}

// --- Mutex-guarded target state (Pattern 2) ------------------------------
// The HTTP handler (setFloraState) writes sTarget; the task reads it each tick.
// Reuses the project-wide gRuntimeStateMux (portMUX_TYPE).
struct FloraTarget {
  FloraPreset preset = FloraPreset::Idle;
  uint16_t    baseDuty = kPresetDefaults[0].baseDuty;
  uint16_t    peakDuty = kPresetDefaults[0].peakDuty;
  uint32_t    periodMs = kPresetDefaults[0].periodMs;
  uint32_t    crossfadeMs = kFloraDefaultCrossfadeMs;
  bool        vibroEnabled = false;
  uint16_t    vibroDuty = kFloraVibroIntensityCeiling;
  uint32_t    appliedAtMs = 0;   // millis() when this target became active (crossfade start)
};

FloraTarget sTarget;

// Crossfade snapshot: the duties that were on the lamps the instant the target
// changed. The task interpolates from these toward the freshly-computed frame
// over crossfade_ms. Captured from gRuntimeState.pca9685Channels[] on switch.
uint16_t sCrossfadeFrom[16] = {0};

// PRNG state for random-subset effects (think_pulse / wake_bloom). esp_random()
// is available but a tiny xorshift keeps the per-frame path allocation-free and
// deterministic enough for visual flicker.
uint32_t sRngState = 0x9E3779B9u;
inline uint32_t nextRand() {
  sRngState ^= sRngState << 13;
  sRngState ^= sRngState >> 17;
  sRngState ^= sRngState << 5;
  return sRngState;
}

bool presetFromName(const char *name, FloraPreset &out) {
  if (name == nullptr) return false;
  for (size_t i = 0; i < kPresetCount; ++i) {
    if (strcmp(name, kPresetDefaults[i].name) == 0) {
      out = static_cast<FloraPreset>(i);
      return true;
    }
  }
  return false;
}

// Compute the light envelope (0..4095 linear, pre-gamma) for the active preset
// at the given phase. Phase is 0..1 over periodMs. Returns a single collective
// level; per-channel scatter (think_pulse flashes) is applied separately.
uint16_t computeLightLevel(FloraPreset preset, uint16_t base, uint16_t peak,
                           float phase, uint32_t elapsedMs, uint32_t periodMs) {
  const float span = static_cast<float>(peak) - static_cast<float>(base);
  switch (preset) {
    case FloraPreset::Breathe:
    case FloraPreset::Idle: {
      // Slow collective sine inhale/exhale.
      const float s = 0.5f * (1.0f - cosf(phase * 2.0f * static_cast<float>(M_PI)));
      return static_cast<uint16_t>(base + span * s);
    }
    case FloraPreset::Accent: {
      // Fast attack to peak in the first ~20% of the period, then settle back.
      const float attack = 0.20f;
      float s;
      if (phase < attack) {
        s = phase / attack;
      } else {
        s = 1.0f - ((phase - attack) / (1.0f - attack));
      }
      s = constrain(s, 0.0f, 1.0f);
      return static_cast<uint16_t>(base + span * s);
    }
    case FloraPreset::Attentive: {
      // Per-channel fast waves; collective level is computed per-channel in floraTick.
      // Return base as the floor reference only.
      return base;
    }
    case FloraPreset::ThinkPulse: {
      // Low collective base; per-channel wandering flashes added in the frame loop.
      return base;
    }
    case FloraPreset::WakeBloom: {
      // From dark: a single collective inhale up to peak across the period.
      const float s = constrain(phase, 0.0f, 1.0f);
      return static_cast<uint16_t>(base + span * s);
    }
    case FloraPreset::External: {
      // Unused — floraTick returns before computing levels for External.
      return base;
    }
  }
  return base;
}

// One animation frame: fill duties[16] for this tick.
void floraTick(uint32_t nowMs) {
  // C7: honor flora.enabled — when disabled the task must not drive the channels
  // (let external/manual control stand).
  if (!sFloraEnabled) {
    return;
  }

  // Snapshot target under the mux (cheap copy of POD fields).
  portENTER_CRITICAL(&gRuntimeStateMux);
  const FloraTarget t = sTarget;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  // Part B: External preset — floraTask yields so the Jetson raw-frame stream
  // (RMS "ответ" effect / calibration) is not overwritten every 20 ms (fixes
  // C1/C2). Watchdog: if no external HTTP frame arrives for kFloraExternalTimeoutMs
  // (stream died), auto-recover to breathe so the lamps never freeze.
  if (t.preset == FloraPreset::External) {
    uint32_t lastExt;
    portENTER_CRITICAL(&gRuntimeStateMux);
    lastExt = gRuntimeState.lastExternalPcaWriteMs;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    const uint32_t ref = (lastExt != 0) ? lastExt : t.appliedAtMs;
    if ((nowMs - ref) <= kFloraExternalTimeoutMs) {
      return;  // external writer is live — let its frames stand
    }
    // Stale: recover to Attentive (steady plateau) instead of Breathe.
    // Phase 30 R3/D-06: External is only entered during Adam's spoken answer.
    // On the degraded /speak path (no WAV/RMS stream), the lamps should hold a
    // steady lit plateau — not breathe — so the installation never looks like
    // Adam is idling while he's actually speaking.
    // R4/D-07: The watchdog cannot fire before kFloraExternalTimeoutMs from entry
    // because setFloraState(External) resets lastExternalPcaWriteMs to millis(),
    // so (nowMs - ref) starts at 0 and grows; the guard `<= kFloraExternalTimeoutMs`
    // ensures the full grace window is always honoured.
    const PresetDefaults &ad = kPresetDefaults[static_cast<size_t>(FloraPreset::Attentive)];
    portENTER_CRITICAL(&gRuntimeStateMux);
    for (uint8_t ch = 0; ch < 16; ++ch) {
      sCrossfadeFrom[ch] = gRuntimeState.pca9685Channels[ch];
    }
    sTarget.preset = FloraPreset::Attentive;
    sTarget.baseDuty = ad.baseDuty;
    sTarget.peakDuty = ad.peakDuty;
    sTarget.periodMs = ad.periodMs;
    sTarget.vibroEnabled = false;  // Attentive always mutes vibro (D-11)
    sTarget.appliedAtMs = nowMs;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    return;  // next tick renders attentive (steady plateau)
  }

  const uint32_t periodMs = (t.periodMs == 0) ? 1 : t.periodMs;
  const uint32_t sinceApplied = nowMs - t.appliedAtMs;
  const float phase = static_cast<float>(sinceApplied % periodMs) / static_cast<float>(periodMs);

  // Collective light level (linear, pre-gamma).
  const uint16_t linearLevel =
      computeLightLevel(t.preset, t.baseDuty, t.peakDuty, phase, sinceApplied, periodMs);
  const uint16_t lightDuty = gammaApply(linearLevel);

  uint16_t duties[16] = {0};

  // --- Light channels 0-10 (D-02) ---
  for (uint8_t ch = kFloraLightChannelLo; ch <= kFloraLightChannelHi; ++ch) {
    uint16_t d = lightDuty;
    if (t.preset == FloraPreset::Attentive) {
      // Fast independent per-channel sine waves (user req: быстрые волны на
      // случайных каналах). Each channel runs at a phase offset = ch * 173
      // (prime) so all 11 lamps oscillate visibly out of sync — reads as organic
      // shimmer, not collective breathing. Wave period comes from t.periodMs
      // (Jetson sends wave_period_ms -> period_ms, default 450 ms ≈ 2.2 Hz).
      const uint32_t wavePeriod = (t.periodMs > 0) ? t.periodMs : 450u;
      const uint32_t phaseOff   = static_cast<uint32_t>(ch) * 173u;
      const float cp = static_cast<float>((sinceApplied + phaseOff) % wavePeriod)
                       / static_cast<float>(wavePeriod);
      const float s = 0.5f * (1.0f - cosf(cp * 2.0f * static_cast<float>(M_PI)));
      d = gammaApply(static_cast<uint16_t>(
          static_cast<float>(t.baseDuty) +
          static_cast<float>(t.peakDuty - t.baseDuty) * s));
    } else if (t.preset == FloraPreset::ThinkPulse) {
      // D-01: wandering random-subset flashes (no spatial order). Each tick a
      // small random subset of channels gets boosted toward peak.
      if ((nextRand() & 0x1F) == 0) {  // ~1/32 channels flare per tick
        d = gammaApply(t.peakDuty);
      }
    } else if (t.preset == FloraPreset::WakeBloom) {
      // D-01: random sprouting from dark — channels light in random order as the
      // collective inhale rises, so it reads as "blooming" not a directional wave.
      const float sprout = static_cast<float>(nextRand() & 0xFF) / 255.0f;
      if (sprout > phase) {
        d = gammaApply(t.baseDuty);
      }
    }
    duties[ch] = d;
  }

  // --- Vibro channels 11-14 (D-11 / D-12 / FLORA-06) ---
  // Belt-and-suspenders: force vibro to 0 whenever preset==attentive regardless
  // of vibroEnabled, protecting ASR from motor->mic coupling.
  uint16_t vibroDuty = 0;
  if (t.preset != FloraPreset::Attentive && t.vibroEnabled) {
    // Vibro "follows the light": pulse amplitude tracks the breathing phase so
    // the motor presence is rhythmically tied to the lamps (D-11). Clamp to the
    // flora vibro ceiling (NOT safety.motor_* — D-04/FLORA-06).
    const float s = 0.5f * (1.0f - cosf(phase * 2.0f * static_cast<float>(M_PI)));
    const uint16_t ceiling = min<uint16_t>(kFloraVibroIntensityCeiling, t.vibroDuty);
    vibroDuty = static_cast<uint16_t>(ceiling * s);
  }
  for (uint8_t ch = kFloraVibroChannelLo; ch <= kFloraVibroChannelHi; ++ch) {
    duties[ch] = vibroDuty;
  }

  // --- Crossfade (D-09): interpolate from the snapshot toward this frame ---
  if (t.crossfadeMs > 0 && sinceApplied < t.crossfadeMs) {
    const float a = static_cast<float>(sinceApplied) / static_cast<float>(t.crossfadeMs);
    for (uint8_t ch = 0; ch < 16; ++ch) {
      const float from = static_cast<float>(sCrossfadeFrom[ch]);
      const float to = static_cast<float>(duties[ch]);
      duties[ch] = static_cast<uint16_t>(from + (to - from) * a);
    }
  }

  // Phase 30 D-03: safe-ceiling firmware clamp (defence-in-depth).
  // Clamp every channel to kFloraMaxDutyPct of full 12-bit scale before writing.
  // Mirrors Config.json flora.max_duty_pct — structural default duplicated
  // firmware-side. Ensures no animation frame exceeds the safe PWM cap regardless
  // of preset params, Jetson-side values, or floating-point rounding.
  {
    const uint16_t maxDuty = (4095u * kFloraMaxDutyPct) / 100u;
    for (uint8_t ch = 0; ch < 16; ++ch) {
      duties[ch] = min<uint16_t>(duties[ch], maxDuty);
    }
  }

  writeAllChannelsRaw(duties);
}

void floraTask(void *parameter) {
  (void)parameter;
  const TickType_t period = pdMS_TO_TICKS(kFloraTickMs);
  while (true) {
    floraTick(millis());
    vTaskDelay(period);
  }
}

}  // namespace

void startFloraTask() {
  if (sFloraTaskStarted) {
    return;
  }
  if (!sGammaLutReady) {
    buildGammaLut();
  }

  // Seed the crossfade snapshot and apply timestamp so the first frames fade in
  // from whatever the lamps currently show (typically the boot scene).
  portENTER_CRITICAL(&gRuntimeStateMux);
  for (uint8_t ch = 0; ch < 16; ++ch) {
    sCrossfadeFrom[ch] = gRuntimeState.pca9685Channels[ch];
  }
  sTarget.appliedAtMs = millis();
  portEXIT_CRITICAL(&gRuntimeStateMux);

  xTaskCreateStaticPinnedToCore(
    floraTask,
    "flora_task",
    sizeof(sFloraTaskStack) / sizeof(StackType_t),
    nullptr,
    1,                       // priority 1 — match sensorTask
    sFloraTaskStack,
    &sFloraTaskBuffer,
    APP_CPU_NUM
  );
  sFloraTaskStarted = true;
}

bool setFloraState(const char *preset, const FloraParams &params) {
  // C7: honor flora.enabled — can arrive with any preset (e.g. {"state":"breathe",
  // "enabled":false}). Applied even if the preset name is unknown below.
  if (params.enabled == 0) {
    sFloraEnabled = false;
  } else if (params.enabled == 1) {
    sFloraEnabled = true;
  }

  FloraPreset resolved;
  if (!presetFromName(preset, resolved)) {
    return false;
  }

  const PresetDefaults &def = kPresetDefaults[static_cast<size_t>(resolved)];

  // Resolve params: caller override (if provided) else preset default. Clamp
  // all duties to 0-4095 (T-29-02/T-29-03 mitigation).
  uint16_t base = (params.baseDuty != UINT16_MAX) ? params.baseDuty : def.baseDuty;
  uint16_t peak = (params.peakDuty != UINT16_MAX) ? params.peakDuty : def.peakDuty;
  base = min<uint16_t>(4095, base);
  peak = min<uint16_t>(4095, peak);

  uint32_t periodMs = (params.periodMs != 0) ? params.periodMs : def.periodMs;
  if (periodMs == 0) periodMs = 1;
  const uint32_t crossfadeMs = (params.crossfadeMs != 0) ? params.crossfadeMs : kFloraDefaultCrossfadeMs;

  bool vibroEnabled = def.vibroEnabled;
  if (params.vibroEnabled == 0) vibroEnabled = false;
  else if (params.vibroEnabled == 1) vibroEnabled = true;
  // Attentive ALWAYS mutes vibro regardless of request (D-11 belt-and-suspenders).
  if (resolved == FloraPreset::Attentive) {
    vibroEnabled = false;
  }

  uint16_t vibroDuty = (params.vibroDuty != UINT16_MAX) ? params.vibroDuty : kFloraVibroIntensityCeiling;
  vibroDuty = min<uint16_t>(kFloraVibroIntensityCeiling, vibroDuty);  // ceiling clamp (FLORA-06)

  portENTER_CRITICAL(&gRuntimeStateMux);
  // Capture the current duties as the crossfade start point (D-09).
  for (uint8_t ch = 0; ch < 16; ++ch) {
    sCrossfadeFrom[ch] = gRuntimeState.pca9685Channels[ch];
  }
  sTarget.preset = resolved;
  sTarget.baseDuty = base;
  sTarget.peakDuty = peak;
  sTarget.periodMs = periodMs;
  sTarget.crossfadeMs = crossfadeMs;
  sTarget.vibroEnabled = vibroEnabled;
  sTarget.vibroDuty = vibroDuty;
  sTarget.appliedAtMs = millis();
  portEXIT_CRITICAL(&gRuntimeStateMux);

  // Entering External resets the watchdog so the Jetson gets the full grace
  // window (kFloraExternalTimeoutMs) to start streaming frames before auto-recovery.
  if (resolved == FloraPreset::External) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.lastExternalPcaWriteMs = millis();
    portEXIT_CRITICAL(&gRuntimeStateMux);
  }

  return true;
}
