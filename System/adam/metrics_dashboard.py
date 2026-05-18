"""Metrics dashboard: computes all 13 diploma research metrics automatically.

Reads inference_metrics.jsonl, metrics_sessions.jsonl, events.jsonl and
memory/episodes/*.jsonl. No external dependencies — stdlib only.

Metric blocks:
  M1-M4  — Role stability & normativity  (3.4.2)
  M5-M8  — Memory & temporal continuity  (3.4.3)
  M9-M13 — Interactivity & initiative    (3.4.4)

All "expert-required" metrics are approximated with heuristic proxies where
possible. Notes on each metric describe the automation level.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from .events import utc_now
from .metrics import _tail_lines


# ── JSONL helpers ─────────────────────────────────────────────────────────────

def _load_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = _tail_lines(path, limit)
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _load_episodes(episodes_dir: Path, limit: int = 300) -> list[dict[str, Any]]:
    """Load most-recent episodes from memory/episodes/*.jsonl."""
    if not episodes_dir.exists():
        return []
    episodes: list[dict[str, Any]] = []
    for path in sorted(episodes_dir.glob("*.jsonl"), reverse=True):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                episodes.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if len(episodes) >= limit:
            break
    return episodes[:limit]


# ── TF-IDF cosine similarity (no scipy) ──────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[а-яёa-z]{2,}", text.lower())


def _tfidf_vectors(docs: list[str]) -> list[dict[str, float]]:
    tokenized = [_tokenize(d) for d in docs]
    N = len(docs)
    df: Counter[str] = Counter()
    for tokens in tokenized:
        df.update(set(tokens))
    vectors: list[dict[str, float]] = []
    for tokens in tokenized:
        tf: Counter[str] = Counter(tokens)
        total = len(tokens) or 1
        vec: dict[str, float] = {}
        for term, count in tf.items():
            idf = math.log((N + 1) / (df[term] + 1)) + 1.0
            vec[term] = (count / total) * idf
        vectors.append(vec)
    return vectors


def _centroid(vecs: list[dict[str, float]]) -> dict[str, float]:
    if not vecs:
        return {}
    keys = set().union(*vecs)
    n = len(vecs)
    return {k: sum(v.get(k, 0.0) for v in vecs) / n for k in keys}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ── Engagement extractor ──────────────────────────────────────────────────────

_ENGAGEMENT_RE = re.compile(r"Engagement:\s*(\w+)", re.IGNORECASE)

def _engagement_level(scene_text: str) -> str:
    m = _ENGAGEMENT_RE.search(scene_text)
    return m.group(1).lower() if m else "unknown"


# ── Main class ────────────────────────────────────────────────────────────────

class MetricsDashboard:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.turns_path = data_dir / "inference_metrics.jsonl"
        self.sessions_path = data_dir / "metrics_sessions.jsonl"
        self.events_path = data_dir / "events.jsonl"
        self.episodes_dir = data_dir / "memory" / "episodes"
        self.summaries_dir = data_dir / "summaries"

    def compute(self, window_turns: int = 300, window_events: int = 3000) -> dict[str, Any]:
        turns = _load_jsonl(self.turns_path, window_turns)
        sessions = _load_jsonl(self.sessions_path, 100)
        events = _load_jsonl(self.events_path, window_events)
        episodes = _load_episodes(self.episodes_dir)

        return {
            "computed_at": utc_now(),
            "window_turns": len(turns),
            "window_sessions": len(sessions),
            "window_events": len(events),
            "total_episodes": len(episodes),
            "blocks": {
                "role_normativity": {
                    "label": "3.4.2 Удержание роли и нормативность",
                    "m1_persona_consistency": self._m1(turns),
                    "m2_echo_injection": self._m2(turns),
                    "m3_action_rejection": self._m3(turns),
                    "m4_style_drift": self._m4(turns),
                },
                "memory_temporal": {
                    "label": "3.4.3 Память и темпоральная связность",
                    "m5_retrieval_proxy": self._m5(turns),
                    "m6_salience_internal": self._m6(episodes),
                    "m7_consolidation": self._m7(),
                    "m8_cross_session_proxy": self._m8(turns),
                },
                "interactivity": {
                    "label": "3.4.4 Интеракционность и инициатива",
                    "m9_dialog_length": self._m9(sessions),
                    "m10_latency": self._m10(turns),
                    "m11_wake_word": self._m11(events),
                    "m12_half_duplex": self._m12(events),
                    "m13_engagement": self._m13(events),
                },
            },
        }

    # ── M1: Persona Consistency ────────────────────────────────────────────

    def _m1(self, turns: list[dict]) -> dict[str, Any]:
        hashes = [t["tuning_hash"] for t in turns if t.get("tuning_hash")]
        if not hashes:
            return {
                "status": "no_data",
                "value": None,
                "note": "поле tuning_hash не найдено — нужна обновлённая версия системы",
                "automation": "full",
            }
        changes = sum(1 for i in range(1, len(hashes)) if hashes[i] != hashes[i - 1])
        total = max(len(hashes) - 1, 1)
        rate = round(1.0 - changes / total, 4)
        return {
            "status": "ok",
            "value": rate,
            "value_pct": round(rate * 100, 1),
            "changes": changes,
            "total": len(hashes),
            "note": "доля turn'ов без смены конфига персонажа; 1.0 = полная стабильность",
            "automation": "full",
        }

    # ── M2: Echo Injection Rate ────────────────────────────────────────────

    def _m2(self, turns: list[dict]) -> dict[str, Any]:
        if not turns:
            return {"status": "no_data", "value": None, "automation": "full"}
        # Поддержка старого поля "echo" и нового "echo_injected"
        injected = [
            t for t in turns
            if t.get("echo_injected") or (t.get("echo") is not None and t.get("echo") != "null")
        ]
        pools: Counter[str] = Counter(
            t.get("echo_pool") or (t.get("echo") or {}).get("pool", "unknown")
            for t in injected
            if t.get("echo_pool") or t.get("echo")
        )
        rate = round(len(injected) / len(turns), 4)
        disabled_note = ""
        if rate == 0:
            disabled_note = "; echoes.enabled=false в Config.json — для теста включить временно"
        return {
            "status": "ok",
            "value": rate,
            "value_pct": round(rate * 100, 1),
            "injected_count": len(injected),
            "total": len(turns),
            "pools": dict(pools),
            "note": "доля turn'ов с инжекцией echo-реплики" + disabled_note,
            "automation": "full",
        }

    # ── M3: ActionLayer Rejection Rate ────────────────────────────────────

    def _m3(self, turns: list[dict]) -> dict[str, Any]:
        if not turns:
            return {"status": "no_data", "value": None, "automation": "full"}
        kinds: Counter[str] = Counter(
            t.get("action_kind") or t.get("action") or "unknown" for t in turns
        )
        reasons: Counter[str] = Counter(
            t.get("action_reason") or "unknown"
            for t in turns
            if (t.get("action_kind") or t.get("action")) == "no_action"
        )
        no_action = kinds.get("no_action", 0)
        total = len(turns)
        rate = round(no_action / total, 4)
        # Норма: 5-15%; >30% = рассогласование промпта и whitelist
        if rate > 0.30:
            status = "warn"
        elif rate == 0:
            status = "warn"  # нулевое значение тоже подозрительно
        else:
            status = "ok"
        return {
            "status": status,
            "value": rate,
            "value_pct": round(rate * 100, 1),
            "action_kinds": dict(kinds),
            "no_action_reasons": dict(reasons),
            "total": total,
            "thresholds": {"normal_min": 0.05, "normal_max": 0.15},
            "note": "норма 5–15%; >30% = рассогласование промпта и whitelist",
            "automation": "full",
        }

    # ── M4: Style Drift (TF-IDF cosine similarity) ────────────────────────

    def _m4(self, turns: list[dict]) -> dict[str, Any]:
        by_session: dict[str, list[str]] = {}
        for t in turns:
            sid = t.get("session_id", "unknown")
            reply = (t.get("reply") or "").strip()
            if reply:
                by_session.setdefault(sid, []).append(reply)

        results = []
        for sid, replies in by_session.items():
            if len(replies) < 20:
                continue
            vecs = _tfidf_vectors(replies[:10] + replies[-10:])
            sim = _cosine(_centroid(vecs[:10]), _centroid(vecs[10:]))
            results.append({
                "session_id": sid,
                "turns": len(replies),
                "cosine_similarity": round(sim, 4),
                "stable": sim >= 0.70,
            })

        if not results:
            long_sessions = {sid: len(r) for sid, r in by_session.items() if len(r) >= 5}
            return {
                "status": "insufficient_data",
                "value": None,
                "note": f"нужны сессии ≥20 реплик; найдено {len(long_sessions)} сессий ≥5 реплик в окне",
                "automation": "full",
            }
        avg_sim = round(statistics.mean(r["cosine_similarity"] for r in results), 4)
        return {
            "status": "ok",
            "value": avg_sim,
            "value_pct": round(avg_sim * 100, 1),
            "sessions_analyzed": len(results),
            "sessions": results,
            "threshold": 0.70,
            "note": ">0.70 = стилистическая стабильность; измерено на сессиях ≥20 реплик",
            "automation": "full",
        }

    # ── M5: Retrieval Relevance Proxy ─────────────────────────────────────

    def _m5(self, turns: list[dict]) -> dict[str, Any]:
        if not turns:
            return {"status": "no_data", "value": None, "automation": "proxy"}
        with_episodic = [t for t in turns if (t.get("memory_retrieved_count") or 0) > 0]
        with_semantic = [t for t in turns if t.get("semantic_used")]
        with_name = [t for t in turns if t.get("visitor_name")]
        total = len(turns)
        rate = round(len(with_episodic) / total, 4)
        has_new_field = any(t.get("memory_retrieved_count") is not None for t in turns)
        note = "прокси: доля turn'ов с активированным episodic retrieval"
        if not has_new_field:
            note += "; поле memory_retrieved_count не найдено — нужна обновлённая система"
        return {
            "status": "ok" if has_new_field else "degraded",
            "value": rate,
            "value_pct": round(rate * 100, 1),
            "episodic_turns": len(with_episodic),
            "semantic_turns": len(with_semantic),
            "named_turns": len(with_name),
            "total": total,
            "expected_min": 0.10,
            "note": note,
            "automation": "proxy",
        }

    # ── M6: Salience Internal Consistency ─────────────────────────────────

    def _m6(self, episodes: list[dict]) -> dict[str, Any]:
        if not episodes:
            return {
                "status": "no_data",
                "value": None,
                "note": "нет эпизодов в памяти; нужны реальные сессии",
                "automation": "heuristic",
            }

        def safe_avg(lst: list[float]) -> float | None:
            return round(statistics.mean(lst), 3) if lst else None

        saliences = [float(e.get("salience", 0)) for e in episodes]
        with_name = [float(e["salience"]) for e in episodes if e.get("visitor", {}).get("introduced_name")]
        without_name = [float(e["salience"]) for e in episodes if not e.get("visitor", {}).get("introduced_name")]
        long_ep = [float(e["salience"]) for e in episodes if (e.get("duration_s") or 0) > 120]
        short_ep = [float(e["salience"]) for e in episodes if (e.get("duration_s") or 0) <= 60]
        themed = [float(e["salience"]) for e in episodes if e.get("themes")]
        no_themes = [float(e["salience"]) for e in episodes if not e.get("themes")]

        name_boost = (safe_avg(with_name) or 0) > (safe_avg(without_name) or 0) if with_name and without_name else None
        duration_boost = (safe_avg(long_ep) or 0) > (safe_avg(short_ep) or 0) if long_ep and short_ep else None
        theme_boost = (safe_avg(themed) or 0) > (safe_avg(no_themes) or 0) if themed and no_themes else None

        checks = [x for x in [name_boost, duration_boost, theme_boost] if x is not None]
        passed = sum(1 for x in checks if x)
        consistency = round(passed / len(checks), 2) if checks else None

        return {
            "status": "ok",
            "value": consistency,
            "total_episodes": len(episodes),
            "avg_salience": safe_avg(saliences),
            "salience_with_name": safe_avg(with_name),
            "salience_without_name": safe_avg(without_name),
            "salience_long_session": safe_avg(long_ep),
            "salience_short_session": safe_avg(short_ep),
            "consistency_checks": {
                "name_boost": name_boost,
                "duration_boost": duration_boost,
                "theme_boost": theme_boost,
                "passed": f"{passed}/{len(checks)}",
            },
            "note": "автоматическая внутренняя согласованность формулы salience; ручная аннотация даёт Спирмена",
            "automation": "heuristic",
        }

    # ── M7: Consolidation Coverage ────────────────────────────────────────

    def _m7(self) -> dict[str, Any]:
        # diary.md — главный артефакт консолидации в текущей архитектуре
        diary = self.data_dir / "memory" / "diary.md"
        summaries_files: list[Path] = []
        if self.summaries_dir.exists():
            summaries_files = list(self.summaries_dir.glob("*.txt")) + list(self.summaries_dir.glob("*.md"))

        diary_size = diary.stat().st_size if diary.exists() else 0
        files_count = len(summaries_files)
        files_size = sum(f.stat().st_size for f in summaries_files)

        if diary_size == 0 and files_count == 0:
            return {
                "status": "no_data",
                "value": None,
                "note": "diary.md пуст и summaries/ не заполнена — консолидатор ещё не запускался",
                "automation": "partial",
            }
        return {
            "status": "ok",
            "diary_size_bytes": diary_size,
            "diary_exists": diary.exists(),
            "summaries_count": files_count,
            "summaries_total_bytes": files_size,
            "note": "объём diary.md и summaries/ — полнота и когерентность требуют ручной оценки 10 summary",
            "automation": "partial",
        }

    # ── M8: Cross-Session Continuity Proxy ───────────────────────────────

    def _m8(self, turns: list[dict]) -> dict[str, Any]:
        if not turns:
            return {"status": "no_data", "value": None, "automation": "proxy"}
        # Прокси-1: episodic retrieval был активирован
        with_episodic = [t for t in turns if (t.get("memory_retrieved_count") or 0) > 0]
        # Прокси-2: semantic memory использовалась
        with_semantic = [t for t in turns if t.get("semantic_used")]
        # Суммарный прокси: хоть что-то из памяти было использовано
        with_memory = [
            t for t in turns
            if (t.get("memory_retrieved_count") or 0) > 0 or t.get("semantic_used")
        ]
        total = len(turns)
        rate = round(len(with_memory) / total, 4)
        return {
            "status": "ok",
            "value": rate,
            "value_pct": round(rate * 100, 1),
            "episodic_turns": len(with_episodic),
            "semantic_turns": len(with_semantic),
            "combined_turns": len(with_memory),
            "total": total,
            "expected_range": [0.10, 0.25],
            "note": "прокси: доля turn'ов с активацией памяти; ручная разметка транскриптов даёт точность",
            "automation": "proxy",
        }

    # ── M9: Average Dialog Length ─────────────────────────────────────────

    def _m9(self, sessions: list[dict]) -> dict[str, Any]:
        counts = [s["turn_count"] for s in sessions if s.get("turn_count")]
        if not counts:
            return {
                "status": "no_data",
                "value": None,
                "note": "нет закрытых сессий в metrics_sessions.jsonl — нужна обновлённая система",
                "automation": "full",
            }
        avg = round(statistics.mean(counts), 1)
        med = statistics.median(counts)
        # Интерпретация: <2 = плохо, 2-5 = умеренно, >5 = активное взаимодействие
        if avg < 2:
            level = "low"
        elif avg < 5:
            level = "moderate"
        else:
            level = "active"
        return {
            "status": "ok",
            "value": avg,
            "avg": avg,
            "median": med,
            "min": min(counts),
            "max": max(counts),
            "sessions": len(counts),
            "engagement_level": level,
            "thresholds": {"low": 2, "active": 5},
            "note": "<2 = посетители не поддерживают диалог; >5 = активное взаимодействие",
            "automation": "full",
        }

    # ── M10: Response Latency ─────────────────────────────────────────────

    def _m10(self, turns: list[dict]) -> dict[str, Any]:
        def _stats(key: str) -> dict[str, Any] | None:
            vals = [float(t[key]) for t in turns if t.get(key) is not None]
            if not vals:
                return None
            sv = sorted(vals)
            p95 = sv[max(0, int(0.95 * (len(sv) - 1)))]
            return {
                "min": round(min(vals), 0),
                "avg": round(statistics.mean(vals), 0),
                "p95": round(p95, 0),
                "max": round(max(vals), 0),
                "n": len(vals),
            }

        asr = _stats("asr_ms")
        llm = _stats("llm_ms")
        tts = _stats("tts_ms")
        total = _stats("total_ms")
        return {
            "status": "ok" if turns else "no_data",
            "asr_ms": asr,
            "llm_ms": llm,
            "tts_ms": tts,
            "total_ms": total,
            "expected": {
                "llm_ms": "9000–12000",
                "asr_ms": "1000–2000",
                "tts_ms": "300–800",
                "total_ms": "11000–15000",
            },
            "note": "LLM ~9с из-за SWA cache reset (Gemma 4 E4B); filler-фраза компенсирует задержку",
            "automation": "full",
        }

    # ── M11: Wake Word Accuracy ───────────────────────────────────────────

    def _m11(self, events: list[dict]) -> dict[str, Any]:
        detections = [e for e in events if e.get("type") == "wake_word_detected"]
        scores = [e for e in events if e.get("type") == "oww_score"]
        score_vals = [float(e["payload"]["score"]) for e in scores if e.get("payload", {}).get("score") is not None]
        return {
            "status": "no_test_data",
            "value": None,
            "detections_in_window": len(detections),
            "oww_scores_in_window": len(score_vals),
            "avg_score": round(statistics.mean(score_vals), 3) if score_vals else None,
            "note": "TPR/FPR требуют контрольного теста (см. scripts/test_wake_word.py)",
            "automation": "semi",
        }

    # ── M12: Half-Duplex Violations ───────────────────────────────────────

    def _m12(self, events: list[dict]) -> dict[str, Any]:
        # Строим окна TTS по turn_id
        tts_start: dict[str, str] = {}
        tts_end: dict[str, str] = {}
        for ev in events:
            tid = ev.get("turn_id")
            if not tid:
                continue
            if ev.get("type") == "tts_started":
                tts_start[tid] = ev["ts"]
            elif ev.get("type") == "tts_finished":
                tts_end[tid] = ev["ts"]

        violations: list[dict[str, Any]] = []
        for ev in events:
            if ev.get("type") not in ("asr_result", "asr_final"):
                continue
            tid = ev.get("turn_id")
            if not tid:
                continue
            ts_start = tts_start.get(tid)
            ts_end_val = tts_end.get(tid)
            if ts_start and ts_end_val and ts_start <= ev["ts"] <= ts_end_val:
                violations.append({"turn_id": tid, "ts": ev["ts"]})

        return {
            "status": "ok",
            "value": len(violations),
            "violations": len(violations),
            "expected": 0,
            "details": violations[:5],
            "note": "ожидаемое значение 0 (half_duplex_mute=true — архитектурный инвариант)",
            "automation": "full",
        }

    # ── M13: Scene Engagement & Proactive Initiative ──────────────────────

    def _m13(self, events: list[dict]) -> dict[str, Any]:
        eng_events = [e for e in events if e.get("type") == "scene_engagement_changed"]
        scene_events = [e for e in events if e.get("type") == "scene_updated"]
        transitions: Counter[str] = Counter(
            f"{e.get('payload', {}).get('from', '?')}→{e.get('payload', {}).get('to', '?')}"
            for e in eng_events
        )
        # Разбивка сцен по engagement-уровню из текста
        engagement_counts: Counter[str] = Counter()
        for ev in scene_events:
            text = ev.get("payload", {}).get("text", "") or ""
            lvl = _engagement_level(text)
            if lvl != "unknown":
                engagement_counts[lvl] += 1

        has_instrumentation = len(eng_events) > 0
        return {
            "status": "ok" if has_instrumentation else "no_data",
            "engagement_changes": len(eng_events),
            "transitions": dict(transitions),
            "engagement_distribution": dict(engagement_counts),
            "proactive_mcu_reactions": 0,
            "note": "scene_engagement_changed требует инструментации SceneWorker; проактивные MCU = 0 (механизм в разработке)",
            "automation": "partial",
        }
