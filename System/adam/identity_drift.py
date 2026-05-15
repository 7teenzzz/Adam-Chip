"""Cross-session identity drift for Adam Chip's AIIM system.

Tracks slow evolution of aspect weights across sessions:
- classify_session() maps an emotion distribution to an experience type
- compute_delta() calculates drift deltas (base_delta × salience)
- DriftRecord is persisted atomically to data/adam/identity/drift.json
- drift_log.jsonl records per-session entries (append-only, for debugging)

Design invariants:
- se and co are LOCKED — never appear in drift deltas
- Drift accumulates additively; ceilings prevent unbounded growth
- Atomic write-then-rename prevents corruption on unclean shutdown
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .identity import IdentityVector

if TYPE_CHECKING:
    from .tuning import IdentityTuning

log = logging.getLogger(__name__)

SessionExperienceType = Literal[
    "void", "witnessed", "memory_surfacing", "confrontation", "deep_contact"
]

_IDENTITY_DIR = "identity"
_DRIFT_FILE = "drift.json"
_DRIFT_LOG_FILE = "drift_log.jsonl"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DriftRecord:
    """Persistent drift state written to drift.json at session close."""

    schema_version: int = 1
    # Accumulated deltas to add on top of base aspect weights each session start.
    aspect_drift: dict[str, float] = field(default_factory=dict)
    # How many sessions of each experience type have occurred.
    session_counts: dict[str, int] = field(default_factory=dict)
    total_sessions: int = 0
    created_at: str = ""
    last_updated: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DriftRecord":
        return cls(
            schema_version=data.get("schema_version", 1),
            aspect_drift=data.get("aspect_drift", {}),
            session_counts=data.get("session_counts", {}),
            total_sessions=data.get("total_sessions", 0),
            created_at=data.get("created_at", ""),
            last_updated=data.get("last_updated", ""),
        )


# ---------------------------------------------------------------------------
# DriftAccumulator
# ---------------------------------------------------------------------------


class DriftAccumulator:
    """Manages cross-session aspect weight drift.

    Usage per session:
        record = acc.load(data_dir)
        vector = acc.apply_to_vector(base_vector, record, tuning.identity)
        # ... session runs ...
        record = acc.apply_session(emotion_dist, salience, turns, record, tuning.identity)
        acc.save(record, data_dir)
    """

    def classify_session(
        self,
        emotion_dist: dict[str, int],
        salience: float,
        turns: int,
    ) -> SessionExperienceType:
        """Map an emotion distribution + salience to an experience type.

        Priority (highest first):
          deep_contact   — warm occurred AND salience >= 0.5
          confrontation  — sharp occurred
          memory_surfacing — unease occurred >= 2 times
          witnessed      — at least some turns happened
          void           — almost nothing happened
        """
        warm_count = emotion_dist.get("warm", 0)
        sharp_count = emotion_dist.get("sharp", 0)
        unease_count = emotion_dist.get("unease", 0)

        if warm_count > 0 and salience >= 0.5:
            return "deep_contact"
        if sharp_count > 0:
            return "confrontation"
        if unease_count >= 2:
            return "memory_surfacing"
        if turns >= 2 and salience >= 0.2:
            return "witnessed"
        return "void"

    def compute_delta(
        self,
        experience_type: SessionExperienceType,
        salience: float,
        tuning: "IdentityTuning",
    ) -> dict[str, float]:
        """Return per-aspect drift delta for this session.

        delta = base_delta × salience
        LOCKED aspects (se, co) are excluded.
        """
        drift_table = tuning.drift_table
        entries = getattr(drift_table, experience_type, [])
        result: dict[str, float] = {}
        for entry in entries:
            aspect = entry.aspect if hasattr(entry, "aspect") else entry.get("aspect", "")
            base_delta = (
                entry.base_delta if hasattr(entry, "base_delta")
                else entry.get("base_delta", 0.0)
            )
            if aspect in IdentityVector.LOCKED:
                continue
            if aspect and base_delta > 0:
                result[aspect] = round(base_delta * max(0.0, salience), 6)
        return result

    def apply_ceilings(
        self,
        new_drift: dict[str, float],
        existing_drift: dict[str, float],
        ceilings: dict[str, float],
        base_weights: dict[str, float],
    ) -> dict[str, float]:
        """Merge new_drift into existing_drift, clamping to (ceiling - base_weight).

        Returns the updated accumulated drift dict.
        """
        updated = dict(existing_drift)
        for aspect, delta in new_drift.items():
            if aspect in IdentityVector.LOCKED:
                continue
            ceiling = ceilings.get(aspect)
            base = base_weights.get(aspect, 0.0)
            current_accum = updated.get(aspect, 0.0)
            new_accum = current_accum + delta
            if ceiling is not None:
                max_accum = max(0.0, ceiling - base)
                new_accum = min(new_accum, max_accum)
            updated[aspect] = round(new_accum, 6)
        return updated

    def apply_to_vector(
        self,
        base: IdentityVector,
        record: DriftRecord,
        tuning: "IdentityTuning",
    ) -> IdentityVector:
        """Return a new IdentityVector with accumulated drift applied.

        This is called at session start to get the 'true current' weights.
        """
        ceilings = tuning.ceilings.as_dict()
        return base.with_drift(record.aspect_drift, ceilings)

    def load(self, data_dir: Path) -> DriftRecord:
        """Load drift.json. Returns a fresh DriftRecord if file missing or corrupt."""
        drift_path = data_dir / _IDENTITY_DIR / _DRIFT_FILE
        if not drift_path.exists():
            log.info("identity: no drift file found at %s, starting fresh", drift_path)
            return DriftRecord(created_at=_now_iso())
        try:
            with drift_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return DriftRecord.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            log.error("identity: failed to load drift file: %s", exc)
            return DriftRecord(created_at=_now_iso())

    def save(
        self,
        record: DriftRecord,
        data_dir: Path,
        log_entry: dict | None = None,
    ) -> None:
        """Atomically write drift.json and append to drift_log.jsonl.

        Uses write-then-rename so a crash mid-write doesn't corrupt the file.
        """
        identity_dir = data_dir / _IDENTITY_DIR
        identity_dir.mkdir(parents=True, exist_ok=True)

        drift_path = identity_dir / _DRIFT_FILE
        tmp_path = drift_path.with_suffix(".tmp")

        record.last_updated = _now_iso()
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, drift_path)
        except OSError as exc:
            log.error("identity: failed to save drift file: %s", exc)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return

        # Append to drift_log.jsonl
        if log_entry:
            log_path = identity_dir / _DRIFT_LOG_FILE
            try:
                with log_path.open("a", encoding="utf-8") as lf:
                    lf.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except OSError as exc:
                log.warning("identity: could not append to drift log: %s", exc)

    def apply_session(
        self,
        emotion_dist: dict[str, int],
        salience: float,
        turns: int,
        record: DriftRecord,
        tuning: "IdentityTuning",
    ) -> DriftRecord:
        """Classify session, compute delta, apply ceilings, update record.

        Returns a new DriftRecord (immutable-style; original not mutated).
        """
        experience = self.classify_session(emotion_dist, salience, turns)
        delta = self.compute_delta(experience, salience, tuning)

        ceilings = tuning.ceilings.as_dict()
        base_weights = tuning.base_weights

        updated_drift = self.apply_ceilings(
            delta, record.aspect_drift, ceilings, base_weights
        )

        new_counts = dict(record.session_counts)
        new_counts[experience] = new_counts.get(experience, 0) + 1

        ts = _now_iso()
        return DriftRecord(
            schema_version=record.schema_version,
            aspect_drift=updated_drift,
            session_counts=new_counts,
            total_sessions=record.total_sessions + 1,
            created_at=record.created_at or ts,
            last_updated=ts,
        )

    def build_log_entry(
        self,
        experience: SessionExperienceType,
        salience: float,
        turns: int,
        delta: dict[str, float],
    ) -> dict:
        """Build a single-line JSON entry for drift_log.jsonl."""
        return {
            "ts": _now_iso(),
            "type": experience,
            "salience": round(salience, 4),
            "turns": turns,
            "deltas": delta,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
