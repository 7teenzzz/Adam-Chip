# Subconscious Processor: Dual-Task VLM Architecture
**Research Date:** 2026-06-11  
**Phase:** 36 (SubconsciousProcessor — речевое подсознание)  
**Branch:** `subconscious-symbiont`  

---

## Executive Summary

Adam Chip requires splitting the current single-pass VLM request into **two independent tasks** that run on Cosmos Reason2-2B:

1. **Task A (Visual Encoder)** — analyzes scene for `[ctx.vision]` state (people detection, positioning, demographics)
2. **Task B (AIIM Modulator)** — generates `emotion_hint` + `flora_preset` based on scene + сontext + visitor speech acoustics

Both tasks are stateless and non-blocking. They feed into the Orchestrator's AIIM pipeline at different points.

---

## Current Architecture (Pre-Phase 36)

### VLM Integration (Today)

- **Service**: Cosmos Reason2-2B via llama-server @ port 8051
- **Timeout**: 20 sec, `max_new_tokens: 80`
- **Current prompt location**: `System/Config.json` → `services.vlm.prompt`

**Current prompt:**
```
You are an eyes of interactive art installation "Adam Chip". Look at the image and write ONE short English sentence describing what you actually see, using this structure:
Scene: <people count and position>. Engagement: <one of: none, watching, approaching, leaving, interacting>.

Reference examples (style only — do not copy):
- Scene: 2 people near installation, one leaning in. Engagement: watching.
- Scene: 1 person walking away from the camera. Engagement: leaving.
- Scene: empty room. Engagement: none.

Output only the final sentence about this specific image. Never output placeholders 
like <people count and position> or angle-bracket tokens. English only.
```

### Response Parsing

**Location**: `System/adam/inference.py` lines 775–802 (`VLMClient.describe_jpeg()`)

**Format expected**: `"Scene: <description>. Engagement: <one of: none/watching/approaching/leaving/interacting>."`

**Rejection filters**:
- CJK ideographs ≥ 3 → rejected (model sometimes outputs Chinese)
- Placeholder echoes matching `\[(?:count\+position|none/watching|<[^>]+>)\]` → rejected
- Stale response (takes > 20s) → discarded

**Current flow in Orchestrator**:
1. `SceneWorker._run()` line ~1940: calls `vlm_client.describe_jpeg(jpeg, prev_scene=...)`
2. Response → `SceneDescriptionBuffer.push()` (deduplication)
3. `scene_cache.text` updated → injected as `[ctx.vision]` in `PromptBuilder._build_context_body()` line 256

---

## Proposed Architecture (Phase 36+)

### Two Independent VLM Tasks

```
┌─────────────────────────────────────────────────────────────────┐
│ COSMOS REASON2-2B (Port 8051)                                   │
│                                                                  │
│  Task A (Visual)          Task B (AIIM Modulator)              │
│  ───────────────          ──────────────────────               │
│  JPEG + prompt_A    ──┬──  JPEG + Scene(A) + Speech + prompt_B │
│  → Structural      │    → Emotional signal JSON                │
│    description      │                                           │
│  (people, poses)    │    Returns:                              │
│                     │    {emotion_hint, flora_mode,            │
│  Returns:           │     intensity, reasoning}                 │
│  "3 adults near,    └──                                        │
│   2 speaking,          ◄ Runs after Task A completes           │
│   child in corner"  (sequential, not parallel)                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Both tasks feed the Orchestrator's AIIM pipeline:
- Task A  → [ctx.vision] block in prompt
- Task B  → emotion_hint (conditional premod) + flora P2 preset
```

### Decision: Sequential, Not Parallel

**Rationale:**
1. **Latency budget**: 764 ms/frame is sustainable; 2×764 ms overhead is too high
2. **Semantic dependency**: Task B uses Task A's output (scene structure)
3. **Frequency**: Task A runs every `scene_interval_sec=4`; Task B only when `asr_final` event fires
4. **Cost**: Running Task B only on speech events (not continuous) justifies the extra call

