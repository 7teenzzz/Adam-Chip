#pragma once

#include <Arduino.h>
#include "esp_camera.h"

struct CameraControlState {
  int framesize;
  int quality;
  int brightness;
  int contrast;
  int saturation;
  int sharpness;
  int denoise;
  int gainCeiling;
  bool awb;
  bool agc;
  bool aec;
  bool hmirror;
  bool vflip;
  char preset[16];
};

struct CameraPresetDescriptor {
  char name[16];
  bool builtin;
  bool exists;
  bool hasFramesize;
  int framesize;
};

struct CameraControlUpdate {
  bool hasFramesize = false;
  int framesize = 0;
  bool hasQuality = false;
  int quality = 0;
  bool hasBrightness = false;
  int brightness = 0;
  bool hasContrast = false;
  int contrast = 0;
  bool hasSaturation = false;
  int saturation = 0;
  bool hasSharpness = false;
  int sharpness = 0;
  bool hasDenoise = false;
  int denoise = 0;
  bool hasGainCeiling = false;
  int gainCeiling = 0;
  bool hasAwb = false;
  bool awb = true;
  bool hasAgc = false;
  bool agc = true;
  bool hasAec = false;
  bool aec = true;
  bool hasHmirror = false;
  bool hmirror = false;
  bool hasVflip = false;
  bool vflip = false;
};

bool initCamera();
sensor_t *getCameraSensor();
camera_fb_t *captureCameraFrame();
void releaseCameraFrame(camera_fb_t *fb);
bool getCameraControlState(CameraControlState &state);
bool applyCameraControlUpdate(const CameraControlUpdate &update, const char *presetName = nullptr);
bool applyCameraPreset(const char *presetName);
void noteCameraStreamDemand();
uint32_t getCameraConfigRevision();
uint32_t getCameraGeneration();
uint32_t getLatestCameraFrameSequence();
size_t getLatestCameraFrameSize();
bool copyLatestCameraFrame(uint8_t *dst, size_t capacity, size_t &outLength, int64_t &outTimestampUs, uint32_t &outSequence, uint32_t minimumSequence = 0);
size_t getCameraPresetCount();
bool getCameraPresetDescriptor(size_t index, CameraPresetDescriptor &descriptor);
bool saveCameraPreset(const char *presetName);
bool deleteCameraPreset(const char *presetName);
void resetBuiltInCameraPresets();
