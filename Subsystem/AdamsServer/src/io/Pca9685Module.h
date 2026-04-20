#pragma once

#include <Arduino.h>

struct Pca9685ChannelUpdate {
  uint8_t channel;
  char mode[8];
  uint16_t value;
};

bool initPca9685();
bool setPca9685Frequency(uint16_t frequency);
bool applyPca9685Update(const Pca9685ChannelUpdate &update);
bool applyPca9685Updates(const Pca9685ChannelUpdate *updates, size_t count);
bool applyPca9685Scene(const char *sceneName);
size_t getPca9685SceneCount();
const char *getPca9685SceneName(size_t index);
