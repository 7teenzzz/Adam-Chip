"""adam-logviewer: read-only HTTP service for logs.

Runs independently from adam-orchestrator — accessible even when orchestrator is down.
Port: ADAM_LOG_VIEWER_PORT (default 8083).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from collections import deque
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# ── Path resolution ───────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parents[2]

_data_dir_env = os.environ.get("ADAM_DATA_DIR", "")
if _data_dir_env:
    DATA_DIR = Path(_data_dir_env)
else:
    _cfg_path = Path(os.environ.get("ADAM_CONFIG", str(PROJECT_ROOT / "System" / "Config.json")))
    try:
        _cfg = json.loads(_cfg_path.read_text())
        _raw = _cfg.get("agent", {}).get("data_dir", "data/adam")
        DATA_DIR = Path(_raw) if Path(_raw).is_absolute() else PROJECT_ROOT / _raw
    except Exception:
        DATA_DIR = PROJECT_ROOT / "data" / "adam"

EVENTS_FILE = DATA_DIR / "events.jsonl"
METRICS_FILE = DATA_DIR / "inference_metrics.jsonl"
PORT = int(os.environ.get("ADAM_LOG_VIEWER_PORT", "8083"))
_START_TIME = time.monotonic()

_ADAM_UNITS = [
    "adam-orchestrator.service",
    "adam-llm.service",
    "adam-tts-silero.service",
    "adam-asr-whisperx.service",
    "adam-logviewer.service",
]

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Adam Log Viewer", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def tail_jsonl(
    path: Path,
    n: int,
    *,
    type_filter: str | None = None,
    since: str | None = None,
) -> list[dict]:
    if not path.exists():
        return []
    buf: deque[dict] = deque(maxlen=n)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if type_filter and obj.get("type") != type_filter:
                    continue
                if since and obj.get("ts", "") < since:
                    continue
                buf.append(obj)
    except OSError:
        return []
    return list(buf)


def _run(args: list[str]) -> tuple[str, str]:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=5)
        return r.stdout, r.stderr
    except Exception as exc:
        return "", str(exc)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "events_file_exists": EVENTS_FILE.exists(),
        "metrics_file_exists": METRICS_FILE.exists(),
        "uptime_sec": round(time.monotonic() - _START_TIME, 1),
    }


@app.get("/events")
def events(
    tail: int = Query(200, ge=1, le=2000),
    type: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
):
    return tail_jsonl(EVENTS_FILE, tail, type_filter=type, since=since)


@app.get("/metrics")
def metrics(tail: int = Query(50, ge=1, le=500)):
    return tail_jsonl(METRICS_FILE, tail)


@app.get("/journal")
def journal(
    unit: str = Query("adam-orchestrator.service"),
    lines: int = Query(100, ge=1, le=1000),
):
    if not unit.startswith("adam-"):
        return JSONResponse({"error": "unit must start with 'adam-'"}, status_code=400)
    stdout, stderr = _run(
        ["journalctl", "-u", unit, "-n", str(lines), "--no-pager", "--output=short-iso"]
    )
    return {"unit": unit, "lines": stdout.splitlines(), "error": stderr or None}


@app.get("/services")
def services():
    result = {}
    for unit in _ADAM_UNITS:
        stdout, _ = _run([
            "systemctl", "show", unit, "--no-pager",
            "-p", "ActiveState,SubState,ActiveEnterTimestamp",
        ])
        props: dict[str, str] = {}
        for line in stdout.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                props[k] = v
        result[unit] = {
            "active_state": props.get("ActiveState", "unknown"),
            "sub_state": props.get("SubState", "unknown"),
            "since": props.get("ActiveEnterTimestamp", ""),
        }
    return result


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _DASHBOARD_HTML


_DASHBOARD_HTML = """\
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="5">
<title>Adam Log Viewer</title>
<style>
  body{font-family:ui-monospace,monospace;font-size:12px;background:#0d1117;color:#c9d1d9;margin:0;padding:16px}
  h2{color:#58a6ff;margin:16px 0 6px}
  table{border-collapse:collapse;width:100%;margin-bottom:16px}
  th,td{border:1px solid #30363d;padding:4px 8px;text-align:left;white-space:pre-wrap;word-break:break-all}
  th{background:#161b22;color:#8b949e}
  .active{color:#3fb950}.inactive{color:#f85149}.unknown{color:#8b949e}
  .etype{color:#d2a8ff}.ts{color:#8b949e}
  a{color:#58a6ff;text-decoration:none}
</style>
</head>
<body>
<h1 style="color:#58a6ff;margin-top:0">
  Adam Log Viewer
  <span style="font-size:12px;color:#8b949e">auto-refresh 5s</span>
</h1>
<p style="color:#8b949e">
  data_dir: <code id="dd">…</code> &nbsp;|&nbsp; uptime: <code id="up">…</code>
</p>

<h2>Сервисы</h2>
<div id="svc">загрузка…</div>

<h2>Последние события <a href="/events?tail=200">[все →]</a></h2>
<div id="ev">загрузка…</div>

<h2>Метрики (последние 20 turn'ов) <a href="/metrics?tail=50">[все →]</a></h2>
<div id="mt">загрузка…</div>

<script>
async function load() {
  const [h, s, e, m] = await Promise.all([
    fetch('/health').then(r => r.json()).catch(() => ({})),
    fetch('/services').then(r => r.json()).catch(() => ({})),
    fetch('/events?tail=50').then(r => r.json()).catch(() => []),
    fetch('/metrics?tail=20').then(r => r.json()).catch(() => []),
  ]);

  document.getElementById('dd').textContent = h.data_dir || '?';
  document.getElementById('up').textContent = (h.uptime_sec || 0) + 's';

  let st = '<table><tr><th>Юнит</th><th>Состояние</th><th>SubState</th><th>С</th></tr>';
  for (const [u, v] of Object.entries(s)) {
    const cls = v.active_state === 'active' ? 'active' : v.active_state === 'inactive' ? 'inactive' : 'unknown';
    st += `<tr><td>${u}</td><td class="${cls}">${v.active_state}</td><td>${v.sub_state}</td><td class="ts">${v.since}</td></tr>`;
  }
  document.getElementById('svc').innerHTML = st + '</table>';

  let et = '<table><tr><th>Время</th><th>Тип</th><th>Payload</th></tr>';
  for (const ev of [...e].reverse().slice(0, 50)) {
    et += `<tr><td class="ts">${(ev.ts || '').slice(11, 23)}</td><td class="etype">${ev.type || ''}</td><td>${JSON.stringify(ev.payload || {})}</td></tr>`;
  }
  document.getElementById('ev').innerHTML = et + '</table>';

  let mt = '<table><tr><th>Время</th><th>ASR</th><th>LLM</th><th>TTS</th><th>Итого</th></tr>';
  const fmt = v => v != null ? Math.round(v) + 'ms' : '—';
  for (const r of [...m].reverse().slice(0, 20)) {
    mt += `<tr><td class="ts">${(r.ts || '').slice(11, 19)}</td><td>${fmt(r.asr_ms)}</td><td>${fmt(r.llm_ms)}</td><td>${fmt(r.tts_ms)}</td><td>${fmt(r.total_ms)}</td></tr>`;
  }
  document.getElementById('mt').innerHTML = mt + '</table>';
}

load();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
