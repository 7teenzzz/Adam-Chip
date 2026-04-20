#include "Pca9685Module.h"

#include <cstring>

#include <Wire.h>

#include "../../config/AdamsConfig.h"
#include "../core/BootDiagnostics.h"
#include "../core/RuntimeState.h"

namespace {

constexpr uint8_t kMode1Reg = 0x00;
constexpr uint8_t kMode2Reg = 0x01;
constexpr uint8_t kPrescaleReg = 0xFE;
constexpr uint8_t kLed0OnLowReg = 0x06;

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(kPca9685Address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool writeRegisters(uint8_t reg, const uint8_t *data, size_t len) {
  Wire.beginTransmission(kPca9685Address);
  Wire.write(reg);
  for (size_t i = 0; i < len; ++i) {
    Wire.write(data[i]);
  }
  return Wire.endTransmission() == 0;
}

bool readRegister(uint8_t reg, uint8_t &value) {
  Wire.beginTransmission(kPca9685Address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(static_cast<int>(kPca9685Address), 1) != 1) {
    return false;
  }
  value = Wire.read();
  return true;
}

bool writeChannelRaw(uint8_t channel, uint16_t duty) {
  if (channel >= 16) {
    return false;
  }

  uint8_t payload[4] = {};
  if (duty == 0) {
    payload[0] = 0;
    payload[1] = 0;
    payload[2] = 0;
    payload[3] = 0x10;
  } else if (duty >= 4095) {
    payload[0] = 0;
    payload[1] = 0x10;
    payload[2] = 0;
    payload[3] = 0;
  } else {
    payload[0] = 0;
    payload[1] = 0;
    payload[2] = duty & 0xFF;
    payload[3] = (duty >> 8) & 0x0F;
  }

  if (!writeRegisters(kLed0OnLowReg + (channel * 4), payload, sizeof(payload))) {
    return false;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.pca9685Channels[channel] = duty;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  return true;
}

const Pca9685SceneConfig *findScene(const char *name) {
  if (name == nullptr) {
    return nullptr;
  }
  for (size_t i = 0; i < kPca9685SceneCount; ++i) {
    if (strcmp(kPca9685Scenes[i].name, name) == 0) {
      return &kPca9685Scenes[i];
    }
  }
  return nullptr;
}

}  // namespace

bool initPca9685() {
  uint8_t oldMode = 0;
  if (!readRegister(kMode1Reg, oldMode)) {
    bootLogf("pca9685", "read MODE1 failed at address 0x%02x", kPca9685Address);
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.pca9685Ready = false;
    portEXIT_CRITICAL(&gRuntimeStateMux);
    return false;
  }

  if (!writeRegister(kMode1Reg, 0x10)) {
    bootLog("pca9685", "failed to enter sleep mode");
    return false;
  }
  if (!writeRegister(kMode2Reg, 0x04)) {
    bootLog("pca9685", "failed to configure MODE2");
    return false;
  }
  if (!setPca9685Frequency(kPca9685DefaultFrequency)) {
    bootLogf("pca9685", "failed to set frequency %u", kPca9685DefaultFrequency);
    return false;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.pca9685Ready = true;
  gRuntimeState.pca9685Address = kPca9685Address;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  bootLogf("pca9685", "ready, address=0x%02x, frequency=%u", kPca9685Address, kPca9685DefaultFrequency);
  return applyPca9685Scene(kPca9685BootScene);
}

bool setPca9685Frequency(uint16_t frequency) {
  if (frequency < 24 || frequency > 1526) {
    return false;
  }

  const float prescaleValue = (25000000.0f / (4096.0f * static_cast<float>(frequency))) - 1.0f;
  const uint8_t prescale = static_cast<uint8_t>(prescaleValue + 0.5f);

  uint8_t oldMode = 0;
  if (!readRegister(kMode1Reg, oldMode)) {
    return false;
  }

  const uint8_t sleepMode = static_cast<uint8_t>((oldMode & 0x7F) | 0x10);
  if (!writeRegister(kMode1Reg, sleepMode)) {
    return false;
  }
  if (!writeRegister(kPrescaleReg, prescale)) {
    return false;
  }
  if (!writeRegister(kMode1Reg, oldMode)) {
    return false;
  }
  delay(5);
  if (!writeRegister(kMode1Reg, static_cast<uint8_t>(oldMode | 0xA1))) {
    return false;
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.pca9685Frequency = frequency;
  portEXIT_CRITICAL(&gRuntimeStateMux);
  bootLogf("pca9685", "frequency set to %u Hz", frequency);
  return true;
}

bool applyPca9685Update(const Pca9685ChannelUpdate &update) {
  uint16_t duty = update.value;
  if (strcmp(update.mode, "off") == 0) {
    duty = 0;
  } else if (strcmp(update.mode, "on") == 0) {
    duty = 4095;
  } else if (strcmp(update.mode, "pwm") == 0) {
    duty = min<uint16_t>(4095, update.value);
  } else {
    return false;
  }

  const bool ok = writeChannelRaw(update.channel, duty);
  if (ok) {
    portENTER_CRITICAL(&gRuntimeStateMux);
    strncpy(gRuntimeState.activeScene, "manual", sizeof(gRuntimeState.activeScene) - 1);
    gRuntimeState.activeScene[sizeof(gRuntimeState.activeScene) - 1] = '\0';
    portEXIT_CRITICAL(&gRuntimeStateMux);
  }
  return ok;
}

bool applyPca9685Updates(const Pca9685ChannelUpdate *updates, size_t count) {
  if (updates == nullptr) {
    return false;
  }
  for (size_t i = 0; i < count; ++i) {
    if (!applyPca9685Update(updates[i])) {
      return false;
    }
  }
  return true;
}

bool applyPca9685Scene(const char *sceneName) {
  const Pca9685SceneConfig *scene = findScene(sceneName);
  if (scene == nullptr) {
    return false;
  }

  for (uint8_t channel = 0; channel < 16; ++channel) {
    if (!writeChannelRaw(channel, scene->values[channel])) {
      return false;
    }
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  strncpy(gRuntimeState.activeScene, scene->name, sizeof(gRuntimeState.activeScene) - 1);
  gRuntimeState.activeScene[sizeof(gRuntimeState.activeScene) - 1] = '\0';
  portEXIT_CRITICAL(&gRuntimeStateMux);
  return true;
}

size_t getPca9685SceneCount() {
  return kPca9685SceneCount;
}

const char *getPca9685SceneName(size_t index) {
  if (index >= kPca9685SceneCount) {
    return nullptr;
  }
  return kPca9685Scenes[index].name;
}
