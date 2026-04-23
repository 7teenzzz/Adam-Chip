#include "VideoLatencyMetrics.h"

#include <cstdlib>
#include <cstring>

#include <freertos/FreeRTOS.h>
#include <freertos/portmacro.h>

namespace {

constexpr uint32_t kWindowSeconds = 60;
constexpr size_t kSamplesPerMetric = 512;

struct MetricBufferMs {
  uint16_t values[kSamplesPerMetric];
  uint32_t seconds[kSamplesPerMetric];
  size_t nextIndex = 0;
  size_t count = 0;
};

struct MetricBufferUs {
  uint32_t values[kSamplesPerMetric];
  uint32_t seconds[kSamplesPerMetric];
  size_t nextIndex = 0;
  size_t count = 0;
};

MetricBufferMs sCaptureWaitMetric = {};
MetricBufferMs sProducerCopyMetric = {};
MetricBufferMs sLatestLockWaitMetric = {};
MetricBufferMs sFrameAgeBeforeSendMetric = {};
MetricBufferMs sSendBoundaryMetric = {};
MetricBufferMs sSendHeaderMetric = {};
MetricBufferMs sSendPayloadMetric = {};
MetricBufferMs sStreamLoopMetric = {};
MetricBufferMs sE2eEstimateMetric = {};

MetricBufferUs sProducerCopyUsMetric = {};
MetricBufferUs sLatestLockWaitUsMetric = {};
MetricBufferUs sSendBoundaryUsMetric = {};
MetricBufferUs sSendHeaderUsMetric = {};
MetricBufferUs sSendPayloadUsMetric = {};

uint32_t sCopyFrameMissCount = 0;
uint32_t sNoNewFramePollCount = 0;
uint32_t sLatestMutexTimeoutCount = 0;
uint32_t sSlowSendStrikeCount = 0;
uint32_t sBufferReallocCount = 0;
uint32_t sFrameSkippedDueStale = 0;

uint16_t sTmpSortedValuesMs[kSamplesPerMetric];
uint32_t sTmpSortedValuesUs[kSamplesPerMetric];

portMUX_TYPE sVideoLatencyMux = portMUX_INITIALIZER_UNLOCKED;

int compareUint16(const void *lhs, const void *rhs) {
  const uint16_t a = *reinterpret_cast<const uint16_t *>(lhs);
  const uint16_t b = *reinterpret_cast<const uint16_t *>(rhs);
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

int compareUint32(const void *lhs, const void *rhs) {
  const uint32_t a = *reinterpret_cast<const uint32_t *>(lhs);
  const uint32_t b = *reinterpret_cast<const uint32_t *>(rhs);
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

uint16_t clampMetricValueMs(uint32_t valueMs) {
  return static_cast<uint16_t>(valueMs > 60000 ? 60000 : valueMs);
}

uint32_t clampMetricValueUs(uint32_t valueUs) {
  return valueUs > 60000000UL ? 60000000UL : valueUs;
}

void recordMetricMs(MetricBufferMs &buffer, uint32_t valueMs) {
  const size_t index = buffer.nextIndex;
  buffer.values[index] = clampMetricValueMs(valueMs);
  buffer.seconds[index] = millis() / 1000UL;
  buffer.nextIndex = (index + 1) % kSamplesPerMetric;
  if (buffer.count < kSamplesPerMetric) {
    buffer.count++;
  }
}

void recordMetricUs(MetricBufferUs &buffer, uint32_t valueUs) {
  const size_t index = buffer.nextIndex;
  buffer.values[index] = clampMetricValueUs(valueUs);
  buffer.seconds[index] = millis() / 1000UL;
  buffer.nextIndex = (index + 1) % kSamplesPerMetric;
  if (buffer.count < kSamplesPerMetric) {
    buffer.count++;
  }
}

void buildMetricSummaryMs(const MetricBufferMs &buffer, LatencyMetricSummary &summary, uint32_t nowSeconds) {
  summary = {};
  if (buffer.count == 0) {
    return;
  }

  uint32_t sum = 0;
  uint16_t minValue = 0;
  uint16_t maxValue = 0;
  size_t eligible = 0;
  for (size_t i = 0; i < buffer.count; ++i) {
    const uint32_t sampleSeconds = buffer.seconds[i];
    if (sampleSeconds > nowSeconds || nowSeconds - sampleSeconds > kWindowSeconds) {
      continue;
    }

    const uint16_t value = buffer.values[i];
    if (eligible == 0) {
      minValue = value;
      maxValue = value;
    } else {
      if (value < minValue) minValue = value;
      if (value > maxValue) maxValue = value;
    }
    sum += value;
    sTmpSortedValuesMs[eligible] = value;
    eligible++;
  }

  if (eligible == 0) {
    return;
  }

  qsort(sTmpSortedValuesMs, eligible, sizeof(uint16_t), compareUint16);
  const size_t p95Index = (eligible * 95 + 99) / 100;
  const size_t clampedP95Index = p95Index == 0 ? 0 : ((p95Index - 1) < eligible ? (p95Index - 1) : (eligible - 1));

  summary.samples = static_cast<uint32_t>(eligible);
  summary.minMs = minValue;
  summary.avgMs = sum / static_cast<uint32_t>(eligible);
  summary.p95Ms = sTmpSortedValuesMs[clampedP95Index];
  summary.maxMs = maxValue;
}

void buildMetricSummaryUs(const MetricBufferUs &buffer, LatencyMetricSummaryUs &summary, uint32_t nowSeconds) {
  summary = {};
  if (buffer.count == 0) {
    return;
  }

  uint64_t sum = 0;
  uint32_t minValue = 0;
  uint32_t maxValue = 0;
  size_t eligible = 0;
  for (size_t i = 0; i < buffer.count; ++i) {
    const uint32_t sampleSeconds = buffer.seconds[i];
    if (sampleSeconds > nowSeconds || nowSeconds - sampleSeconds > kWindowSeconds) {
      continue;
    }

    const uint32_t value = buffer.values[i];
    if (eligible == 0) {
      minValue = value;
      maxValue = value;
    } else {
      if (value < minValue) minValue = value;
      if (value > maxValue) maxValue = value;
    }
    sum += value;
    sTmpSortedValuesUs[eligible] = value;
    eligible++;
  }

  if (eligible == 0) {
    return;
  }

  qsort(sTmpSortedValuesUs, eligible, sizeof(uint32_t), compareUint32);
  const size_t p95Index = (eligible * 95 + 99) / 100;
  const size_t clampedP95Index = p95Index == 0 ? 0 : ((p95Index - 1) < eligible ? (p95Index - 1) : (eligible - 1));

  summary.samples = static_cast<uint32_t>(eligible);
  summary.minUs = minValue;
  summary.avgUs = static_cast<uint32_t>(sum / static_cast<uint64_t>(eligible));
  summary.p95Us = sTmpSortedValuesUs[clampedP95Index];
  summary.maxUs = maxValue;
}

}  // namespace

void videoLatencyRecordCaptureWaitMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sCaptureWaitMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordProducerCopyMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sProducerCopyMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordLatestLockWaitMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sLatestLockWaitMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordFrameAgeBeforeSendMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sFrameAgeBeforeSendMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordSendBoundaryMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sSendBoundaryMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordSendHeaderMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sSendHeaderMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordSendPayloadMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sSendPayloadMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordStreamLoopMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sStreamLoopMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordE2eEstimateMs(uint32_t valueMs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricMs(sE2eEstimateMetric, valueMs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordProducerCopyUs(uint32_t valueUs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricUs(sProducerCopyUsMetric, valueUs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordLatestLockWaitUs(uint32_t valueUs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricUs(sLatestLockWaitUsMetric, valueUs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordSendBoundaryUs(uint32_t valueUs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricUs(sSendBoundaryUsMetric, valueUs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordSendHeaderUs(uint32_t valueUs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricUs(sSendHeaderUsMetric, valueUs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyRecordSendPayloadUs(uint32_t valueUs) {
  portENTER_CRITICAL(&sVideoLatencyMux);
  recordMetricUs(sSendPayloadUsMetric, valueUs);
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyIncrementCopyFrameMiss() {
  portENTER_CRITICAL(&sVideoLatencyMux);
  sCopyFrameMissCount++;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyIncrementNoNewFramePoll() {
  portENTER_CRITICAL(&sVideoLatencyMux);
  sNoNewFramePollCount++;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyIncrementLatestMutexTimeout() {
  portENTER_CRITICAL(&sVideoLatencyMux);
  sLatestMutexTimeoutCount++;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyIncrementSlowSendStrike() {
  portENTER_CRITICAL(&sVideoLatencyMux);
  sSlowSendStrikeCount++;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyIncrementBufferRealloc() {
  portENTER_CRITICAL(&sVideoLatencyMux);
  sBufferReallocCount++;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyIncrementFrameSkippedDueStale() {
  portENTER_CRITICAL(&sVideoLatencyMux);
  sFrameSkippedDueStale++;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyGetSnapshot(VideoLatencySnapshot &snapshot) {
  const uint32_t nowSeconds = millis() / 1000UL;
  portENTER_CRITICAL(&sVideoLatencyMux);
  buildMetricSummaryMs(sCaptureWaitMetric, snapshot.captureWaitMs, nowSeconds);
  buildMetricSummaryMs(sProducerCopyMetric, snapshot.producerCopyMs, nowSeconds);
  buildMetricSummaryMs(sLatestLockWaitMetric, snapshot.latestLockWaitMs, nowSeconds);
  buildMetricSummaryMs(sFrameAgeBeforeSendMetric, snapshot.frameAgeBeforeSendMs, nowSeconds);
  buildMetricSummaryMs(sSendBoundaryMetric, snapshot.sendBoundaryMs, nowSeconds);
  buildMetricSummaryMs(sSendHeaderMetric, snapshot.sendHeaderMs, nowSeconds);
  buildMetricSummaryMs(sSendPayloadMetric, snapshot.sendPayloadMs, nowSeconds);
  buildMetricSummaryMs(sStreamLoopMetric, snapshot.streamLoopMs, nowSeconds);
  buildMetricSummaryMs(sE2eEstimateMetric, snapshot.e2eEstimateMs, nowSeconds);

  buildMetricSummaryUs(sProducerCopyUsMetric, snapshot.producerCopyUs, nowSeconds);
  buildMetricSummaryUs(sLatestLockWaitUsMetric, snapshot.latestLockWaitUs, nowSeconds);
  buildMetricSummaryUs(sSendBoundaryUsMetric, snapshot.sendBoundaryUs, nowSeconds);
  buildMetricSummaryUs(sSendHeaderUsMetric, snapshot.sendHeaderUs, nowSeconds);
  buildMetricSummaryUs(sSendPayloadUsMetric, snapshot.sendPayloadUs, nowSeconds);

  snapshot.copyFrameMissCount = sCopyFrameMissCount;
  snapshot.noNewFramePollCount = sNoNewFramePollCount;
  snapshot.latestMutexTimeoutCount = sLatestMutexTimeoutCount;
  snapshot.slowSendStrikeCount = sSlowSendStrikeCount;
  snapshot.bufferReallocCount = sBufferReallocCount;
  snapshot.frameSkippedDueStale = sFrameSkippedDueStale;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}

void videoLatencyReset() {
  portENTER_CRITICAL(&sVideoLatencyMux);
  memset(&sCaptureWaitMetric, 0, sizeof(sCaptureWaitMetric));
  memset(&sProducerCopyMetric, 0, sizeof(sProducerCopyMetric));
  memset(&sLatestLockWaitMetric, 0, sizeof(sLatestLockWaitMetric));
  memset(&sFrameAgeBeforeSendMetric, 0, sizeof(sFrameAgeBeforeSendMetric));
  memset(&sSendBoundaryMetric, 0, sizeof(sSendBoundaryMetric));
  memset(&sSendHeaderMetric, 0, sizeof(sSendHeaderMetric));
  memset(&sSendPayloadMetric, 0, sizeof(sSendPayloadMetric));
  memset(&sStreamLoopMetric, 0, sizeof(sStreamLoopMetric));
  memset(&sE2eEstimateMetric, 0, sizeof(sE2eEstimateMetric));

  memset(&sProducerCopyUsMetric, 0, sizeof(sProducerCopyUsMetric));
  memset(&sLatestLockWaitUsMetric, 0, sizeof(sLatestLockWaitUsMetric));
  memset(&sSendBoundaryUsMetric, 0, sizeof(sSendBoundaryUsMetric));
  memset(&sSendHeaderUsMetric, 0, sizeof(sSendHeaderUsMetric));
  memset(&sSendPayloadUsMetric, 0, sizeof(sSendPayloadUsMetric));

  sCopyFrameMissCount = 0;
  sNoNewFramePollCount = 0;
  sLatestMutexTimeoutCount = 0;
  sSlowSendStrikeCount = 0;
  sBufferReallocCount = 0;
  sFrameSkippedDueStale = 0;
  portEXIT_CRITICAL(&sVideoLatencyMux);
}
