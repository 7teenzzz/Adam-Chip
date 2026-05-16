# Knowledge Graphs — Adam Chip Project

Central repository of knowledge graphs and reference documentation for the Adam Chip system.

## Structure

- **`code/`** — Jetson inference pipeline (System/adam/ + Orchestrator + Speech)
  - `graph.json`: Full code graph (646 nodes, VoiceLoopController god-node 42 edges)
  - Query: `/graphify query "<concept>"` against this graph

- **`esp32/`** — ESP32-S3 firmware (Subsystem/AdamsServer/)
  - `graph.json`: Firmware graph (780 nodes, bootLogf god-node 32 edges)
  - Used for embodiment criterion (2.1.7) verification

- **`persona/`** — Agent personality model (Identity, AIIM, Memory Schema)
  - `graph.json`: Persona graph (nodes: Identity, AIIM, TuningStore)

- **`docs/`** — External documentation graphs (Silero, Jetson AI Lab)
  - `graph.json`: Integration reference for external systems

- **`diploma-theory/`** — Diploma theoretical concepts (Chapter 1–2)
  - `graph.json`: Maps diploma concepts to implementation requirements

- **`reference/`** — Technical reference documents
  - `CameraStreamingPipeline.md` — OV5640 MJPEG streaming architecture
  - `AudioModule.md` — I2S RX/TX, ring buffers, audio health monitoring
  - `Pca9685Control.md` — 16-ch PWM control, NVS persistence, scenes
  - `NetworkAndFailover.md` — W5500 Ethernet + WiFi + AP failover
  - `BootDiagnostics.md` — 10-step boot sequence, firmware initialization

## Quick Navigation

### For Architecture Overview
→ Start with `code/GRAPH_REPORT.md` (System/)

### For Embodiment Verification (Criterion 2.1.7)
→ See `esp32/GRAPH_REPORT.md` (firmware architecture)

### For Persona/Identity Consistency
→ See `persona/GRAPH_REPORT.md` (AIIM, tuning, identity model)

### For System Integration Details
→ See `reference/` for detailed technical dives

## Updating Graphs

Graphs are built with `/graphify`:

```bash
# Update code graph after changes to System/
/graphify Knowledge-graphs/code/ --update

# Build ESP32 graph (firmware changes)
/graphify Subsystem/AdamsServer/ --mode deep
# Then move to Knowledge-graphs/esp32/

# Update diplomat theory graph
/graphify diploma/project-analysis/ --mode deep
# Then move to Knowledge-graphs/diploma-theory/
```

## References in Diploma Chapter 3

Chapter 3 sections reference these graphs:
- **3.3.2 Perception & Motor Layers**: See `reference/CameraStreamingPipeline.md`, `reference/AudioModule.md`, `reference/Pca9685Control.md`
- **3.3.3 MCU Programming**: See `reference/BootDiagnostics.md`, `reference/NetworkAndFailover.md`
- **3.3.4 Interaction Scenario**: MCU commands map to ESP32 API routes in `esp32/GRAPH_REPORT.md`
- **3.3.5 Installation Testing**: Diagnostics scripts query `code/graph.json`

## Evidence-Based Verification

All diploma criterion verifications link to specific nodes in these graphs:
- Criterion 2.1.1 (Autonomy): VoiceLoopController (42 edges), SessionWatcher
- Criterion 2.1.7 (Embodiment): bootLogf (32 edges, esp32/), MCUClient (25 edges, code/)
- Criterion 3.4.x (Testing metrics): EpisodicMemory (29 edges), ActionLayer

See `diploma/project-verification/by-criterion/` for full mapping.
