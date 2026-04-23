#pragma once

#include <Arduino.h>
#include <cstdint>

struct LatencyMetricSummary {
  uint32_t samples = 0;
  uint32_t minMs = 0;
  uint32_t avgMs = 0;
  uint32_t p95Ms = 0;
  uint32_t maxMs = 0;
};

struct LatencyMetricSummaryUs {
  uint32_t samples = 0;
  uint32_t minUs = 0;
  uint32_t avgUs = 0;
  uint32_t p95Us = 0;
  uint32_t maxUs = 0;
};

struct VideoLatencySnapshot {
  LatencyMetricSummary captureWaitMs;
  LatencyMetricSummary producerCopyMs;
  LatencyMetricSummary latestLockWaitMs;
  LatencyMetricSummary frameAgeBeforeSendMs;
  LatencyMetricSummary sendBoundaryMs;
  LatencyMetricSummary sendHeaderMs;
  LatencyMetricSummary sendPayloadMs;
  LatencyMetricSummary streamLoopMs;
  LatencyMetricSummary e2eEstimateMs;
  LatencyMetricSummaryUs producerCopyUs;
  LatencyMetricSummaryUs latestLockWaitUs;
  LatencyMetricSummaryUs sendBoundaryUs;
  LatencyMetricSummaryUs sendHeaderUs;
  LatencyMetricSummaryUs sendPayloadUs;

  uint32_t copyFrameMissCount = 0;
  uint32_t noNewFramePollCount = 0;
  uint32_t latestMutexTimeoutCount = 0;
  uint32_t slowSendStrikeCount = 0;
  uint32_t bufferReallocCount = 0;
  uint32_t frameSkippedDueStale = 0;
};

void videoLatencyRecordCaptureWaitMs(uint32_t valueMs);
void videoLatencyRecordProducerCopyMs(uint32_t valueMs);
void videoLatencyRecordLatestLockWaitMs(uint32_t valueMs);
void videoLatencyRecordFrameAgeBeforeSendMs(uint32_t valueMs);
void videoLatencyRecordSendBoundaryMs(uint32_t valueMs);
void videoLatencyRecordSendHeaderMs(uint32_t valueMs);
void videoLatencyRecordSendPayloadMs(uint32_t valueMs);
void videoLatencyRecordStreamLoopMs(uint32_t valueMs);
void videoLatencyRecordE2eEstimateMs(uint32_t valueMs);
void videoLatencyRecordProducerCopyUs(uint32_t valueUs);
void videoLatencyRecordLatestLockWaitUs(uint32_t valueUs);
void videoLatencyRecordSendBoundaryUs(uint32_t valueUs);
void videoLatencyRecordSendHeaderUs(uint32_t valueUs);
void videoLatencyRecordSendPayloadUs(uint32_t valueUs);

void videoLatencyIncrementCopyFrameMiss();
void videoLatencyIncrementNoNewFramePoll();
void videoLatencyIncrementLatestMutexTimeout();
void videoLatencyIncrementSlowSendStrike();
void videoLatencyIncrementBufferRealloc();
void videoLatencyIncrementFrameSkippedDueStale();

void videoLatencyGetSnapshot(VideoLatencySnapshot &snapshot);
void videoLatencyReset();