**Execution timeline:**
```
T+0 ms    : JPEG captured
T+0–764ms : Task A processes frame → scene description
T+764ms   : Scene description cached in [ctx.vision]
T+764ms   : (await next asr_final event)
T+3000ms  : Visitor speaks (asr_final event fires)
T+3000ms  : Task B begins (concurrent with LLM thinking)
            Inputs: Task A output + ASR transcript + acoustic features
T+3764ms  : Task B completes → emotion_hint + flora_preset
T+3764ms  : SubconsciousAnalyzer merges signals into AIIM state
```

---

## Task A — Visual Channel Prompt

**Goal**: Structured scene description optimized for Adam's `[ctx.vision]` context block.

### Prompt Text

```
You are a fixed camera in an interactive art installation. Analyze the image and 
write a FACTUAL scene description in exactly this format:

Format: {N} people; [demographics and positions]; atmosphere.

Rules:
- Count people in frame (0–N). Use "empty" if count=0.
- For each person: estimated age tier (CHILD/YOUNG/ADULT/ELDER), visible gender marker 
  (male/female/unclear), clothing (color + type), activity (standing/sitting/leaning/speaking/silent).
- Positions: describe spatial relationships (near installation / left side / center / back / 
  approaching / leaving).
- Atmosphere: one phrase about lighting, motion level, or spatial density.

Keep under 80 words. Facts only—no interpretation. English only.

Examples (style reference only):
- "3 adults; two in mid-30s (male/female, casual dark wear), one ELDER (female, blue jacket). 
  One speaking, two listening, all clustered at center. Bright overhead light, calm."
- "1 YOUNG adult female (colorful hoodie) near main screen, leaning in. CHILD (male, 
  striped shirt) approaching from left, curious. Daytime soft light."
- "Empty room. Standard gallery lighting. Quiet."

Output ONLY the scene description sentence. Do NOT include explanations, metadata, or 
confidence estimates.
```

### Expected Output Examples

```
✓ "3 people; two adults (30s, casual) speaking at center installation, 
   one elder (female, red sweater) watching from bench on right. 
   Bright daylight, moderate movement."

✓ "2 young adults (male/female, colorful hoodies) leaning toward main screen, 
   very engaged. Dark gallery space, focused attention."

✓ "Empty gallery. Standard lighting. Still."

✗ "Scene: 3 people. Engagement: watching." 
   (Old format—reject, trigger re-prompt)

✗ "[CHILD/YOUNG/ADULT/ELDER] near installation..." 
   (Placeholder echo—reject)
```

### Parsing & Validation

**Location to implement**: `System/adam/inference.py` → new method `VLMClient.describe_scene_structure()`

**Validation checks**:
1. Word count ≤ 120 (hard limit)
2. No CJK characters ≥ 3 (same as current)
3. No placeholder patterns: `[...]`, `<...>`, escaped labels like `CHILD/YOUNG` unresolved
4. Optional: Extract count using regex `(\d+)\s+people|^empty` for telemetry

**On validation failure**: Keep previous `scene_cache.text`, log error, try again next cycle

---

## Task B — AIIM Modulator Prompt

**Goal**: Generate structured emotional & flora control signal from scene + speech.

### Prompt Text

