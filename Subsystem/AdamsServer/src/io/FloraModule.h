#pragma once

#include <Arduino.h>

// Technoflora animation engine (Phase 29, FLORA-01).
//
// A dedicated FreeRTOS task drives the PCA9685 light cluster (channels 0-10)
// and vibro motors (channels 11-14) with smooth ~50 Hz animation, independent
// of the 4 Hz main loop(). Presets are swapped at runtime via setFloraState()
// (called from the /api/flora/state HTTP handler) and crossfaded over
// crossfade_ms. The firmware boots into a quiet autonomous preset so the
// installation is never dark or test_all-glaring before the Jetson connects.

// Optional per-preset parameter overrides. Any field left as the sentinel
// value (UINT16_MAX for duties/periods, -1 for vibroEnabled) keeps the
// firmware default for that preset. Channels/duties are clamped on apply.
struct FloraParams {
  uint16_t baseDuty = UINT16_MAX;     // 0-4095, low brightness floor
  uint16_t peakDuty = UINT16_MAX;     // 0-4095, animation peak
  uint32_t periodMs = 0;              // breathing/animation period (0 = keep)
  uint32_t crossfadeMs = 0;           // 0 = keep firmware default
  int8_t   vibroEnabled = -1;         // -1 keep, 0 force off, 1 enable
  uint16_t vibroDuty = UINT16_MAX;    // 0-4095 vibro amplitude (clamped to ceiling)
};

// Start the animation FreeRTOS task. Call once from setup() after
// initPca9685() succeeds. Idempotent: a second call is a no-op.
void startFloraTask();

// Swap the active preset. Returns false for an unknown preset name (the HTTP
// handler maps that to a 400). Thread-safe: writes a mutex-guarded target the
// animation task picks up on its next tick.
bool setFloraState(const char *preset, const FloraParams &params);
