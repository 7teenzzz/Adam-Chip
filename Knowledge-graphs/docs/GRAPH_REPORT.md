# Graph Report - raw/  (2026-05-15)

## Corpus Check
- 2 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 36 nodes · 43 edges · 7 communities
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 4 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]

## God Nodes (most connected - your core abstractions)
1. `Jetson AI Lab` - 14 edges
2. `Silero v5_5_ru (Russian TTS)` - 9 edges
3. `Silero Models (snakers4)` - 7 edges
4. `NVIDIA Jetson (Edge Hardware Platform)` - 4 edges
5. `Jetson Orin NX 16GB` - 4 edges
6. `llama.cpp (LLM Inference Engine)` - 3 edges
7. `VILA 1.5 (Vision-Language Model)` - 3 edges
8. `WhisperX (ASR with CUDA)` - 3 edges
9. `CUDA-enabled PyTorch (aarch64)` - 3 edges
10. `Jetson AGX Orin 64GB` - 2 edges

## Surprising Connections (you probably didn't know these)
- `Jetson AI Lab` --references--> `Jetson Orin NX 16GB`  [EXTRACTED]
  raw/jetson-ai-lab.md → raw/jetson-ai-lab.md  _Bridges community 2 → community 5_
- `Jetson AI Lab` --references--> `llama.cpp (LLM Inference Engine)`  [EXTRACTED]
  raw/jetson-ai-lab.md → raw/jetson-ai-lab.md  _Bridges community 2 → community 4_
- `Jetson AI Lab` --references--> `VILA 1.5 (Vision-Language Model)`  [EXTRACTED]
  raw/jetson-ai-lab.md → raw/jetson-ai-lab.md  _Bridges community 2 → community 6_
- `Jetson AI Lab` --references--> `WhisperX (ASR with CUDA)`  [EXTRACTED]
  raw/jetson-ai-lab.md → raw/jetson-ai-lab.md  _Bridges community 2 → community 3_
- `ctranslate2 (WhisperX CUDA backend)` --references--> `Jetson Orin NX 16GB`  [EXTRACTED]
  raw/jetson-ai-lab.md → raw/jetson-ai-lab.md  _Bridges community 5 → community 3_

## Communities (7 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.22
Nodes (9): Silero Output Sample Rate 24000 Hz, Silero Speaker: aidar, Silero Speaker: baya, Silero Speaker: eugene, Silero Speaker: kseniya, Silero Speaker: xenia, SSML Support (Speech Synthesis Markup Language), Automatic Stress and Homograph Handling (Russian) (+1 more)

### Community 1 - "Community 1"
Cohesion: 0.29
Nodes (7): CC-NC-BY License (Main Repo Models), Jetson Install Order Constraint (PyTorch first, then --no-deps silero), MIT License (V5 CIS Base), Silero Models (snakers4), PyTorch Hub (torch.hub.load), Silero V3 Models (v3_en, v3_de, v3_es, v3_fr), Silero V4 Models (v4_ru, v4_cyrillic, v4_indic)

### Community 2 - "Community 2"
Cohesion: 0.47
Nodes (6): JetPack SDK, Jetson AGX Orin 64GB, Jetson AI Lab, Jetson Orin Nano, NVIDIA Jetson (Edge Hardware Platform), TensorRT-LLM

### Community 3 - "Community 3"
Cohesion: 0.4
Nodes (5): CUDA-enabled PyTorch (aarch64), Jetson Containers Project (dusty-nv), Silero TTS, WhisperX (ASR with CUDA), ctranslate2 (WhisperX CUDA backend)

### Community 4 - "Community 4"
Cohesion: 0.67
Nodes (3): Gemma (LLM via llama.cpp), llama.cpp (LLM Inference Engine), Model Quantization (GGUF, AWQ, INT4)

### Community 5 - "Community 5"
Cohesion: 0.67
Nodes (3): Exhibition AI Agent (multimodal camera+audio), Jetson Orin NX 16GB, MAXN Power Mode (nvpmodel -m 0 + jetson_clocks)

### Community 6 - "Community 6"
Cohesion: 0.67
Nodes (3): LLaVA (Vision-Language Model), nano_llm Docker Container, VILA 1.5 (Vision-Language Model)

## Knowledge Gaps
- **18 isolated node(s):** `JetPack SDK`, `nano_llm Docker Container`, `Gemma (LLM via llama.cpp)`, `TensorRT-LLM`, `Silero Speaker: eugene` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Jetson AI Lab` connect `Community 2` to `Community 3`, `Community 4`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.242) - this node is a cross-community bridge._
- **Why does `Silero v5_5_ru (Russian TTS)` connect `Community 0` to `Community 1`?**
  _High betweenness centrality (0.141) - this node is a cross-community bridge._
- **Why does `Silero Models (snakers4)` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **What connects `JetPack SDK`, `nano_llm Docker Container`, `Gemma (LLM via llama.cpp)` to the rest of the system?**
  _18 weakly-connected nodes found - possible documentation gaps or missing edges._