```
You are analyzing an interactive moment in an art installation. Given:
1. Current scene description (from camera)
2. Visitor's spoken transcript (if any)
3. Acoustic tone (speech rate, volume variability, pause patterns)

Produce a structured emotional response signal (JSON).

Scene: {scene_description_from_task_A}
Transcript: {asr_transcript_or_empty}
Acoustic tone: {rms_mean} dB mean, {rms_peak} dB peak, {silence_ratio}% silence

Your task: Generate a brief EMOTIONAL SIGNAL that Adam's subconsciousness uses to 
pre-modulate his emotional state and control ambient flora (lights).

Output VALID JSON only, no commentary:
{{
  "emotion_hint": <one of: "curious", "warm", "unease", "sharp", "calm">,
  "flora_mode": <one of: "breathe", "accent", "attentive", "think_pulse">,
  "intensity": <0.0 to 1.0>,
  "reasoning": "<one sentence explaining the choice>"
}}

Mapping guidelines:
- "curious": scene shows approach/engagement + questions in transcript OR unclear intent
- "warm": calm scene + positive tone in speech OR prolonged stillness near installation
- "unease": sudden movement/appearance + hesitation in speech OR rapid rms peaks
- "sharp": focused attention + assertive speech OR intense acoustic variation
- "calm": empty space OR minimal speech with low rms + high silence ratio

Flora:
- "accent": sudden movement detected (people appeared/approaching)
- "attentive": visitor is speaking directly to installation or leaning in
- "think_pulse": complex question or technical interest in transcript
- "breathe": default idle state when no visitor or very calm scene

Intensity: 0.0 (whisper-quiet, barely active) → 1.0 (maximum arousal/brightness)

Critical: If transcript is empty or acoustic confidence is low (<0.3), do NOT 
guess—prefer "calm" + "breathe" + 0.3 intensity.

Output ONLY the JSON object. No markdown, no extra text.
```

### Expected Output Examples

```json
{
  "emotion_hint": "curious",
  "flora_mode": "attentive",
  "intensity": 0.7,
  "reasoning": "Visitor leaning in with clear question about installation mechanics."
}
```

```json
{
  "emotion_hint": "calm",
  "flora_mode": "breathe",
  "intensity": 0.2,
  "reasoning": "Empty gallery, no active engagement detected."
}
```

```json
{
  "emotion_hint": "sharp",
  "flora_mode": "think_pulse",
  "intensity": 0.8,
  "reasoning": "Rapid speech with technical questions, high acoustic energy."
}
```

### Parsing & Validation

**Location to implement**: `System/adam/inference.py` → new method `VLMClient.generate_aiim_signal()`

**JSON schema** (in code):
```python
@dataclass
class SubconsciousSignal:
    emotion_hint: Literal["curious", "warm", "unease", "sharp", "calm"]
    flora_mode: Literal["breathe", "accent", "attentive", "think_pulse"]
    intensity: float  # 0.0–1.0, clamp if out of range
    reasoning: str    # optional, logged for diagnostics
```

**Validation**:
1. Valid JSON parse (reject if malformed)
2. `emotion_hint` in allowed set
3. `flora_mode` in allowed set  
4. `intensity` numeric, clamp to [0.0, 1.0]
5. `reasoning` field optional (ignore if missing)

**On validation failure**: Emit error event, return neutral signal:
```python
SubconsciousSignal(
    emotion_hint="calm",
    flora_mode="breathe",
    intensity=0.3,
    reasoning="VLM response parse failure, defaulting to neutral."
)
```

---

## Integration Architecture: SubconsciousAnalyzer

**New module**: `System/adam/subconscious.py`

