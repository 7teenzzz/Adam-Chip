// Panel: #/diagnostics/metrics
// Thin wrapper — mounts the existing metrics.js content (Метрики/Аналитика/Промты
// tabs) plus the Log Viewer status block from logs.js.

import { mount as mountMetrics } from "../metrics.js";
import { mount as mountLogs } from "../logs.js";

export function mount(target) {
  const teardownMetrics = mountMetrics(target);
  const teardownLogs = mountLogs(target);

  return function teardown() {
    if (typeof teardownMetrics === "function") teardownMetrics();
    if (typeof teardownLogs === "function") teardownLogs();
  };
}
