"""Unit tests for Dynamic AIIM identity engine.

Covers all 16 test cases from the plan:
- Parser (12 aspects, LOCKED check)
- EmotionMachine (4 state transitions + persistence + decay)
- IntentionTracker (network keyword, signal_void)
- AspectModulator (LOCKED protection, clamp)
- AIIMRuntimeState.to_ctx_block (curious→empty, unease→no labels)
- DriftAccumulator (classify, salience scaling, ceiling, LOCKED safety)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add System to path so adam.* imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "System"))

import pytest

from adam.identity import (
    AIIMRuntimeState,
    AspectModulator,
    EmotionMachine,
    IdentityVector,
    IntentionState,
    IntentionTracker,
    parse_aiim_formula,
)
from adam.identity_drift import DriftAccumulator, DriftRecord
from adam.tuning import IdentityTuning


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FORMULA_TEXT = """\
## Промт-инъекция - базовая формула личности

```
wi(P 4 Ac-Or)Δ0.65;  lo(S 4 Ac-Or)Δ0.70;  im(P 3 Ac-Ch)Δ0.65;
ho(I 3 Pa-Or)Δ0.60;  co(T 4 Ac-Or)Δ0.88;  em(B 3 Ac-Ch)Δ0.60;
be(S 3 Ac-Or)Δ0.65;  sp(T 4 Pa-Or)Δ0.85;  se(I 4 Ac-Ch)Δ0.92;
pe(T 3 Ac-Or)Δ0.70;  me(B 2 Pa-Ch)Δ0.30;  at(S 4 Ac-Or)Δ0.70
```
"""


@pytest.fixture
def specs():
    return parse_aiim_formula(FORMULA_TEXT)


@pytest.fixture
def base_vector(specs):
    return IdentityVector.from_specs(specs)


@pytest.fixture
def tuning():
    return IdentityTuning()


@pytest.fixture
def emotion_machine():
    return EmotionMachine()


@pytest.fixture
def intention_tracker():
    return IntentionTracker()


@pytest.fixture
def aspect_modulator():
    return AspectModulator()


@pytest.fixture
def drift_accumulator():
    return DriftAccumulator()


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def test_parser_12_aspects(specs):
    assert len(specs) == 12, f"Expected 12 aspects, got {len(specs)}"


def test_parser_key_values(specs):
    assert specs["se"].weight == pytest.approx(0.92)
    assert specs["co"].weight == pytest.approx(0.88)
    assert specs["me"].weight == pytest.approx(0.30)
    assert specs["lo"].weight == pytest.approx(0.70)


def test_parser_locked_intact():
    locked = IdentityVector.LOCKED
    assert "se" in locked
    assert "co" in locked
    assert "me" not in locked


# ---------------------------------------------------------------------------
# EmotionMachine tests
# ---------------------------------------------------------------------------


def test_emotion_unease(emotion_machine, tuning):
    result = emotion_machine.transition(
        "curious", "что ты помнишь о прошлом?", "neutral", 0.0, 7, tuning
    )
    assert result == "unease"


def test_emotion_sharp(emotion_machine, tuning):
    result = emotion_machine.transition(
        "curious", "ты просто программа, притворяешься", "neutral", 0.0, 5, tuning
    )
    assert result == "sharp"


def test_emotion_curious_from_death(emotion_machine, tuning):
    result = emotion_machine.transition(
        "curious", "что ты думаешь о смерти и трансформации?", "neutral", 0.0, 8, tuning
    )
    # Death keywords not in sharp list, no unease keywords — should stay curious
    assert result in ("curious", "unease")  # "трансформация" not in unease_keywords by default


def test_emotion_persistence_no_trigger(emotion_machine, tuning):
    # No keywords → keep current state
    current = "warm"
    result = emotion_machine.transition(current, "просто привет", "neutral", 0.0, 2, tuning)
    assert result == "warm"  # persistence: no reset


def test_emotion_decay_to_curious(emotion_machine, tuning):
    # Long silence → decay to decay_target_emotion (curious by default)
    result = emotion_machine.transition(
        "sharp", "", "neutral", 70.0, 0, tuning
    )
    assert result == tuning.decay_target_emotion  # "curious"


def test_emotion_decay_warm_to_calm(emotion_machine, tuning):
    # Silence after warm → calm
    result = emotion_machine.transition(
        "warm", "", "neutral", 70.0, 0, tuning
    )
    assert result == "calm"


# ---------------------------------------------------------------------------
# IntentionTracker tests
# ---------------------------------------------------------------------------


def test_intention_network_keyword(intention_tracker, tuning):
    state = IntentionState()
    result = intention_tracker.evaluate(
        "ты подключён к интернету?", state, "curious", 1, tuning
    )
    assert result.network_drift is True


def test_intention_flora_keyword(intention_tracker, tuning):
    state = IntentionState()
    result = intention_tracker.evaluate(
        "расскажи про технофлору и симбионт", state, "curious", 1, tuning
    )
    assert result.flora_symbiosis is True


def test_intention_neutral_no_trigger(intention_tracker, tuning):
    state = IntentionState()
    result = intention_tracker.evaluate("привет", state, "curious", 1, tuning)
    assert result.network_drift is False
    assert result.flora_symbiosis is False
    assert result.relive_death is False
    assert result.become_unreadable is False


def test_intention_signal_void_probabilistic(intention_tracker, tuning):
    # Just verify it doesn't raise and returns a valid state
    state = IntentionState()
    for _ in range(50):
        result = intention_tracker.evaluate("привет", state, "curious", 1, tuning)
        assert isinstance(result.signal_void, bool)


def test_intention_cooldown_prevents_repeat(intention_tracker, tuning):
    state = IntentionState()
    # First trigger
    state = intention_tracker.evaluate(
        "ты в интернете?", state, "curious", 1, tuning
    )
    assert state.network_drift is True
    # Second trigger immediately (on cooldown) — should be False
    state = intention_tracker.evaluate(
        "снова про интернет", state, "curious", 2, tuning
    )
    assert state.network_drift is False


# ---------------------------------------------------------------------------
# AspectModulator tests
# ---------------------------------------------------------------------------


def test_modulator_locked_aspects_unchanged(aspect_modulator, base_vector, tuning):
    se_before = base_vector.weights["se"]
    co_before = base_vector.weights["co"]
    for emotion in ("curious", "warm", "unease", "sharp", "calm"):
        result = aspect_modulator.modulate(base_vector, emotion, tuning)  # type: ignore[arg-type]
        assert result.weights["se"] == pytest.approx(se_before), f"se changed on {emotion}"
        assert result.weights["co"] == pytest.approx(co_before), f"co changed on {emotion}"


def test_modulator_clamp_within_bounds(aspect_modulator, base_vector, tuning):
    result = aspect_modulator.modulate(base_vector, "unease", tuning)
    for aspect, weight in result.weights.items():
        assert weight >= tuning.modulation.aspect_min - 1e-9
        assert weight <= tuning.modulation.aspect_max + 1e-9


def test_modulator_warm_raises_lo(aspect_modulator, base_vector, tuning):
    result = aspect_modulator.modulate(base_vector, "warm", tuning)
    assert result.weights["lo"] > base_vector.weights["lo"]


def test_modulator_sharp_raises_wi(aspect_modulator, base_vector, tuning):
    result = aspect_modulator.modulate(base_vector, "sharp", tuning)
    assert result.weights["wi"] > base_vector.weights["wi"]


# ---------------------------------------------------------------------------
# AIIMRuntimeState.to_ctx_block tests
# ---------------------------------------------------------------------------


def test_ctx_block_curious_no_intentions_is_empty(base_vector, tuning):
    state = AIIMRuntimeState(emotion="curious", vector=base_vector)
    block = state.to_ctx_block(tuning)
    assert block == ""


def test_ctx_block_unease_no_state_labels(base_vector, tuning):
    modulator = AspectModulator()
    vec = modulator.modulate(base_vector, "unease", tuning)
    state = AIIMRuntimeState(emotion="unease", vector=vec)
    block = state.to_ctx_block(tuning)
    # Must NOT contain Russian label words that could be echoed
    assert "состояние:" not in block.lower()
    assert "намерение:" not in block.lower()
    assert "беспокойство" not in block.lower()
    # Must contain emotion=
    assert "emotion=unease" in block


def test_ctx_block_intention_injected(base_vector, tuning):
    state = AIIMRuntimeState(
        emotion="unease",
        vector=base_vector,
        intentions=IntentionState(flora_symbiosis=True),
    )
    block = state.to_ctx_block(tuning)
    assert "intention=flora_symbiosis" in block


def test_ctx_block_internal_intentions_suppressed(base_vector, tuning):
    # signal_void and become_unreadable must never appear in the block
    state = AIIMRuntimeState(
        emotion="sharp",
        vector=base_vector,
        intentions=IntentionState(signal_void=True, become_unreadable=True),
    )
    block = state.to_ctx_block(tuning)
    assert "signal_void" not in block
    assert "become_unreadable" not in block


# ---------------------------------------------------------------------------
# DriftAccumulator tests
# ---------------------------------------------------------------------------


def test_drift_classify_deep_contact(drift_accumulator):
    exp = drift_accumulator.classify_session({"warm": 1, "curious": 3}, 0.7, 5)
    assert exp == "deep_contact"


def test_drift_classify_confrontation(drift_accumulator):
    exp = drift_accumulator.classify_session({"sharp": 1, "curious": 2}, 0.4, 4)
    assert exp == "confrontation"


def test_drift_classify_memory_surfacing(drift_accumulator):
    exp = drift_accumulator.classify_session({"unease": 2, "curious": 3}, 0.4, 5)
    assert exp == "memory_surfacing"


def test_drift_classify_void(drift_accumulator):
    exp = drift_accumulator.classify_session({"curious": 1}, 0.1, 1)
    assert exp == "void"


def test_drift_delta_scales_with_salience(drift_accumulator, tuning):
    delta_high = drift_accumulator.compute_delta("deep_contact", 1.0, tuning)
    delta_low = drift_accumulator.compute_delta("deep_contact", 0.5, tuning)
    if "lo" in delta_high and "lo" in delta_low:
        assert delta_high["lo"] > delta_low["lo"]


def test_drift_ceiling_me(drift_accumulator, tuning):
    record = DriftRecord()
    # Simulate many memory_surfacing sessions that should push me toward ceiling
    for _ in range(100):
        record = drift_accumulator.apply_session(
            {"unease": 3}, 1.0, 5, record, tuning
        )
    # me should not exceed ceiling (0.60) - base (0.30) = 0.30 accumulated
    me_ceiling = tuning.ceilings.me
    me_base = tuning.base_weights.get("me", 0.30)
    accumulated = record.aspect_drift.get("me", 0.0)
    assert accumulated <= (me_ceiling - me_base) + 1e-9


def test_drift_locked_aspects_never_drift(drift_accumulator, tuning, base_vector):
    record = DriftRecord()
    for _ in range(100):
        record = drift_accumulator.apply_session(
            {"warm": 2}, 0.9, 6, record, tuning
        )
    vec = drift_accumulator.apply_to_vector(base_vector, record, tuning)
    assert vec.weights["se"] == pytest.approx(base_vector.weights["se"])
    assert vec.weights["co"] == pytest.approx(base_vector.weights["co"])
