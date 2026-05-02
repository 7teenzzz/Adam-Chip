#include "SystemSoundModule.h"

#include <cmath>
#include <cstring>

#include <pgmspace.h>

#include "../../config/AdamsConfig.h"
#include "AudioModule.h"
#include "SystemSoundData.h"
#include "../core/BootDiagnostics.h"
#include "../core/RuntimeState.h"

namespace {

constexpr size_t kSoundChunkBytes = 1024;
constexpr uint32_t kWriteRetryDelayMs = 4;
constexpr uint32_t kWriteRetryLimit = 250;
constexpr uint32_t kToneStepDurationMs = 1000;
constexpr uint32_t kToneGapDurationMs = 120;
constexpr float kToneAmplitude = 22000.0f;
constexpr float kTwoPi = 6.28318530718f;
constexpr float kToneFrequenciesHz[] = {110.0f, 165.0f, 220.0f, 330.0f, 440.0f, 660.0f, 880.0f};

bool sSoundsReady = false;

const char *pathForSound(const char *name) {
  if (name == nullptr) {
    return nullptr;
  }
  if (strcmp(name, "boot") == 0) {
    return "boot";
  }
  if (strcmp(name, "success") == 0) {
    return "success";
  }
  if (strcmp(name, "tone") == 0) {
    return "tone";
  }
  return nullptr;
}

size_t soundBytesForPath(const char *path) {
  if (path == nullptr) {
    return 0;
  }
  if (strcmp(path, "boot") == 0) {
    return kBootSoundPcmLen;
  }
  if (strcmp(path, "success") == 0) {
    return kSuccessSoundPcmLen;
  }
  if (strcmp(path, "tone") == 0) {
    const size_t toneSamples = (static_cast<size_t>(kSpeakerSampleRate) * kToneStepDurationMs) / 1000;
    const size_t gapSamples = (static_cast<size_t>(kSpeakerSampleRate) * kToneGapDurationMs) / 1000;
    const size_t toneCount = sizeof(kToneFrequenciesHz) / sizeof(kToneFrequenciesHz[0]);
    return ((toneSamples * toneCount) + (gapSamples * (toneCount - 1))) * sizeof(int16_t);
  }
  return 0;
}

void recordSoundState(const char *name, const char *result, size_t bytes, bool incrementRequestCount) {
  portENTER_CRITICAL(&gRuntimeStateMux);
  if (name != nullptr) {
    strncpy(gRuntimeState.lastSoundName, name, sizeof(gRuntimeState.lastSoundName) - 1);
    gRuntimeState.lastSoundName[sizeof(gRuntimeState.lastSoundName) - 1] = '\0';
  }
  if (result != nullptr) {
    strncpy(gRuntimeState.lastSoundResult, result, sizeof(gRuntimeState.lastSoundResult) - 1);
    gRuntimeState.lastSoundResult[sizeof(gRuntimeState.lastSoundResult) - 1] = '\0';
  }
  gRuntimeState.lastSoundBytes = static_cast<uint32_t>(bytes);
  if (incrementRequestCount) {
    gRuntimeState.soundPlayRequests = gRuntimeState.soundPlayRequests + 1;
    gRuntimeState.lastSoundStartedAtMs = millis();
  } else {
    gRuntimeState.lastSoundCompletedAtMs = millis();
  }
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

bool writeAllToSpeaker(const uint8_t *data, size_t len) {
  size_t offset = 0;
  uint32_t retries = 0;
  while (offset < len) {
    const size_t written = writeSpeakerData(data + offset, len - offset);
    if (written > 0) {
      offset += written;
      retries = 0;
      continue;
    }

    if (++retries > kWriteRetryLimit) {
      return false;
    }
    delay(kWriteRetryDelayMs);
  }
  return true;
}

bool streamSilenceToSpeaker(uint32_t durationMs) {
  int16_t samples[kSoundChunkBytes / sizeof(int16_t)] = {};
  const size_t totalSamples = (static_cast<size_t>(kSpeakerSampleRate) * durationMs) / 1000;
  size_t sampleIndex = 0;

  while (sampleIndex < totalSamples) {
    const size_t samplesToWrite = min(sizeof(samples) / sizeof(samples[0]), totalSamples - sampleIndex);
    if (!writeAllToSpeaker(reinterpret_cast<const uint8_t *>(samples), samplesToWrite * sizeof(samples[0]))) {
      return false;
    }
    sampleIndex += samplesToWrite;
  }

  return true;
}

bool streamBootSoundToSpeaker() {
  uint8_t buffer[kSoundChunkBytes];
  size_t offset = 0;

  while (offset < kBootSoundPcmLen) {
    const size_t bytesToCopy = min(kSoundChunkBytes, kBootSoundPcmLen - offset);
    memcpy_P(buffer, kBootSoundPcm + offset, bytesToCopy);
    if (!writeAllToSpeaker(buffer, bytesToCopy)) {
      return false;
    }
    offset += bytesToCopy;
  }

  return true;
}

bool streamSuccessSoundToSpeaker() {
  uint8_t buffer[kSoundChunkBytes];
  size_t offset = 0;

  while (offset < kSuccessSoundPcmLen) {
    const size_t bytesToCopy = min(kSoundChunkBytes, kSuccessSoundPcmLen - offset);
    memcpy_P(buffer, kSuccessSoundPcm + offset, bytesToCopy);
    if (!writeAllToSpeaker(buffer, bytesToCopy)) {
      return false;
    }
    offset += bytesToCopy;
  }

  return true;
}

bool streamDiagnosticToneToSpeaker() {
  int16_t samples[kSoundChunkBytes / sizeof(int16_t)];
  const size_t toneCount = sizeof(kToneFrequenciesHz) / sizeof(kToneFrequenciesHz[0]);
  const size_t totalSamplesPerTone = (static_cast<size_t>(kSpeakerSampleRate) * kToneStepDurationMs) / 1000;

  for (size_t toneIndex = 0; toneIndex < toneCount; ++toneIndex) {
    const float frequencyHz = kToneFrequenciesHz[toneIndex];
    size_t sampleIndex = 0;

    while (sampleIndex < totalSamplesPerTone) {
      const size_t samplesToWrite = min(sizeof(samples) / sizeof(samples[0]), totalSamplesPerTone - sampleIndex);
      for (size_t i = 0; i < samplesToWrite; ++i) {
        const float phase = kTwoPi * frequencyHz * static_cast<float>(sampleIndex + i) / static_cast<float>(kSpeakerSampleRate);
        samples[i] = static_cast<int16_t>(lroundf(sinf(phase) * kToneAmplitude));
      }

      if (!writeAllToSpeaker(reinterpret_cast<const uint8_t *>(samples), samplesToWrite * sizeof(samples[0]))) {
        return false;
      }
      sampleIndex += samplesToWrite;
    }

    if (toneIndex + 1 < toneCount && !streamSilenceToSpeaker(kToneGapDurationMs)) {
      return false;
    }
  }

  return true;
}

}  // namespace

bool initSystemSounds() {
  if (sSoundsReady) {
    return true;
  }

  sSoundsReady = true;
  bootLogf(
    "sounds",
    "embedded sounds ready, boot=%lu success=%lu bytes",
    static_cast<unsigned long>(kBootSoundPcmLen),
    static_cast<unsigned long>(kSuccessSoundPcmLen));
  return true;
}

bool playSystemSound(const char *name) {
  if (!sSoundsReady && !initSystemSounds()) {
    return false;
  }

  const char *path = pathForSound(name);
  if (path == nullptr) {
    recordSoundState(name == nullptr ? "null" : name, "unknown", 0, true);
    recordSoundState(name == nullptr ? "null" : name, "unknown", 0, false);
    bootLogf("sounds", "unknown sound: %s", name == nullptr ? "null" : name);
    return false;
  }

  const size_t expectedBytes = soundBytesForPath(path);
  recordSoundState(path, "started", expectedBytes, true);

  if (!beginSpeakerStream()) {
    recordSoundState(path, "busy", expectedBytes, false);
    bootLogf("sounds", "speaker busy, skipped: %s", path);
    return false;
  }

  bool ok = false;
  if (strcmp(path, "boot") == 0) {
    ok = streamBootSoundToSpeaker();
  } else if (strcmp(path, "success") == 0) {
    ok = streamSuccessSoundToSpeaker();
  } else if (strcmp(path, "tone") == 0) {
    ok = streamDiagnosticToneToSpeaker();
  }
  endSpeakerStream();
  recordSoundState(path, ok ? "played" : "failed", expectedBytes, false);

  bootLogf("sounds", "%s %s", path, ok ? "played" : "failed");
  return ok;
}