```python
class SubconsciousAnalyzer:
    """Stateless analyzer that merges Task A + Task B outputs into AIIM control signals."""
    
    async def analyze(
        self,
        transcript: str,
        acoustic_features: AcousticFeatures,
        scene_text: str,
        vlm_client: VLMClient,
    ) -> SubconsciousSignal:
        """
        Execute Task B: generate emotion_hint + flora_preset from scene + speech.
        
        Args:
            transcript: ASR final output (or empty string)
            acoustic_features: RMS mean/peak/silence_ratio from PCM analysis
            scene_text: Output from Task A (scene description)
            vlm_client: Cosmos VLM client
            
        Returns:
            SubconsciousSignal with emotion_hint, flora_mode, intensity
        """
        # Build Task B prompt with all inputs
        prompt = self._build_task_b_prompt(
            scene_text=scene_text,
            transcript=transcript,
            acoustic_features=acoustic_features,
        )
        
        # Call Cosmos with structured output request
        json_str = await vlm_client.generate_aiim_signal(
            jpeg_bytes=None,  # Task B doesn't need image (uses scene_text instead)
            prompt=prompt,
        )
        
        # Parse and validate
        signal = self._parse_signal_json(json_str)
        
        # Apply post-processing rules
        signal = self._apply_acoustic_dampening(signal, acoustic_features)
        
        return signal
    
    def _build_task_b_prompt(
        self,
        scene_text: str,
        transcript: str,
        acoustic_features: AcousticFeatures,
    ) -> str:
        """Format Task B prompt with actual values."""
        # Implemented in full below
        pass
    
    def _apply_acoustic_dampening(
        self,
        signal: SubconsciousSignal,
        features: AcousticFeatures,
    ) -> SubconsciousSignal:
        """Reduce intensity if acoustic confidence is low."""
        if features.silence_ratio > 0.7:  # mostly silence
            signal.intensity *= 0.5
        return signal
```

---

## VLM Client Extensions (System/adam/inference.py)

### New Method: `describe_scene_structure()`

```python
async def describe_scene_structure(self, jpeg_bytes: bytes) -> str:
    """Task A: Generate structured scene description."""
    # Reuse existing _call_vlm infrastructure
    # Prompt is TASK_A_PROMPT (defined in inference.py top)
    # Return format: "N people; [details]"
```

### New Method: `generate_aiim_signal()`

```python
async def generate_aiim_signal(
    self, 
    prompt: str,  # Pre-built Task B prompt with actual values
) -> str:
    """Task B: Generate JSON emotional signal (no image needed)."""
    # Call llama-server with text-only prompt
    # Request structured JSON output via stop sequences or grammar
    # Return raw JSON string (VLMClient does NOT parse—caller validates)
```

### Note on llama-server Structured Output

**Challenge**: Cosmos Reason2-2B's llama-server may not support constrained JSON generation.

**Workarounds**:
1. **Stop sequence**: Include `\n}\n` in prompt, force model to halt
2. **Grammar constraint**: If llama-server supports JSON grammar—use it
3. **Post-processing**: Regex extraction of `{...}` block from free text
4. **Fallback**: If JSON parsing fails, default to neutral signal (see validation above)

---

## Execution Points in Orchestrator

### Point 1: Task A (Continuous)

**Location**: `System/Orchestrator.py` line ~1940 (SceneWorker._run)

**Current code**:
```python
summary = (await self.vlm_client.describe_jpeg(jpeg, prev_scene=prev)).strip()
```

**After Phase 36**:
```python
# Task A: Scene structure
summary = (await self.vlm_client.describe_scene_structure(jpeg)).strip()
scene_cache.update(summary, meta)

# Task B: Deferred until asr_final event (see Point 2)
```

### Point 2: Task B (On ASR Final)

**Location**: `System/Orchestrator.py` line ~1779 (_transcribe_and_dispatch)

**Trigger**: ASR produces final transcript (`asr_final` event)

**New code** (conceptual):
```python
async def _transcribe_and_dispatch(self, pcm: bytes) -> None:
    # ... existing transcription logic ...
    
    if result_final:
        transcript = result_final.get("transcript", "").strip()
        
        # Compute acoustic features from PCM
        acoustic_features = compute_acoustic_features(pcm)
        
        # Trigger SubconsciousAnalyzer Task B
        if transcript:  # Only when there's speech
            signal = await subconscious_analyzer.analyze(
                transcript=transcript,
                acoustic_features=acoustic_features,
                scene_text=scene_cache.text,
                vlm_client=vlm,
            )
            event_log.append("subconscious_signal_generated", signal.as_dict())
            
            # Store for AIIM premod (applied in _run_dialogue_turn_locked)
            runtime_state["pending_subconscious_signal"] = signal
```

