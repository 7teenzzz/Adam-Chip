# Knowledge Graphs — Adam Chip Project

Central repository of knowledge graphs and reference documentation for the Adam Chip system.

## Structure

### Knowledge Graphs (Auto-Generated)

- **`code/`** — Jetson inference pipeline (System/adam/ + Orchestrator + Speech)
  - `graph.json` — Full code graph (646 nodes, VoiceLoopController god-node 42 edges)
  - `GRAPH_REPORT.md` — Structured analysis (god-nodes, communities, patterns)
  - `graph.html` — Interactive visualization
  - `semantic/` — Vector embeddings for semantic search

- **`esp32/`** — ESP32-S3 firmware (Subsystem/AdamsServer/)
  - `graph.json` — Firmware architecture (780 nodes, bootLogf god-node 32 edges)
  - `GRAPH_REPORT.md` — Embodiment verification (criterion 2.1.7)
  - `graph.html` — Interactive visualization
  - `semantic/` — Vector embeddings

- **`persona/`** — Agent personality model (Identity, AIIM, Memory Schema)
  - `graph.json` — Persona graph (Identity, AIIM, TuningStore nodes)
  - `GRAPH_REPORT.md` — Character consistency analysis
  - `graph.html` — Interactive visualization

- **`docs/`** — External documentation (Silero, Jetson AI Lab)
  - `graph.json` — Integration reference
  - `GRAPH_REPORT.md` — System dependencies
  - `graph.html` — Interactive visualization

- **`diploma/`** — Diploma theoretical concepts (Chapter 1–2 requirements)
  - `graph.json` — Maps diploma concepts to implementation requirements
  - `GRAPH_REPORT.md` — Criterion mapping
  - `graph.html` — Interactive visualization

### Reference Documentation (Manual)

- **`reference/`** — Technical deep dives
  - `AudioModule.md` — I2S RX/TX, ring buffers, audio health monitoring
  - `BootDiagnostics.md` — 10-step boot sequence, firmware initialization
  - `CameraStreamingPipeline.md` — OV5640 MJPEG streaming architecture
  - `Pca9685Control.md` — 16-ch PWM control, NVS persistence, scenes

## Quick Navigation

### For Architecture Overview
→ Start with `code/GRAPH_REPORT.md` (System/)

### For Embodiment Verification (Criterion 2.1.7)
→ See `esp32/GRAPH_REPORT.md` (firmware architecture)

### For Persona/Identity Consistency
→ See `persona/GRAPH_REPORT.md` (AIIM, tuning, identity model)

### For System Integration Details
→ See `reference/` for detailed technical dives

## Rebuilding Graphs

Graphs are auto-generated and should be rebuilt when underlying code changes.
**Serve temporary files (`.chunk_*.json`, `.graphify_uncached.txt`, `manifest.json`, `cost.json`) are excluded from git — see `.gitignore`.**

```bash
# Update code graph (run in repo root after System/ changes)
/graphify System/adam --mode deep

# Update ESP32 firmware graph
/graphify Subsystem/AdamsServer --mode deep

# Update persona graph (rare — only after Identity.md / Lore.md changes)
/graphify "Agent Adam Chip/About" --mode deep

# Update diploma requirements graph
/graphify .planning/diploma/ --mode deep
```

All graphs update in-place; no manual moves needed.

## Diploma References (Chapter 3)

Chapter 3 sections reference these graphs and documents:

| Section | Resource | Graph |
| ------- | -------- | ----- |
| 3.3.2 — Perception Layers | `reference/CameraStreamingPipeline.md`, `reference/AudioModule.md` | `code/GRAPH_REPORT.md` |
| 3.3.3 — Motor Layers | `reference/Pca9685Control.md` | `esp32/GRAPH_REPORT.md` |
| 3.3.4 — MCU Boot & Failover | `reference/BootDiagnostics.md` | `esp32/GRAPH_REPORT.md` |
| 3.3.5 — Interaction Scenario | ESP32 API routes in GRAPH_REPORT | `esp32/GRAPH_REPORT.md` |
| 3.3.6 — Diagnostics Integration | Jetson scripts | `code/GRAPH_REPORT.md` |
| Ch. 2 — Requirements Mapping | Theory ↔ Implementation | `diploma/GRAPH_REPORT.md` |

## Criterion Verification

Key system components that verify diploma criteria:

| Criterion | Component | God-Node | Edges | Graph |
| --------- | --------- | -------- | ----- | ----- |
| 2.1.1 — Autonomy | Voice Loop | VoiceLoopController | 42 | `code/` |
| 2.1.7 — Embodiment | Firmware Boot | bootLogf | 32 | `esp32/` |
| 3.4.x — Testing | Memory & Action | EpisodicMemory / ActionLayer | 29 | `code/` |

Full criterion ↔ implementation mapping: see `.planning/diploma/` and `diploma/GRAPH_REPORT.md`.
