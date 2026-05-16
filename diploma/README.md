# Diploma Project Structure

## 📂 Directory Guide

### `config/`
Project configuration and instructions
- `Claude.md` — Main instructions for diploma work (role, workflow, rules)
- `.dependencies.yaml` — Dependencies tracking
- `.gitignore` — Git ignore rules

### `prompts/`
Writing prompts and methodology
- `00_synthesis.md` — Synthesis workflow
- `01_diploma_to_architecture.md` — Phase 1: Extract engineering from theory
- `02_code_to_diploma_verification.md` — Phase 2: Verify theory against runtime
- `03_write_chapter3.md` — Phase 3: Chapter 3 writing guide

### `chapters/`
Complete diploma chapters
- `ch00_introduction.md` — Introduction
- `ch01_chapter1.md` — Chapter 1: Philosophical and technological foundations
- `ch02_chapter2.md` — Chapter 2: Architectural models
- `ch03_chapter3.md` — Chapter 3: Implementation
- `ch99_bibliography.md` — Bibliography
- `_drafts/` — Raw/draft versions of chapters

### `chapter-3/`
Detailed Chapter 3 sections (hierarchical breakdown)
```
3.1 — Conceptual foundations
  3.1.1 Concept basis
  3.1.2 Agent behavior logic
  3.1.3 Agent functions
3.2 — System architecture
  3.2.1 Architecture overview
  3.2.2 Software stack
  3.2.3 System prompt & identity
  3.2.4 Memory & context
  3.2.5 Perception & speech
  3.2.6 Command layer
3.3 — Physical implementation
  3.3.1 Installation setup
  3.3.2 Perception & motor layers
  3.3.3 Microcontroller programming
  3.3.4 Interaction scenarios
  3.3.5 Testing procedures
3.4 — Evaluation & metrics
  3.4.1 Testing methodology
  3.4.2 Role normativity metrics
  3.4.3 Memory & temporal metrics
  3.4.4 Interaction & initiative metrics
  3.4.5 Limitations & interpretation
```

### `output/`
Generated analysis and verification results
- `project-analysis/` — Stage 1 output (architecture extraction)
- `project-verification/` — Stage 2 output (code-to-theory verification)
- `graphify-out/` — Code graph analysis

### `research/`
Working documents, audits, and reference materials
- `CHAPTER3_PROBLEMS_AND_ROADMAP.md` — Chapter 3 roadmap
- `CHAPTER3_RESOURCES_AUDIT.md` — Resource audit
- `ESP32_PINOUT_TABLE.md` — Hardware pin configuration
- `PROACTIVE_SPEECH_MAPPING.md` — Proactive speech implementation mapping
- `GAPS_AND_COMPROMISES_PRIORITY.md` — Priority gaps & compromises
- `*.md` — Various audit and analysis documents

### `assets/`
Diagrams, figures, and media
- Reserved for diagrams referenced in text
- Use relative paths: `[Figure 3.2.1](assets/diagrams/architecture.svg)`

### `tools/`
Utility scripts
- `consolidate_chapters.py` — Combine chapter files
- `convert_pdf.py`, `convert_pdf_pymupdf.py` — PDF processing
- `split_diploma.py` — Split diploma into sections
- `inspect_structure.py` — Analyze diploma structure

### Root level
Main files
- `Diploma.md` — Full diploma text (Docling output)
- `Diploma.pdf` — Diploma PDF version
- `Diploma_bibliography.md` — Bibliography extracted
- `Diploma_figures.md` — Figures index

---

## 🔄 Workflow

1. **Read**: Start in `config/Claude.md` for instructions
2. **Analyze**: Use `output/project-analysis/` for architecture extraction
3. **Verify**: Cross-check with `output/project-verification/`
4. **Reference**: Consult `research/` files for detailed mappings
5. **Write**: Add content to `chapters/` or `chapter-3/`
6. **Check**: Use prompts in `prompts/` for quality gates

---

## 📊 Graphs (Ready to query)

- `graphify-out/graph.json` — Code architecture graph
- `graphify-out-persona/graph.json` — Agent persona graph
- Use `/graphify query "<concept>"` for evidence lookup

---

Generated: 2026-05-16