### Point 3: AIIM Integration

**Location**: `System/Orchestrator.py` line ~3445 (_run_dialogue_turn_locked)

**Current code**:
```python
emotion = emotion_machine.transition(
    transcript=transcript,
    current=session_state["aiim_state"].emotion,
)
```

**After Phase 36** (pseudocode):
```python
emotion = emotion_machine.transition(
    transcript=transcript,
    current=session_state["aiim_state"].emotion,
)

# Conditional premod: if no keyword-driven emotion, apply subconscious hint
signal: SubconsciousSignal = runtime_state.get("pending_subconscious_signal")
if signal and emotion_machine.last_transition_source == "":  # no keyword override
    if signal.intensity > 0.35:  # minimum confidence threshold
        emotion = signal.emotion_hint
        emotion_src = "subconscious"
        session_state["aiim_state"].emotion = emotion

# Flora P2 priority (deferred to Phase 36.04)
if signal and signal.flora_mode != "breathe":
    await flora_controller.push_preset_p2(signal.flora_mode, signal.intensity)
```

---

## Acoustic Features Pipeline

**New dataclass** (System/adam/subconscious.py):
```python
@dataclass
class AcousticFeatures:
    rms_mean: float      # dB, mean over segment
    rms_peak: float      # dB, max peak in segment
    silence_ratio: float # 0.0–1.0, ratio of silence to total
    zero_crossing_rate: float  # optional, for voice activity confidence
```

**Computation** (in _transcribe_and_dispatch, after ASR final):
```python
def compute_acoustic_features(pcm: bytes, sample_rate: int = 16000) -> AcousticFeatures:
    """Extract RMS and silence features from raw PCM."""
    # Convert bytes to int16 array
    pcm_int16 = np.frombuffer(pcm, dtype=np.int16)
    
    # RMS per frame (20ms windows)
    frame_size = sample_rate // 50  # 20 ms @ 16 kHz
    frames = [
        pcm_int16[i:i+frame_size]
        for i in range(0, len(pcm_int16), frame_size)
    ]
    
    rms_values = [np.sqrt(np.mean(f.astype(float)**2)) for f in frames]
    rms_db = [20 * np.log10(r + 1e-10) for r in rms_values]
    
    # Statistics
    rms_mean = np.mean(rms_db)
    rms_peak = np.max(rms_db)
    
    # Silence: frames below -40 dB
    silence_count = sum(1 for db in rms_db if db < -40)
    silence_ratio = silence_count / max(len(rms_db), 1)
    
    return AcousticFeatures(
        rms_mean=float(rms_mean),
        rms_peak=float(rms_peak),
        silence_ratio=float(silence_ratio),
    )
```

---

## Flora Priority System (Phase 36.04)

**Current state**: FloraController accepts events, "last one wins" (no priorities).

**Proposed P2 layer**:
```python
class FloraController:
    PRIORITY_IDLE = 1      # breathe, wake_bloom
    PRIORITY_SUBCONSCIOUS = 2  # emotion_hint premod
    PRIORITY_PIPELINE = 3      # voice_state transitions, llm_thinking
    
    async def push_preset_p2(
        self, 
        preset: str, 
        intensity: float,
    ) -> None:
        """Push from SubconsciousAnalyzer (P2 priority)."""
        if self._current_priority >= self.PRIORITY_PIPELINE:
            return  # Pipeline has priority
        if self._voice_state == "attentive":
            return  # Vibro always off during listening
        self._current_priority = self.PRIORITY_SUBCONSCIOUS
        await self._set_flora_state(preset, intensity)
```

---

## Configuration Changes (Config.json)

**No new parameters required** for Phase 36 core functionality.

**Optional tuning parameters** (Phase 36.04+):

