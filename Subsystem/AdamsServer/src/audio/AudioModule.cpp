#include "AudioModule.h"

#include <cmath>
#include <cstring>

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

#include "driver/i2s_std.h"
#include "esp_heap_caps.h"

#include "../../config/AdamsConfig.h"
#include "../core/BootDiagnostics.h"
#include "../core/RuntimeState.h"

namespace {

enum class AudioFormatMode : uint8_t {
  Philips = 1,
  Msb = 2,
};

struct AudioProfileDefinition {
  const char *name;
  AudioFormatMode format;
  uint8_t dataBits;
  uint8_t slotBits;
  uint8_t preferredSlot;
  uint8_t sampleShift;
};

struct AudioCaptureConfigState {
  char profile[32];
  AudioFormatMode format;
  uint8_t dataBits;
  uint8_t slotBits;
  uint8_t preferredSlot;
  uint8_t sampleShift;
  bool dcBlock;
  float softwareGain;
};

StaticTask_t sAudioTaskBuffer;
StackType_t sAudioTaskStack[4096];

StaticTask_t sSpeakerTaskBuffer;
StackType_t sSpeakerTaskStack[4096];

StaticSemaphore_t sAudioConfigMutexBuffer;
SemaphoreHandle_t sAudioConfigMutex = nullptr;

portMUX_TYPE sAudioMux = portMUX_INITIALIZER_UNLOCKED;
portMUX_TYPE sSpeakerMux = portMUX_INITIALIZER_UNLOCKED;

uint8_t *sAudioRing = nullptr;
uint8_t *sSpeakerRing = nullptr;
i2s_chan_handle_t sAudioRxHandle = nullptr;
i2s_chan_handle_t sSpeakerTxHandle = nullptr;

volatile uint64_t sAudioWriteSequence = 0;
volatile size_t sSpeakerWriteIndex = 0;
volatile size_t sSpeakerReadIndex = 0;
volatile size_t sSpeakerFillCount = 0;
volatile bool sAudioInitialized = false;
volatile bool sSpeakerInitialized = false;
volatile bool sSpeakerClientActive = false;
volatile bool sAudioTaskStarted = false;
volatile bool sSpeakerTaskStarted = false;
volatile uint32_t sAudioLastSampleMs = 0;
volatile uint32_t sAudioLastNonZeroMs = 0;
volatile uint32_t sAudioLeftPeak = 0;
volatile uint32_t sAudioRightPeak = 0;
volatile uint32_t sAudioSelectedPeak = 0;
volatile uint32_t sAudioAverageLevel = 0;
volatile int32_t sAudioDcOffset = 0;
volatile uint32_t sAudioZeroCrossRateTimes1000 = 0;
volatile uint32_t sAudioClipCount = 0;
volatile uint8_t sAudioDetectedChannelMask = 0;
char sAudioSignalState[16] = "silence";

float sDcPrevInput = 0.0f;
float sDcPrevOutput = 0.0f;
AudioCaptureConfigState sCaptureConfig = {};

constexpr i2s_port_t kAudioCapturePort = I2S_NUM_0;
constexpr i2s_port_t kSpeakerPlaybackPort = I2S_NUM_1;
constexpr uint32_t kAudioSilenceThreshold = 24;
constexpr float kDcBlockAlpha = 0.995f;
constexpr AudioProfileDefinition kAudioProfiles[] = {
  {"inmp441_philips32_left", AudioFormatMode::Philips, 32, 32, 1, 14},
  {"inmp441_philips32_right", AudioFormatMode::Philips, 32, 32, 2, 14},
  {"inmp441_msb32_left", AudioFormatMode::Msb, 32, 32, 1, 14},
  {"inmp441_msb32_right", AudioFormatMode::Msb, 32, 32, 2, 14},
  {"compat16_left", AudioFormatMode::Philips, 16, 16, 1, 0},
  {"compat16_right", AudioFormatMode::Philips, 16, 16, 2, 0},
};

void copyText(char *dst, size_t dstSize, const char *src) {
  if (dst == nullptr || dstSize == 0) {
    return;
  }
  strncpy(dst, src == nullptr ? "" : src, dstSize - 1);
  dst[dstSize - 1] = '\0';
}

const char *formatName(AudioFormatMode format) {
  return format == AudioFormatMode::Msb ? "msb" : "philips";
}

const AudioProfileDefinition *findProfile(const char *name) {
  if (name == nullptr || name[0] == '\0') {
    return nullptr;
  }
  for (const auto &profile : kAudioProfiles) {
    if (strcmp(profile.name, name) == 0) {
      return &profile;
    }
  }
  return nullptr;
}

const AudioProfileDefinition *defaultProfile() {
  return &kAudioProfiles[0];
}

uint8_t *allocateRingBuffer(const char *name, size_t size) {
  uint8_t *buffer = nullptr;
  if (psramFound()) {
    buffer = static_cast<uint8_t *>(heap_caps_malloc(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  }
  if (buffer == nullptr) {
    buffer = static_cast<uint8_t *>(heap_caps_malloc(size, MALLOC_CAP_8BIT));
  }
  if (buffer != nullptr) {
    memset(buffer, 0, size);
    bootLogf(
      name,
      "buffer allocated: %lu bytes in %s",
      static_cast<unsigned long>(size),
      psramFound() && esp_ptr_external_ram(buffer) ? "psram" : "dram");
  }
  return buffer;
}

bool ensureAudioConfigMutex() {
  if (sAudioConfigMutex != nullptr) {
    return true;
  }
  sAudioConfigMutex = xSemaphoreCreateMutexStatic(&sAudioConfigMutexBuffer);
  return sAudioConfigMutex != nullptr;
}

void applyProfileDefaults(const AudioProfileDefinition &profile) {
  copyText(sCaptureConfig.profile, sizeof(sCaptureConfig.profile), profile.name);
  sCaptureConfig.format = profile.format;
  sCaptureConfig.dataBits = profile.dataBits;
  sCaptureConfig.slotBits = profile.slotBits;
  sCaptureConfig.preferredSlot = profile.preferredSlot;
  sCaptureConfig.sampleShift = profile.sampleShift;
}

i2s_data_bit_width_t toDataWidth(uint8_t bits) {
  return bits >= 32 ? I2S_DATA_BIT_WIDTH_32BIT : I2S_DATA_BIT_WIDTH_16BIT;
}

i2s_slot_bit_width_t toSlotWidth(uint8_t bits) {
  return bits >= 32 ? I2S_SLOT_BIT_WIDTH_32BIT : I2S_SLOT_BIT_WIDTH_16BIT;
}

void appendAudioBytes(const uint8_t *src, size_t length) {
  if (sAudioRing == nullptr) {
    return;
  }

  portENTER_CRITICAL(&sAudioMux);
  uint64_t sequence = sAudioWriteSequence;
  size_t writeIndex = static_cast<size_t>(sequence % kAudioRingBufferBytes);
  size_t firstCopy = min(length, kAudioRingBufferBytes - writeIndex);
  memcpy(sAudioRing + writeIndex, src, firstCopy);
  if (firstCopy < length) {
    memcpy(sAudioRing, src + firstCopy, length - firstCopy);
  }
  sAudioWriteSequence += length;
  sAudioLastSampleMs = millis();
  portEXIT_CRITICAL(&sAudioMux);

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.audioWriteSequenceLow = static_cast<uint32_t>(sAudioWriteSequence & 0xFFFFFFFFULL);
  gRuntimeState.audioWriteSequenceHigh = static_cast<uint32_t>((sAudioWriteSequence >> 32) & 0xFFFFFFFFULL);
  gRuntimeState.audioLastSampleMs = sAudioLastSampleMs;
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

int32_t convertRawSampleToPcm(int32_t rawSample, const AudioCaptureConfigState &config) {
  if (config.sampleShift > 0) {
    rawSample >>= config.sampleShift;
  }
  return rawSample;
}

float applyDcBlockFilter(float input, bool enabled) {
  if (!enabled) {
    return input;
  }
  const float output = input - sDcPrevInput + (kDcBlockAlpha * sDcPrevOutput);
  sDcPrevInput = input;
  sDcPrevOutput = output;
  return output;
}

int16_t selectPreferredOutputSample(int32_t leftSample, int32_t rightSample, uint8_t preferredSlot) {
  return static_cast<int16_t>(preferredSlot == 1 ? leftSample : rightSample);
}

uint8_t detectActiveChannels(uint32_t leftPeak, uint32_t rightPeak) {
  uint8_t mask = 0;
  if (leftPeak >= kAudioSilenceThreshold) {
    mask |= 0x01;
  }
  if (rightPeak >= kAudioSilenceThreshold) {
    mask |= 0x02;
  }
  return mask;
}

const char *classifySignalState(uint32_t averageLevel, uint32_t peakLevel, uint32_t clipCount, uint32_t zeroCrossRateTimes1000) {
  if (peakLevel < kAudioSilenceThreshold && averageLevel < 4) {
    return "silence";
  }
  if (clipCount > 0) {
    return "clipped";
  }
  if (peakLevel < 256 || averageLevel < 16) {
    return "weak";
  }
  if (zeroCrossRateTimes1000 > 420 && averageLevel > 128) {
    return "noisy";
  }
  return "active";
}

void resetDcBlockState() {
  sDcPrevInput = 0.0f;
  sDcPrevOutput = 0.0f;
}

bool initAudioStdRxChannelLocked() {
  i2s_chan_config_t chanCfg = I2S_CHANNEL_DEFAULT_CONFIG(kAudioCapturePort, I2S_ROLE_MASTER);
  chanCfg.dma_desc_num = 6;
  chanCfg.dma_frame_num = 256;
  chanCfg.auto_clear_after_cb = false;
  chanCfg.auto_clear_before_cb = false;

  esp_err_t err = i2s_new_channel(&chanCfg, nullptr, &sAudioRxHandle);
  if (err != ESP_OK) {
    bootLogf("audio-mic", "i2s_new_channel failed: 0x%x", err);
    sAudioRxHandle = nullptr;
    return false;
  }

  i2s_std_config_t stdCfg = {};
  stdCfg.clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(kAudioSampleRate);
  if (sCaptureConfig.format == AudioFormatMode::Msb) {
    stdCfg.slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(toDataWidth(sCaptureConfig.dataBits), I2S_SLOT_MODE_STEREO);
  } else {
    stdCfg.slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(toDataWidth(sCaptureConfig.dataBits), I2S_SLOT_MODE_STEREO);
  }
  stdCfg.slot_cfg.slot_mask = I2S_STD_SLOT_BOTH;
  stdCfg.slot_cfg.slot_bit_width = toSlotWidth(sCaptureConfig.slotBits);
  stdCfg.gpio_cfg.mclk = I2S_GPIO_UNUSED;
  stdCfg.gpio_cfg.bclk = static_cast<gpio_num_t>(I2S_MIC_BCLK);
  stdCfg.gpio_cfg.ws = static_cast<gpio_num_t>(I2S_MIC_WS);
  stdCfg.gpio_cfg.dout = I2S_GPIO_UNUSED;
  stdCfg.gpio_cfg.din = static_cast<gpio_num_t>(I2S_MIC_SD);
  stdCfg.gpio_cfg.invert_flags.mclk_inv = false;
  stdCfg.gpio_cfg.invert_flags.bclk_inv = false;
  stdCfg.gpio_cfg.invert_flags.ws_inv = false;

  err = i2s_channel_init_std_mode(sAudioRxHandle, &stdCfg);
  if (err != ESP_OK) {
    bootLogf("audio-mic", "i2s_channel_init_std_mode failed: 0x%x", err);
    i2s_del_channel(sAudioRxHandle);
    sAudioRxHandle = nullptr;
    return false;
  }

  err = i2s_channel_enable(sAudioRxHandle);
  if (err != ESP_OK) {
    bootLogf("audio-mic", "i2s_channel_enable failed: 0x%x", err);
    i2s_del_channel(sAudioRxHandle);
    sAudioRxHandle = nullptr;
    return false;
  }

  return true;
}

void destroyAudioRxChannelLocked() {
  if (sAudioRxHandle == nullptr) {
    return;
  }
  i2s_channel_disable(sAudioRxHandle);
  i2s_del_channel(sAudioRxHandle);
  sAudioRxHandle = nullptr;
}

bool reconfigureAudioCaptureLocked(const char *reason) {
  destroyAudioRxChannelLocked();
  resetDcBlockState();
  const bool ok = initAudioStdRxChannelLocked();

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.audioReady = ok;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  if (ok) {
    bootLogf(
      "audio-mic",
      "capture config applied: profile=%s format=%s data_bits=%u slot_bits=%u slot=%u shift=%u gain=%.2f dc_block=%s reason=%s",
      sCaptureConfig.profile,
      formatName(sCaptureConfig.format),
      static_cast<unsigned>(sCaptureConfig.dataBits),
      static_cast<unsigned>(sCaptureConfig.slotBits),
      static_cast<unsigned>(sCaptureConfig.preferredSlot),
      static_cast<unsigned>(sCaptureConfig.sampleShift),
      static_cast<double>(sCaptureConfig.softwareGain),
      sCaptureConfig.dcBlock ? "on" : "off",
      reason == nullptr ? "runtime" : reason);
  } else {
    bootLog("audio-mic", "capture reconfigure failed");
  }
  return ok;
}

bool initSpeakerStdTxChannel() {
  i2s_chan_config_t chanCfg = I2S_CHANNEL_DEFAULT_CONFIG(kSpeakerPlaybackPort, I2S_ROLE_MASTER);
  chanCfg.dma_desc_num = 6;
  chanCfg.dma_frame_num = 256;
  chanCfg.auto_clear_after_cb = true;
  chanCfg.auto_clear_before_cb = false;

  esp_err_t err = i2s_new_channel(&chanCfg, &sSpeakerTxHandle, nullptr);
  if (err != ESP_OK) {
    bootLogf("speaker", "i2s_new_channel failed: 0x%x", err);
    sSpeakerTxHandle = nullptr;
    return false;
  }

  i2s_std_config_t stdCfg = {};
  stdCfg.clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(kSpeakerSampleRate);
  stdCfg.slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO);
  stdCfg.slot_cfg.slot_mask = I2S_STD_SLOT_BOTH;
  stdCfg.gpio_cfg.mclk = I2S_GPIO_UNUSED;
  stdCfg.gpio_cfg.bclk = static_cast<gpio_num_t>(I2S_DAC_BCLK);
  stdCfg.gpio_cfg.ws = static_cast<gpio_num_t>(I2S_DAC_LRCK);
  stdCfg.gpio_cfg.dout = static_cast<gpio_num_t>(I2S_DAC_DATA);
  stdCfg.gpio_cfg.din = I2S_GPIO_UNUSED;
  stdCfg.gpio_cfg.invert_flags.mclk_inv = false;
  stdCfg.gpio_cfg.invert_flags.bclk_inv = false;
  stdCfg.gpio_cfg.invert_flags.ws_inv = false;

  err = i2s_channel_init_std_mode(sSpeakerTxHandle, &stdCfg);
  if (err != ESP_OK) {
    bootLogf("speaker", "i2s_channel_init_std_mode failed: 0x%x", err);
    i2s_del_channel(sSpeakerTxHandle);
    sSpeakerTxHandle = nullptr;
    return false;
  }

  err = i2s_channel_enable(sSpeakerTxHandle);
  if (err != ESP_OK) {
    bootLogf("speaker", "i2s_channel_enable failed: 0x%x", err);
    i2s_del_channel(sSpeakerTxHandle);
    sSpeakerTxHandle = nullptr;
    return false;
  }

  return true;
}

void updateSpeakerFillRuntime() {
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.speakerBufferFill = static_cast<uint32_t>(sSpeakerFillCount);
  gRuntimeState.speakerClientActive = sSpeakerClientActive;
  portEXIT_CRITICAL(&gRuntimeStateMux);
}

void updateAudioStats(
  uint32_t leftPeak,
  uint32_t rightPeak,
  uint32_t selectedPeak,
  uint32_t averageLevel,
  int32_t dcOffset,
  uint32_t zeroCrossRateTimes1000,
  uint32_t chunkClipCount) {
  const uint32_t now = millis();
  const uint8_t channelMask = detectActiveChannels(leftPeak, rightPeak);
  const char *signalState = classifySignalState(averageLevel, selectedPeak, chunkClipCount, zeroCrossRateTimes1000);

  portENTER_CRITICAL(&sAudioMux);
  sAudioLeftPeak = leftPeak;
  sAudioRightPeak = rightPeak;
  sAudioSelectedPeak = selectedPeak;
  sAudioAverageLevel = averageLevel;
  sAudioDcOffset = dcOffset;
  sAudioZeroCrossRateTimes1000 = zeroCrossRateTimes1000;
  sAudioClipCount += chunkClipCount;
  sAudioDetectedChannelMask = channelMask;
  copyText(sAudioSignalState, sizeof(sAudioSignalState), signalState);
  if (selectedPeak >= kAudioSilenceThreshold) {
    sAudioLastNonZeroMs = now;
  }
  portEXIT_CRITICAL(&sAudioMux);
}

void audioCaptureTask(void *parameter) {
  (void)parameter;

  uint8_t rawBytes[kAudioReadChunkBytes];
  int16_t monoBuffer[kAudioReadChunkBytes / sizeof(int16_t)];
  int16_t lastOutputSample = 0;

  while (true) {
    i2s_chan_handle_t audioHandle = nullptr;
    AudioCaptureConfigState config = {};

    if (sAudioConfigMutex == nullptr || xSemaphoreTake(sAudioConfigMutex, pdMS_TO_TICKS(100)) != pdTRUE) {
      delay(2);
      continue;
    }

    audioHandle = sAudioRxHandle;
    config = sCaptureConfig;
    size_t bytesRead = 0;
    esp_err_t err = ESP_FAIL;
    if (audioHandle != nullptr) {
      err = i2s_channel_read(audioHandle, rawBytes, sizeof(rawBytes), &bytesRead, 50);
    }
    xSemaphoreGive(sAudioConfigMutex);

    if (audioHandle == nullptr || err != ESP_OK || bytesRead == 0) {
      delay(2);
      continue;
    }

    const size_t frameStride = config.dataBits >= 32 ? sizeof(int32_t) * 2 : sizeof(int16_t) * 2;
    const size_t framesRead = bytesRead / frameStride;
    if (framesRead == 0) {
      continue;
    }

    uint64_t absSum = 0;
    int64_t signedSum = 0;
    uint32_t leftPeak = 0;
    uint32_t rightPeak = 0;
    uint32_t selectedPeak = 0;
    uint32_t zeroCrossCount = 0;
    uint32_t clipCount = 0;

    for (size_t i = 0; i < framesRead; ++i) {
      int32_t leftRaw = 0;
      int32_t rightRaw = 0;
      if (config.dataBits >= 32) {
        const int32_t *samples = reinterpret_cast<const int32_t *>(rawBytes);
        leftRaw = samples[i * 2];
        rightRaw = samples[i * 2 + 1];
      } else {
        const int16_t *samples = reinterpret_cast<const int16_t *>(rawBytes);
        leftRaw = samples[i * 2];
        rightRaw = samples[i * 2 + 1];
      }

      int32_t leftPcm = convertRawSampleToPcm(leftRaw, config);
      int32_t rightPcm = convertRawSampleToPcm(rightRaw, config);
      leftPcm = constrain(leftPcm, -32768, 32767);
      rightPcm = constrain(rightPcm, -32768, 32767);

      leftPeak = max(leftPeak, static_cast<uint32_t>(abs(leftPcm)));
      rightPeak = max(rightPeak, static_cast<uint32_t>(abs(rightPcm)));

      float selected = static_cast<float>(selectPreferredOutputSample(leftPcm, rightPcm, config.preferredSlot));
      signedSum += static_cast<int32_t>(selected);
      selected = applyDcBlockFilter(selected, config.dcBlock);
      selected *= config.softwareGain;

      int32_t output = static_cast<int32_t>(lroundf(selected));
      if (output > 32767) {
        output = 32767;
        clipCount++;
      } else if (output < -32768) {
        output = -32768;
        clipCount++;
      }

      const int16_t outputSample = static_cast<int16_t>(output);
      if ((lastOutputSample < 0 && outputSample >= 0) || (lastOutputSample >= 0 && outputSample < 0)) {
        zeroCrossCount++;
      }
      lastOutputSample = outputSample;

      const uint32_t sampleAbs = static_cast<uint32_t>(abs(output));
      selectedPeak = max(selectedPeak, sampleAbs);
      absSum += sampleAbs;
      monoBuffer[i] = outputSample;
    }

    const uint32_t averageLevel = static_cast<uint32_t>(absSum / framesRead);
    const int32_t dcOffset = static_cast<int32_t>(signedSum / static_cast<int32_t>(framesRead));
    const uint32_t zeroCrossRateTimes1000 = static_cast<uint32_t>((zeroCrossCount * 1000UL) / max<size_t>(framesRead, 1));

    updateAudioStats(leftPeak, rightPeak, selectedPeak, averageLevel, dcOffset, zeroCrossRateTimes1000, clipCount);
    appendAudioBytes(reinterpret_cast<const uint8_t *>(monoBuffer), framesRead * sizeof(int16_t));
  }
}

void speakerPlaybackTask(void *parameter) {
  (void)parameter;

  int16_t monoSamples[kSpeakerTxChunkSamples];
  int16_t stereoFrames[kSpeakerTxChunkSamples * 2];

  while (true) {
    size_t producedSamples = 0;

    portENTER_CRITICAL(&sSpeakerMux);
    const size_t availableBytes = sSpeakerFillCount;
    const size_t wantedBytes = kSpeakerTxChunkSamples * sizeof(int16_t);
    const size_t bytesToRead = min(availableBytes, wantedBytes);

    uint8_t *monoBytes = reinterpret_cast<uint8_t *>(monoSamples);
    const size_t firstCopy = min(bytesToRead, kSpeakerRingBufferBytes - sSpeakerReadIndex);
    memcpy(monoBytes, sSpeakerRing + sSpeakerReadIndex, firstCopy);
    if (firstCopy < bytesToRead) {
      memcpy(monoBytes + firstCopy, sSpeakerRing, bytesToRead - firstCopy);
    }
    sSpeakerReadIndex = (sSpeakerReadIndex + bytesToRead) % kSpeakerRingBufferBytes;
    sSpeakerFillCount -= bytesToRead;
    portEXIT_CRITICAL(&sSpeakerMux);

    producedSamples = bytesToRead / sizeof(int16_t);
    for (size_t i = producedSamples; i < kSpeakerTxChunkSamples; ++i) {
      monoSamples[i] = 0;
    }

    if (bytesToRead < wantedBytes) {
      portENTER_CRITICAL(&gRuntimeStateMux);
      gRuntimeState.speakerUnderruns = gRuntimeState.speakerUnderruns + 1;
      portEXIT_CRITICAL(&gRuntimeStateMux);
    }

    for (size_t i = 0; i < kSpeakerTxChunkSamples; ++i) {
      stereoFrames[i * 2] = monoSamples[i];
      stereoFrames[i * 2 + 1] = monoSamples[i];
    }

    size_t bytesWritten = 0;
    const esp_err_t err = i2s_channel_write(
      sSpeakerTxHandle,
      stereoFrames,
      sizeof(stereoFrames),
      &bytesWritten,
      pdMS_TO_TICKS(500));
    if (err == ESP_ERR_TIMEOUT) {
      vTaskDelay(pdMS_TO_TICKS(10));
    } else if (err != ESP_OK) {
      bootLogf("speaker", "i2s_channel_write failed: 0x%x", err);
      delay(2);
    }

    updateSpeakerFillRuntime();
  }
}

}  // namespace

bool initAudioCapture() {
  if (!ensureAudioConfigMutex()) {
    bootLog("audio-mic", "failed to create config mutex");
    return false;
  }

  if (sAudioRing == nullptr) {
    sAudioRing = allocateRingBuffer("audio-mic", kAudioRingBufferBytes);
    if (sAudioRing == nullptr) {
      bootLog("audio-mic", "failed to allocate audio ring buffer");
      return false;
    }
  }

  if (xSemaphoreTake(sAudioConfigMutex, pdMS_TO_TICKS(250)) != pdTRUE) {
    bootLog("audio-mic", "config mutex timeout");
    return false;
  }

  if (sCaptureConfig.profile[0] == '\0') {
    const AudioProfileDefinition *profile = defaultProfile();
    applyProfileDefaults(*profile);
    sCaptureConfig.dcBlock = true;
    sCaptureConfig.softwareGain = 1.0f;
  }

  const bool ready = reconfigureAudioCaptureLocked("boot");
  xSemaphoreGive(sAudioConfigMutex);
  if (!ready) {
    return false;
  }

  sAudioInitialized = true;
  if (!sAudioTaskStarted) {
    xTaskCreateStaticPinnedToCore(
      audioCaptureTask,
      "audio_capture",
      sizeof(sAudioTaskStack) / sizeof(StackType_t),
      nullptr,
      2,
      sAudioTaskStack,
      &sAudioTaskBuffer,
      APP_CPU_NUM);
    sAudioTaskStarted = true;
  }

  return true;
}

bool initSpeakerPlayback() {
  if (sSpeakerRing == nullptr) {
    sSpeakerRing = allocateRingBuffer("speaker", kSpeakerRingBufferBytes);
    if (sSpeakerRing == nullptr) {
      bootLog("speaker", "failed to allocate speaker ring buffer");
      return false;
    }
  }

  if (!initSpeakerStdTxChannel()) {
    return false;
  }

  sSpeakerInitialized = true;
  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.speakerReady = true;
  gRuntimeState.speakerBufferFill = 0;
  gRuntimeState.speakerUnderruns = 0;
  gRuntimeState.speakerOverflows = 0;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  if (!sSpeakerTaskStarted) {
    xTaskCreateStaticPinnedToCore(
      speakerPlaybackTask,
      "speaker_playback",
      sizeof(sSpeakerTaskStack) / sizeof(StackType_t),
      nullptr,
      2,
      sSpeakerTaskStack,
      &sSpeakerTaskBuffer,
      APP_CPU_NUM);
    sSpeakerTaskStarted = true;
  }

  bootLogf("speaker", "ready, sample_rate=%lu Hz", static_cast<unsigned long>(kSpeakerSampleRate));
  return true;
}

bool readAudioChunk(uint8_t *dst, size_t maxBytes, size_t &outBytes, uint64_t &cursor) {
  outBytes = 0;
  if (!sAudioInitialized || sAudioRing == nullptr || dst == nullptr || maxBytes == 0) {
    return false;
  }

  portENTER_CRITICAL(&sAudioMux);
  const uint64_t writeSequence = sAudioWriteSequence;
  const uint64_t earliestSequence = (writeSequence > kAudioRingBufferBytes) ? (writeSequence - kAudioRingBufferBytes) : 0;
  if (cursor < earliestSequence) {
    cursor = earliestSequence;
  }

  const size_t available = static_cast<size_t>(writeSequence - cursor);
  const size_t toCopy = min(maxBytes, available);
  const size_t readIndex = static_cast<size_t>(cursor % kAudioRingBufferBytes);
  const size_t firstCopy = min(toCopy, kAudioRingBufferBytes - readIndex);
  memcpy(dst, sAudioRing + readIndex, firstCopy);
  if (firstCopy < toCopy) {
    memcpy(dst + firstCopy, sAudioRing, toCopy - firstCopy);
  }
  cursor += toCopy;
  outBytes = toCopy;
  portEXIT_CRITICAL(&sAudioMux);

  return true;
}

uint64_t getAudioWriteSequence() {
  portENTER_CRITICAL(&sAudioMux);
  const uint64_t sequence = sAudioWriteSequence;
  portEXIT_CRITICAL(&sAudioMux);
  return sequence;
}

uint32_t getAudioRingBufferBytes() {
  return static_cast<uint32_t>(kAudioRingBufferBytes);
}

bool getAudioStatusSnapshot(AudioStatusSnapshot &snapshot) {
  AudioCaptureConfigState config = {};
  if (sAudioConfigMutex != nullptr && xSemaphoreTake(sAudioConfigMutex, pdMS_TO_TICKS(100)) == pdTRUE) {
    config = sCaptureConfig;
    xSemaphoreGive(sAudioConfigMutex);
  } else {
    memset(&config, 0, sizeof(config));
  }

  portENTER_CRITICAL(&sAudioMux);
  const uint64_t writeSequence = sAudioWriteSequence;
  const uint32_t lastSampleMs = sAudioLastSampleMs;
  const uint32_t lastNonZeroMs = sAudioLastNonZeroMs;
  const uint32_t leftPeak = sAudioLeftPeak;
  const uint32_t rightPeak = sAudioRightPeak;
  const uint32_t selectedPeak = sAudioSelectedPeak;
  const uint32_t averageLevel = sAudioAverageLevel;
  const int32_t dcOffset = sAudioDcOffset;
  const uint32_t zeroCrossRateTimes1000 = sAudioZeroCrossRateTimes1000;
  const uint32_t clipCount = sAudioClipCount;
  const uint8_t channelMask = sAudioDetectedChannelMask;
  char signalState[sizeof(sAudioSignalState)];
  copyText(signalState, sizeof(signalState), sAudioSignalState);
  portEXIT_CRITICAL(&sAudioMux);

  portENTER_CRITICAL(&gRuntimeStateMux);
  snapshot.capture.ready = gRuntimeState.audioReady;
  snapshot.playback.ready = gRuntimeState.speakerReady;
  snapshot.playback.clientActive = gRuntimeState.speakerClientActive;
  snapshot.playback.bufferFill = gRuntimeState.speakerBufferFill;
  snapshot.playback.underruns = gRuntimeState.speakerUnderruns;
  snapshot.playback.overflows = gRuntimeState.speakerOverflows;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  const uint32_t recentActivityMs = lastSampleMs == 0 ? 0 : millis() - lastSampleMs;
  snapshot.capture.sampleRate = kAudioSampleRate;
  snapshot.capture.pcmBits = kAudioBitsPerSample;
  snapshot.capture.pcmChannels = kAudioChannels;
  snapshot.capture.dataBits = config.dataBits;
  snapshot.capture.slotBits = config.slotBits;
  snapshot.capture.preferredSlot = config.preferredSlot;
  snapshot.capture.sampleShift = config.sampleShift;
  snapshot.capture.dcBlock = config.dcBlock;
  snapshot.capture.softwareGain = config.softwareGain;
  snapshot.capture.bufferBytes = getAudioRingBufferBytes();
  snapshot.capture.writerSequence = writeSequence;
  snapshot.capture.lastSampleMs = lastSampleMs;
  snapshot.capture.lastNonZeroMs = lastNonZeroMs;
  snapshot.capture.recentActivityMs = recentActivityMs;
  snapshot.capture.streamActive = snapshot.capture.ready && recentActivityMs > 0 && recentActivityMs < 2000;
  snapshot.capture.leftPeak = leftPeak;
  snapshot.capture.rightPeak = rightPeak;
  snapshot.capture.selectedPeak = selectedPeak;
  snapshot.capture.averageLevel = averageLevel;
  snapshot.capture.dcOffset = dcOffset;
  snapshot.capture.zeroCrossRate = static_cast<float>(zeroCrossRateTimes1000) / 1000.0f;
  snapshot.capture.clipCount = clipCount;
  snapshot.capture.detectedChannels = channelMask;
  copyText(snapshot.capture.profile, sizeof(snapshot.capture.profile), config.profile);
  copyText(snapshot.capture.format, sizeof(snapshot.capture.format), formatName(config.format));
  copyText(snapshot.capture.signalState, sizeof(snapshot.capture.signalState), signalState);
  return true;
}

bool applyAudioRuntimeUpdate(const AudioRuntimeUpdate &update) {
  if (!ensureAudioConfigMutex()) {
    return false;
  }
  if (xSemaphoreTake(sAudioConfigMutex, pdMS_TO_TICKS(250)) != pdTRUE) {
    return false;
  }

  bool requiresReinit = false;
  if (update.hasProfile) {
    const AudioProfileDefinition *profile = findProfile(update.profile);
    if (profile == nullptr) {
      xSemaphoreGive(sAudioConfigMutex);
      return false;
    }
    if (strcmp(sCaptureConfig.profile, profile->name) != 0) {
      applyProfileDefaults(*profile);
      requiresReinit = true;
    }
  }

  if (update.hasSoftwareGain) {
    sCaptureConfig.softwareGain = constrain(update.softwareGain, 0.25f, 32.0f);
  }
  if (update.hasDcBlock) {
    sCaptureConfig.dcBlock = update.dcBlock;
    resetDcBlockState();
  }
  if (update.hasSlotOverride) {
    sCaptureConfig.preferredSlot = update.preferredSlot == 2 ? 2 : 1;
  }
  if (update.hasShiftOverride) {
    sCaptureConfig.sampleShift = min<uint8_t>(update.sampleShift, 24);
  }

  bool ok = true;
  if (requiresReinit) {
    ok = reconfigureAudioCaptureLocked("runtime");
  }
  xSemaphoreGive(sAudioConfigMutex);
  return ok;
}

size_t getAudioProfileCount() {
  return sizeof(kAudioProfiles) / sizeof(kAudioProfiles[0]);
}

bool getAudioProfileName(size_t index, char *dst, size_t dstSize) {
  if (index >= getAudioProfileCount()) {
    return false;
  }
  copyText(dst, dstSize, kAudioProfiles[index].name);
  return true;
}

size_t getAudioClipBytesForDurationMs(uint32_t durationMs) {
  const uint32_t clampedMs = constrain(durationMs, 250UL, 4000UL);
  const uint64_t bytes = (static_cast<uint64_t>(kAudioSampleRate) * kAudioChannels * (kAudioBitsPerSample / 8) * clampedMs) / 1000ULL;
  return static_cast<size_t>(min<uint64_t>(bytes, kAudioRingBufferBytes));
}

bool copyRecentAudioClip(uint32_t durationMs, uint8_t *dst, size_t capacity, size_t &outBytes) {
  outBytes = 0;
  if (!sAudioInitialized || sAudioRing == nullptr || dst == nullptr) {
    return false;
  }

  const size_t wantedBytes = getAudioClipBytesForDurationMs(durationMs);
  if (wantedBytes == 0 || capacity < wantedBytes) {
    return false;
  }

  portENTER_CRITICAL(&sAudioMux);
  const uint64_t writeSequence = sAudioWriteSequence;
  const uint64_t earliestSequence = (writeSequence > kAudioRingBufferBytes) ? (writeSequence - kAudioRingBufferBytes) : 0;
  uint64_t startSequence = writeSequence > wantedBytes ? (writeSequence - wantedBytes) : 0;
  if (startSequence < earliestSequence) {
    startSequence = earliestSequence;
  }
  outBytes = static_cast<size_t>(writeSequence - startSequence);
  const size_t readIndex = static_cast<size_t>(startSequence % kAudioRingBufferBytes);
  const size_t firstCopy = min(outBytes, kAudioRingBufferBytes - readIndex);
  memcpy(dst, sAudioRing + readIndex, firstCopy);
  if (firstCopy < outBytes) {
    memcpy(dst + firstCopy, sAudioRing, outBytes - firstCopy);
  }
  portEXIT_CRITICAL(&sAudioMux);
  return outBytes > 0;
}

bool beginSpeakerStream() {
  if (!sSpeakerInitialized) {
    return false;
  }

  bool acquired = false;
  portENTER_CRITICAL(&sSpeakerMux);
  if (!sSpeakerClientActive && sSpeakerFillCount == 0) {
    sSpeakerClientActive = true;
    sSpeakerWriteIndex = 0;
    sSpeakerReadIndex = 0;
    sSpeakerFillCount = 0;
    acquired = true;
  }
  portEXIT_CRITICAL(&sSpeakerMux);

  updateSpeakerFillRuntime();
  return acquired;
}

void endSpeakerStream() {
  portENTER_CRITICAL(&sSpeakerMux);
  sSpeakerClientActive = false;
  portEXIT_CRITICAL(&sSpeakerMux);

  updateSpeakerFillRuntime();
}

size_t writeSpeakerData(const uint8_t *data, size_t len) {
  if (!sSpeakerInitialized || sSpeakerRing == nullptr || data == nullptr || len == 0) {
    return 0;
  }

  size_t written = 0;
  portENTER_CRITICAL(&sSpeakerMux);
  const size_t availableSpace = kSpeakerRingBufferBytes - sSpeakerFillCount;
  written = min(len, availableSpace);
  const size_t firstCopy = min(written, kSpeakerRingBufferBytes - sSpeakerWriteIndex);
  memcpy(sSpeakerRing + sSpeakerWriteIndex, data, firstCopy);
  if (firstCopy < written) {
    memcpy(sSpeakerRing, data + firstCopy, written - firstCopy);
  }
  sSpeakerWriteIndex = (sSpeakerWriteIndex + written) % kSpeakerRingBufferBytes;
  sSpeakerFillCount = sSpeakerFillCount + written;
  portEXIT_CRITICAL(&sSpeakerMux);

  if (written < len) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.speakerOverflows = gRuntimeState.speakerOverflows + 1;
    portEXIT_CRITICAL(&gRuntimeStateMux);
  }

  updateSpeakerFillRuntime();
  return written;
}
