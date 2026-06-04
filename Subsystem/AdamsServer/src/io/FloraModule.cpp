#include "FloraModule.h"

#include <cmath>
#include <cstring>

#include "../../config/AdamsConfig.h"
#include "../core/RuntimeState.h"
#include "Pca9685Module.h"

// Technoflora animation engine (Phase 29, FLORA-01).
//
// A static FreeRTOS task ticks at ~50 Hz (kFloraTickMs), runs a preset state
// machine, applies a precomputed gamma LUT, crossfades from the last-written
// duties to the new preset over crossfade_ms, and writes one atomic 16-channel
// frame per tick via writeAllChannelsRaw. Light = ch 0-10, vibro = ch 11-14.
// Vibro is hard-zeroed whenever the active preset is `attentive` (D-11:
// protects the INMP441 mic from motor->mic acoustic coupling during listening).

namespace {

// --- FreeRTOS task storage (mirrors SensorModule.cpp static-task pattern) ---
StaticTask_t sFloraTaskBuffer;
StackType_t  sFloraTaskStack[4096];
bool         sFloraTaskStarted = false;

// --- Preset identifiers --------------------------------------------------
enum class FloraPreset : uint8_t {
  Idle = 0,     // firmware boot default: quiet, never dark, never test_all glare
  Breathe,      // покой — slow collective sine
  Accent,       // детекция — single fast attack to peak then settle
  Attentive,    // слушание — bright plateau, vibro forced 0 (D-11)
  ThinkPulse,   // раздумье — low base + wandering random-subset flashes (D-01)
  WakeBloom,    // пробуждение — random sprout from dark -> collective inhale -> breathe
};

struct PresetDefaults {
  const char *name;
  uint16_t    baseDuty;
  uint16_t    peakDuty;
  uint32_t    periodMs;
  bool        vibroEnabled;
};

// In-code preset defaults (Jetson params override per-call). Duties are 0-4095
// pre-gamma "levels" expressed directly in 12-bit space for the base/peak
// anchors; the gamma LUT shapes the interpolation between them.
constexpr PresetDefaults kPresetDefaults[] = {
  // name           base  peak  periodMs  vibro
  {"idle",          120,   900,  9000,    false},
  {"breathe",       120,  1100,  7000,    false},
  {"accent",        400,  3000,  1400,    true },
  {"attentive",     0,    1600,  4000,    false},   // vibro forced off regardless
  {"think_pulse",   600,  2600,  1750,    true },
  {"wake_bloom",    0,    3200,  3000,    true },
};
constexpr size_t kPresetCount = sizeof(kPresetDefaults) / sizeof(kPresetDefaults[0]);

// --- Gamma LUT (Pattern 3): map a 0..255 animation level to a 12-bit duty ---
// duty = round(4095 * (level/255)^gamma). Filled once at init; NO pow() in the
// per-frame path (50 Hz x 16 ch = 800 pow()/s would be wasteful on the ESP).
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

// Apply the gamma LUT to a 0..4095 linear animation duty. The LUT is indexed by
// a 0..255 level, so we downscale to 8-bit, look up, and the table already
// yields a 12-bit gamma-corrected duty.
inline uint16_t gammaApply(uint16_t linearDuty) {
  const uint8_t level = static_cast<uint8_t>((min<uint16_t>(4095, linearDuty) * 255U) / 4095U);
  return sGammaLut[level];
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
      // Bright steady plateau (no breathing) so the listener reads "I'm hearing you".
      return peak;
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
  }
  return base;
}

// One animation frame: fill duties[16] for this tick.
void floraTick(uint32_t nowMs) {
  // Snapshot target under the mux (cheap copy of POD fields).
  portENTER_CRITICAL(&gRuntimeStateMux);
  const FloraTarget t = sTarget;
  portEXIT_CRITICAL(&gRuntimeStateMux);

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
    if (t.preset == FloraPreset::ThinkPulse) {
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

  return true;
}