```json
{
  "services": {
    "vlm": {
      "task_a_prompt": "...",  // Task A prompt (can be hot-reloaded)
      "task_b_prompt": "...",  // Task B prompt template
      "task_b_timeout_sec": 15,
      "task_b_enabled": true
    }
  },
  "tuning": {
    "subconscious": {
      "emotion_hint_weight": 0.35,  // Minimum confidence to apply premod
      "flora_p2_enabled": true,
      "observations_enabled": true   // For observations.jsonl writer
    }
  }
}
```

---

## Failure Modes & Resilience

| Failure | Mitigation |
|---------|-----------|
| Task A timeout (>20s) | Keep previous `scene_cache.text`; log error; skip one cycle |
| Task A produces Chinese | Reject per existing CJK filter; retry next cycle |
| Task B JSON malformed | Return neutral `SubconsciousSignal(calm, breathe, 0.3)` |
| Task B timeout | Skip AIIM premod; proceed with keyword-only emotion transition |
| No speech (empty transcript) | Task B not called; AIIM uses keyword-driven transition only |
| Acoustic feature extraction fails | Default `AcousticFeatures(0, 0, 0)`; Task B still runs (safe defaults) |

---

## Testing Strategy

### Unit Tests

1. **Prompt validation**: Task A/B prompts generate expected formats
2. **JSON parsing**: SubconsciousSignal parses valid/invalid JSON robustly
3. **Acoustic features**: Compute RMS/silence from PCM correctly
4. **Fallbacks**: Neutral signal on parse failure

### Integration Tests

1. **VLM round-trip**: E2E Task A + Task B on real Cosmos instance
2. **AIIM premod**: emotion_hint correctly merges into AIIMRuntimeState
3. **Flora P2**: preset pushes at right priority level
4. **Event flow**: subconscious_signal_generated event logged

### Manual Testing (Exhibition)

1. Empty gallery → `breathe`, emotion=`calm`
2. Visitor approaches → Task A detects movement; Task B (on speech) → `attentive`
3. Complex question → Task B → `think_pulse` + `curious`
4. Rapid, assertive speech → Task B → `sharp` + `accent`

---

## Phasing & Dependencies

### Phase 36 (SubconsciousProcessor)

**Delivers**:
- [x] Task A prompt + VLMClient.describe_scene_structure()
- [x] Task B prompt + VLMClient.generate_aiim_signal()
- [x] SubconsciousAnalyzer (subconscious.py)
- [x] AcousticFeatures computation
- [x] AIIM premod logic (emotion_hint merge)
- [ ] Flora P2 priority system (36.04)
- [ ] observations.jsonl writer (36.04)

### Phase 37 (VisitorRegistry)

**Depends on**: Phase 36 complete
**Uses**: SubconsciousSignal metadata for visitor profiling

### Phase 38 (Cosmos as Agent)

**Depends on**: Phase 36 + 37 complete
**Extends**: Task B to include scene_delta detection and pe/be aspect modulation

---

## Implementation Roadmap

1. **Week 1**: Task A prompt refinement, VLMClient methods, structural scene description tests
2. **Week 2**: Task B prompt, acoustic features pipeline, SubconsciousAnalyzer implementation
3. **Week 3**: AIIM premod integration, E2E testing on real Cosmos
4. **Week 4**: Flora P2 priority system, observations.jsonl writer, exhibition prep

---

## Appendix: Glossary

- **Task A (Visual)**: Cosmos call to extract scene structure (people, positions, atmosphere)
- **Task B (AIIM Modulator)**: Cosmos call to generate emotional signal + flora control
- **SubconsciousSignal**: Struct containing emotion_hint, flora_mode, intensity, reasoning
- **AcousticFeatures**: RMS mean/peak, silence ratio extracted from visitor's PCM
- **Premod**: Pre-modulation of emotion_hint from subconscious (applied if no keyword override)
- **P2 Flora**: Priority level 2 (subconscious) in flora controller (between idle P1 and pipeline P3)
- **[ctx.vision]**: Context block in LLM prompt containing scene description from Task A

---

**End of Research Document**
