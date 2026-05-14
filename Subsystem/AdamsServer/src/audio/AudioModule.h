#pragma once

#include <Arduino.h>

struct AudioCaptureStatus {
  bool ready = false;
  char profile[32] = "";
  char format[12] = "";
  uint32_t sampleRate = 0;
  uint8_t pcmBits = 0;
  uint8_t pcmChannels = 0;
  uint8_t dataBits = 0;
  uint8_t slotBits = 0;
  uint8_t preferredSlot = 0;
  uint8_t sampleShift = 0;
  bool dcBlock = false;
  float softwareGain = 1.0f;
  uint32_t bufferBytes = 0;
  uint64_t writerSequence = 0;
  uint32_t lastSampleMs = 0;
  uint32_t lastNonZeroMs = 0;
  uint32_t recentActivityMs = 0;
  bool streamActive = false;
  uint32_t leftPeak = 0;
  uint32_t rightPeak = 0;
  uint32_t selectedPeak = 0;
  uint32_t averageLevel = 0;
  int32_t dcOffset = 0;
  float zeroCrossRate = 0.0f;
  uint32_t clipCount = 0;
  uint8_t detectedChannels = 0;
  char signalState[16] = "";
};

struct AudioPlaybackStatus {
  bool ready = false;
  bool clientActive = false;
  uint32_t bufferFill = 0;
  uint32_t underruns = 0;
  uint32_t overflows = 0;
};

struct AudioStatusSnapshot {
  AudioCaptureStatus capture;
  AudioPlaybackStatus playback;
};

struct AudioRuntimeUpdate {
  bool hasProfile = false;
  const char *profile = nullptr;
  bool hasSoftwareGain = false;
  float softwareGain = 1.0f;
  bool hasDcBlock = false;
  bool dcBlock = true;
  bool hasSlotOverride = false;
  uint8_t preferredSlot = 1;
  bool hasShiftOverride = false;
  uint8_t sampleShift = 0;
};

uint8_t getAudioOutputChannels();
bool initAudioCapture();
bool initSpeakerPlayback();
bool readAudioChunk(uint8_t *dst, size_t maxBytes, size_t &outBytes, uint64_t &cursor);
uint64_t getAudioWriteSequence();
uint32_t getAudioRingBufferBytes();
bool getAudioStatusSnapshot(AudioStatusSnapshot &snapshot);
bool applyAudioRuntimeUpdate(const AudioRuntimeUpdate &update);
size_t getAudioProfileCount();
bool getAudioProfileName(size_t index, char *dst, size_t dstSize);
size_t getAudioClipBytesForDurationMs(uint32_t durationMs);
bool copyRecentAudioClip(uint32_t durationMs, uint8_t *dst, size_t capacity, size_t &outBytes);
bool beginSpeakerStream();
void endSpeakerStream();
size_t writeSpeakerData(const uint8_t *data, size_t len);
