#!/usr/bin/env python3
"""Wake-word calibration by ambient noise.

Records OWW score events from the running orchestrator's SSE stream for N
seconds while the operator keeps the room quiet, then computes a recommended
threshold = noise_p99 + margin (with sane floor/ceiling).

Two modes:

1. Recommended — go through the REST endpoint so the orchestrator owns the
   subscription and the archive:

       scripts/adam_calibrate_wakeword.py --duration 20 --apply

2. Standalone (no endpoint) — subscribe to /api/agent/stream SSE directly.
   Useful for SSH debugging or if the calibrate endpoint is unavailable:

       scripts/adam_calibrate_wakeword.py --duration 20 --apply --sse-only

Both modes ultimately call PATCH /api/wake_word/sensitivity to apply the
recommended threshold (only when --apply is set).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _base_url() -> str:
    # PROJECT_ROOT/scripts/this — orchestrator is on localhost by default.
    return os.environ.get("ADAM_API_URL", "http://127.0.0.1:8080").rstrip("/")


def _no_proxy_opener():
    """Build an opener that bypasses any local proxy (v2ray etc.).

    The project CLAUDE.md notes that v2ray intercepts localhost — this
    matches the `curl --noproxy '*'` recipe used throughout the codebase.
    """
    handler = urllib.request.ProxyHandler({})
    return urllib.request.build_opener(handler)


_OPENER = _no_proxy_opener()


def _http_json(method: str, path: str, body: dict | None = None) -> dict:
    url = _base_url() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with _OPENER.open(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise SystemExit(f"HTTP {e.code} on {method} {path}: {detail}")
    except urllib.error.URLError as e:
        raise SystemExit(f"orchestrator unreachable at {url}: {e}")


def _print_profile(result: dict) -> None:
    p = result.get("profile", {})
    print()
    print(f"Profile ({result.get('duration_sec', '?')}s, {result.get('samples', 0)} samples):")
    print(f"  max  = {p.get('max', 0):.3f}")
    print(f"  p99  = {p.get('p99', 0):.3f}")
    print(f"  p95  = {p.get('p95', 0):.3f}")
    print(f"  mean = {p.get('mean', 0):.3f}")
    print()
    print(f"Recommended threshold: {result.get('recommended_threshold', 0):.2f}")
    if result.get("warning"):
        print(f"⚠  {result['warning']}")
    print()


def calibrate_via_endpoint(duration: float, margin: float) -> dict:
    print(f"→ Калибровка через /api/wake_word/calibrate/noise ({duration}s)...")
    print("  Не говорите, оставьте обычный фон комнаты.")
    return _http_json("POST", "/api/wake_word/calibrate/noise",
                      {"duration_sec": duration, "margin": margin})


def calibrate_via_sse(duration: float, margin: float) -> dict:
    """Standalone fallback — subscribes to SSE directly without going through endpoint."""
    from adam.wake_calibration import compute_recommendation

    url = _base_url() + "/api/agent/stream"
    print(f"→ Калибровка через SSE {url} ({duration}s)...")
    print("  Не говорите, оставьте обычный фон комнаты.")

    scores: list[float] = []
    deadline = time.monotonic() + duration
    req = urllib.request.Request(url)
    with _OPENER.open(req, timeout=10) as resp:
        # SSE: data: {json}\n\n  blocks separated by blank line.
        for raw in resp:
            if time.monotonic() >= deadline:
                break
            line = raw.decode("utf-8", errors="ignore").rstrip("\r\n")
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except Exception:
                continue
            if ev.get("type") != "oww_score":
                continue
            score = (ev.get("payload") or {}).get("score")
            if isinstance(score, (int, float)):
                scores.append(float(score))

    result = compute_recommendation(scores, margin)
    result["duration_sec"] = duration
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--duration", type=float, default=20.0,
                    help="Длительность записи шума (с), по умолчанию 20")
    ap.add_argument("--margin", type=float, default=0.08,
                    help="Отступ над p99, по умолчанию 0.08")
    ap.add_argument("--apply", action="store_true",
                    help="Применить рекомендованный порог без интерактивного подтверждения")
    ap.add_argument("--sse-only", action="store_true",
                    help="Не использовать /api/wake_word/calibrate/noise, идти напрямую через SSE")
    ap.add_argument("--quiet", action="store_true",
                    help="JSON-вывод, без человекочитаемой подсказки")
    args = ap.parse_args()

    # Pre-flight — show current sensitivity, fail fast if engine offline.
    try:
        sens = _http_json("GET", "/api/wake_word/sensitivity")
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    if not sens.get("ok"):
        print(f"Wake-word engine inactive: {sens}", file=sys.stderr)
        return 3
    if not args.quiet:
        print(f"Текущая чувствительность: threshold={sens['threshold']} debounce={sens['debounce_hits']}")

    # 3-second countdown so the operator has time to stop talking.
    if not args.quiet:
        for n in range(3, 0, -1):
            print(f"  начинаем через {n}…", end="\r", flush=True)
            time.sleep(1)
        print(" " * 32, end="\r")

    if args.sse_only:
        # Ensure System/ is on PYTHONPATH for the helper import.
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "System"))
        result = calibrate_via_sse(args.duration, args.margin)
    else:
        result = calibrate_via_endpoint(args.duration, args.margin)

    if args.quiet:
        print(json.dumps(result, ensure_ascii=False))
    else:
        _print_profile(result)

    recommended = float(result.get("recommended_threshold", 0))
    if not args.apply:
        if args.quiet:
            return 0
        answer = input("Применить? [y/N] ").strip().lower()
        if answer != "y":
            print("Отменено.")
            return 0

    patch = _http_json(
        "PATCH",
        "/api/wake_word/sensitivity",
        {"threshold": recommended, "persist": True},
    )
    if not args.quiet:
        print(f"✓ Порог применён: threshold={patch.get('threshold')} persisted={patch.get('persisted')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
