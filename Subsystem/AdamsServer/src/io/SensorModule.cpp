#include "SensorModule.h"

#include <Wire.h>

#include "../../config/AdamsConfig.h"
#include "../core/RuntimeState.h"

namespace {

StaticTask_t sSensorTaskBuffer;
StackType_t sSensorTaskStack[4096];

float sLightEma = 0.0f;
bool sMotionStable = false;
bool sMotionLastRead = false;
uint32_t sMotionLastEdgeAt = 0;

void sensorTask(void *parameter) {
  (void)parameter;
  while (true) {
    readSensors();
    vTaskDelay(pdMS_TO_TICKS(kSensorPollMs));
  }
}

}  // namespace

bool initSensors() {
  analogReadResolution(12);
  pinMode(LIGHT_SENSOR_PIN, INPUT);
  pinMode(MOTION_SENSOR_PIN, INPUT);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  Wire.setClock(kI2cClockHz);

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.motionChangedAtMs = millis();
  gRuntimeState.sensorsReady = true;
  portEXIT_CRITICAL(&gRuntimeStateMux);

  return true;
}

void startSensorTask() {
  xTaskCreateStaticPinnedToCore(
    sensorTask,
    "sensor_task",
    sizeof(sSensorTaskStack) / sizeof(StackType_t),
    nullptr,
    1,
    sSensorTaskStack,
    &sSensorTaskBuffer,
    APP_CPU_NUM
  );
}

void readSensors() {
  const uint16_t lightRaw = analogRead(LIGHT_SENSOR_PIN);
  if (sLightEma == 0.0f) {
    sLightEma = static_cast<float>(lightRaw);
  } else {
    sLightEma = (kLightAlpha * static_cast<float>(lightRaw)) + ((1.0f - kLightAlpha) * sLightEma);
  }
  const float lightNorm = constrain(sLightEma / 4095.0f, 0.0f, 1.0f);

  const bool motionRead = digitalRead(MOTION_SENSOR_PIN) == HIGH;
  const uint32_t now = millis();
  if (motionRead != sMotionLastRead) {
    sMotionLastRead = motionRead;
    sMotionLastEdgeAt = now;
  }
  if ((now - sMotionLastEdgeAt) >= kMotionDebounceMs && sMotionStable != motionRead) {
    sMotionStable = motionRead;
    portENTER_CRITICAL(&gRuntimeStateMux);
    gRuntimeState.motionChangedAtMs = now;
    portEXIT_CRITICAL(&gRuntimeStateMux);
  }

  portENTER_CRITICAL(&gRuntimeStateMux);
  gRuntimeState.lightRaw = lightRaw;
  gRuntimeState.lightNorm = lightNorm;
  gRuntimeState.motion = sMotionStable;
  portEXIT_CRITICAL(&gRuntimeStateMux);
}
