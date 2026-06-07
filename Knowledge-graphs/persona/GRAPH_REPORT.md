# Graph Report - Agent Adam Chip/  (2026-05-15)

## Corpus Check
- 11 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 72 nodes · 118 edges · 8 communities
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]

## God Nodes (most connected - your core abstractions)
1. `AIIM Framework (Artificially Integrated Identity Matrix)` - 20 edges
2. `Action Mapping — AIIM State to Flora Scene` - 12 edges
3. `Adam Chip (Character)` - 11 edges
4. `Memory Schema — Episodic & Semantic Memory Spec` - 10 edges
5. `Personality AIIM — Adam Chip AIIM Configuration` - 9 edges
6. `Adam Chip Abilities & Capabilities` - 8 edges
7. `Adam Chip Origin Story` - 6 edges
8. `Mocumentary News Script` - 6 edges
9. `Echoes — Memory Fragment Pool` - 5 edges
10. `Technoflora (Symbiotic Extension)` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Adam Chip (Character)` --references--> `Metacognition / Self-Observation (se)`  [EXTRACTED]
  Agent Adam Chip/About/Identity.md → Agent Adam Chip/Engineering/Personality_AIIM.md
- `Prompt Builder (LLM Context Assembly)` --references--> `System Prompt Rules`  [INFERRED]
  Agent Adam Chip/Engineering/AIIM_Framework.md → Agent Adam Chip/About/System.md
- `AIIM Personality Formula (Encoded String)` --implements--> `AIIM Framework (Artificially Integrated Identity Matrix)`  [EXTRACTED]
  Agent Adam Chip/About/Identity.md → Agent Adam Chip/Engineering/AIIM_Framework.md
- `AIIM Aspect: pe — Sensory Input / Perception` --conceptually_related_to--> `Technoflora (Symbiotic Extension)`  [INFERRED]
  Agent Adam Chip/Engineering/AIIM_Framework.md → Agent Adam Chip/About/Abilities.md
- `Vision & Sensor Context (ctx.vision / ctx.sensors)` --conceptually_related_to--> `Technoflora (Symbiotic Extension)`  [INFERRED]
  Agent Adam Chip/About/System.md → Agent Adam Chip/About/Abilities.md

## Communities (8 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.16
Nodes (17): Adam Chip Abilities & Capabilities, Action Mapping — AIIM State to Flora Scene, AIIMState (Runtime State Object), Scene Cooldown & Sustain Rules, MCU Endpoint (PCA9685 Scene Control), SceneDirector (Python Module), SignalSnapshot (Orchestrator Input Object), Flora Scene: idle (Calm Breathing) (+9 more)

### Community 1 - "Community 1"
Cohesion: 0.22
Nodes (13): AIIM Aspect: em — Emotional State, AIIM Aspect: pe — Sensory Input / Perception, AIIM Personality Formula (Encoded String), Black Humor (Situational, Unmarked), Five Emotional States, First Cyborg (Pre-Death Identity), Rebirth / Third Form of Being, Symbiont (Partner Entity) (+5 more)

### Community 2 - "Community 2"
Cohesion: 0.29
Nodes (12): Chinese Lines — Injection Pool, Consolidator (Nightly LLM Cron Job), Memory Decay Policy (14-day rolling), EchoGate (Injection Gate Mechanism), Episode Schema (JSON Structure), Episodic Memory Layer (JSONL), Prompt Builder (LLM Context Assembly), Salience Formula (Episode Scoring) (+4 more)

### Community 3 - "Community 3"
Cohesion: 0.25
Nodes (9): AIIM Aspect: at — Attention, AIIM Aspect: be — Behavioral Reactions, AIIM Aspect: ho — Ethics, AIIM Aspect: im — Idea Generation, AIIM Aspect: lo — Empathy, AIIM Aspect: wi — Will / Goal-setting, AIIM Framework (Artificially Integrated Identity Matrix), AIIM Plane P — Personal (+1 more)

### Community 4 - "Community 4"
Cohesion: 0.36
Nodes (9): Cybernetic Remains (Artifact), Damaged / Erased Memory, Dubna Previous Installation (Static Diorama), Identity as Memory, Interactive Exhibition Installation, Russo-Chinese Scientific Consortium, Ship of Theseus Paradox (Identity Theme), Adam Chip Origin Story (+1 more)

### Community 5 - "Community 5"
Cohesion: 0.33
Nodes (6): AIIM Aspect: me — Memory (damaged), AIIM Plane B — Hardware / Body, Big Five Profile: O↑↑ C↑ E↓ A→ N↓, Enneagram: 5w4 (Investigator + Individualist), MBTI Profile: INTP-T (Logician, Turbulent), Personality AIIM — Adam Chip AIIM Configuration

### Community 6 - "Community 6"
Cohesion: 0.67
Nodes (3): AIIM Aspect: se — Metacognition (core), AIIM Plane I — Integration, Metacognition / Self-Observation (se)

### Community 7 - "Community 7"
Cohesion: 0.67
Nodes (3): AIIM Aspect: co — Logic & Analysis, AIIM Aspect: sp — Meaning & Purpose, AIIM Plane T — Transcendent

## Knowledge Gaps
- **12 isolated node(s):** `State: Sharpness / Edge (Резкость)`, `AIIM Aspect: wi — Will / Goal-setting`, `AIIM Aspect: ho — Ethics`, `AIIM Aspect: be — Behavioral Reactions`, `AIIM Aspect: at — Attention` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AIIM Framework (Artificially Integrated Identity Matrix)` connect `Community 3` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.355) - this node is a cross-community bridge._
- **Why does `Action Mapping — AIIM State to Flora Scene` connect `Community 0` to `Community 2`, `Community 5`?**
  _High betweenness centrality (0.306) - this node is a cross-community bridge._
- **Why does `Personality AIIM — Adam Chip AIIM Configuration` connect `Community 5` to `Community 0`, `Community 1`, `Community 3`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.272) - this node is a cross-community bridge._
- **What connects `State: Sharpness / Edge (Резкость)`, `AIIM Aspect: wi — Will / Goal-setting`, `AIIM Aspect: ho — Ethics` to the rest of the system?**
  _12 weakly-connected nodes found - possible documentation gaps or missing edges._