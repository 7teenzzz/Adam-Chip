"""adam-logviewer: read-only HTTP service for logs.

Runs independently from adam-orchestrator — accessible even when orchestrator is down.
Port: ADAM_LOG_VIEWER_PORT (default 8083).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import urllib.request
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

EVENTS_FILE  = DATA_DIR / "events.jsonl"
METRICS_FILE = DATA_DIR / "inference_metrics.jsonl"
PORT         = int(os.environ.get("ADAM_LOG_VIEWER_PORT", "8083"))
_ORCH_PORT   = int(os.environ.get("ADAM_ORCHESTRATOR_PORT", "8080"))
_START_TIME  = time.monotonic()

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


def _try_orch(path: str) -> dict | None:
    """Try fetching from orchestrator; return parsed JSON or None on any error."""
    try:
        url = f"http://127.0.0.1:{_ORCH_PORT}{path}"
        with urllib.request.urlopen(url, timeout=1) as r:  # noqa: S310
            return json.loads(r.read())
    except Exception:
        return None


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
async def events(
    tail: int = Query(200, ge=1, le=2000),
    type: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
):
    path = f"/api/events?limit={tail}" + (f"&type={type}" if type else "")
    data = await asyncio.to_thread(_try_orch, path)
    if data is not None:
        return data.get("events", [])
    return tail_jsonl(EVENTS_FILE, tail, type_filter=type, since=since)


@app.get("/metrics")
async def metrics(tail: int = Query(50, ge=1, le=500)):
    data = await asyncio.to_thread(_try_orch, f"/api/metrics/turns?limit={tail}")
    if data is not None:
        return {"source": "orchestrator", "turns": data.get("turns", [])}
    return {"source": "file", "turns": tail_jsonl(METRICS_FILE, tail)}


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
<title>Adam · Logs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
  :root{
    --bg-0:#070708;--bg-1:#0d0d10;--bg-2:#15151a;--bg-3:#1d1d24;
    --line:#262630;--line-strong:#3a3a48;
    --text:#f2f2f5;--muted:#8a8a96;--dim:#5a5a66;
    --accent:#43d17a;--accent-glow:#6effa8;
    --cyan:#64c8ff;--warn:#f0b84a;--bad:#ff6363;
    --radius-s:6px;--radius-m:10px;
    --shadow-card:0 1px 0 rgba(255,255,255,.03) inset,0 12px 30px -20px rgba(0,0,0,.7);
    --font-sans:"Inter",system-ui,sans-serif;
    --font-mono:"JetBrains Mono","SF Mono",Consolas,monospace;
  }
  *,*::before,*::after{box-sizing:border-box}
  html,body{margin:0;padding:0;background:var(--bg-0);color:var(--text);
    font-family:var(--font-sans);font-size:13px;line-height:1.45;
    -webkit-font-smoothing:antialiased;min-height:100vh}
  a{color:var(--accent);text-decoration:none}
  a:hover{color:var(--accent-glow)}
  ::-webkit-scrollbar{width:8px}
  ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:var(--bg-3);border-radius:4px;border:2px solid var(--bg-0)}

  /* topbar */
  .topbar{height:52px;background:var(--bg-1);border-bottom:1px solid var(--line);
    display:flex;align-items:center;gap:12px;padding:0 20px;position:sticky;top:0;z-index:10}
  .topbar-title{font-size:13px;font-weight:500;color:var(--text);letter-spacing:.02em}
  .topbar-sub{font-size:11px;color:var(--muted);font-family:var(--font-mono)}
  .spacer{flex:1}
  .pulse{width:7px;height:7px;border-radius:50%;background:var(--accent);
    box-shadow:0 0 8px var(--accent);animation:blink 2s infinite}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}

  /* layout */
  .page{padding:20px;max-width:1400px;margin:0 auto;display:flex;flex-direction:column;gap:16px}

  /* card */
  .card{background:var(--bg-1);border:1px solid var(--line);border-radius:var(--radius-m);
    box-shadow:var(--shadow-card);overflow:hidden;position:relative}
  .card::before{content:"";position:absolute;inset:0;
    background:linear-gradient(180deg,rgba(255,255,255,.025),transparent 60%);pointer-events:none}
  .card-header{padding:10px 16px;border-bottom:1px solid var(--line);
    display:flex;align-items:center;gap:8px}
  .card-title{font-size:11px;text-transform:uppercase;letter-spacing:.1em;
    color:var(--muted);font-weight:500}
  .card-body{padding:0}

  /* badge */
  .badge{display:inline-flex;align-items:center;gap:5px;padding:2px 8px;
    border-radius:999px;border:1px solid var(--line-strong);background:var(--bg-2);
    font-size:11px;font-family:var(--font-mono);color:var(--muted)}
  .badge.ok{border-color:var(--accent);color:var(--accent)}
  .badge.bad{border-color:var(--bad);color:var(--bad)}
  .badge.warn{border-color:var(--warn);color:var(--warn)}
  .dot{width:6px;height:6px;border-radius:50%;background:currentColor;display:inline-block}

  /* table */
  table{width:100%;border-collapse:collapse;font-size:12px}
  th{padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;
    letter-spacing:.07em;color:var(--muted);font-weight:500;border-bottom:1px solid var(--line);
    background:var(--bg-2);white-space:nowrap}
  td{padding:7px 12px;border-bottom:1px solid var(--line);vertical-align:top}
  tr:last-child td{border-bottom:none}
  tr:hover td{background:rgba(255,255,255,.018)}
  .col-ts{font-family:var(--font-mono);color:var(--dim);white-space:nowrap;width:90px}
  .col-type{font-family:var(--font-mono);color:var(--cyan);white-space:nowrap}
  .col-ms{font-family:var(--font-mono);text-align:right;width:70px}
  .col-payload{font-family:var(--font-mono);font-size:11px;color:var(--muted);
    word-break:break-all;max-width:600px}

  /* kv row */
  .kv-row{display:flex;gap:24px;padding:12px 16px;flex-wrap:wrap}
  .kv-item{display:flex;flex-direction:column;gap:2px}
  .kv-label{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
  .kv-value{font-family:var(--font-mono);font-size:12px;color:var(--text)}
</style>
</head>
<body>

<div class="topbar">
  <div class="pulse"></div>
  <span class="topbar-title">Adam Chip</span>
  <span class="topbar-sub">log viewer · :8083</span>
  <span class="spacer"></span>
  <span class="topbar-sub" id="uptime">—</span>
  <a id="dash-btn" href="#" target="_blank" rel="noopener"
     style="font-size:11px;font-family:var(--font-mono);color:var(--muted);opacity:0.35;pointer-events:none;text-decoration:none;border:1px solid var(--line);padding:3px 10px;border-radius:var(--radius-s)"
     title="Оркестратор недоступен">Dashboard ↗</a>
</div>

<div class="page">

  <!-- health -->
  <div class="card">
    <div class="card-header"><span class="card-title">Система</span></div>
    <div class="kv-row" id="health-kv">
      <div class="kv-item"><span class="kv-label">data_dir</span><span class="kv-value" id="h-datadir">…</span></div>
      <div class="kv-item"><span class="kv-label">events</span><span class="kv-value" id="h-events">…</span></div>
      <div class="kv-item"><span class="kv-label">metrics</span><span class="kv-value" id="h-metrics">…</span></div>
    </div>
  </div>

  <!-- services -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">Сервисы</span>
    </div>
    <div class="card-body"><table>
      <thead><tr><th>Юнит</th><th>Статус</th><th>Sub</th><th>Запущен</th></tr></thead>
      <tbody id="svc-body"></tbody>
    </table></div>
  </div>

  <!-- events -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">События</span>
      <span class="spacer"></span>
      <a href="/events?tail=500" style="font-size:11px">все →</a>
    </div>
    <div class="card-body"><table>
      <thead><tr><th>Время</th><th>Тип</th><th>Payload</th></tr></thead>
      <tbody id="ev-body"></tbody>
    </table></div>
  </div>

  <!-- metrics -->
  <div class="card">
    <div class="card-header">
      <span class="card-title">Метрики pipeline</span>
      <span id="mt-src" style="font-size:10px;font-family:var(--font-mono);color:var(--dim)"></span>
      <span class="spacer"></span>
      <a href="/metrics?tail=100" style="font-size:11px">все →</a>
    </div>
    <div class="card-body"><table>
      <thead><tr><th>Время</th><th>ASR</th><th>LLM</th><th>TTS</th><th>Итого</th></tr></thead>
      <tbody id="mt-body"></tbody>
    </table></div>
  </div>

</div>

<script>
const fmtMs = v => v != null ? Math.round(v) + 'ms' : '—';
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function msColor(v) {
  if (v == null) return '';
  if (v > 5000) return 'color:var(--bad)';
  if (v > 2000) return 'color:var(--warn)';
  return 'color:var(--accent)';
}

async function load() {
  const [h, s, e, m] = await Promise.all([
    fetch('/health').then(r => r.json()).catch(() => ({})),
    fetch('/services').then(r => r.json()).catch(() => ({})),
    fetch('/events?tail=60').then(r => r.json()).catch(() => []),
    fetch('/metrics?tail=20').then(r => r.json()).catch(() => ({ source: 'file', turns: [] })),
  ]);

  // health
  document.getElementById('uptime').textContent = 'uptime ' + (h.uptime_sec || 0) + 's';
  document.getElementById('h-datadir').textContent = h.data_dir || '?';
  document.getElementById('h-events').textContent = h.events_file_exists ? '✓' : '✗';
  document.getElementById('h-metrics').textContent = h.metrics_file_exists ? '✓' : '✗';

  // services
  let sb = '';
  for (const [u, v] of Object.entries(s)) {
    const ok = v.active_state === 'active';
    const bad = v.active_state === 'inactive' || v.active_state === 'failed';
    const cls = ok ? 'ok' : bad ? 'bad' : 'warn';
    const since = v.since ? v.since.replace('MSK','').trim() : '—';
    sb += `<tr>
      <td style="font-family:var(--font-mono);font-size:11px">${esc(u)}</td>
      <td><span class="badge ${cls}"><span class="dot"></span>${esc(v.active_state)}</span></td>
      <td style="font-family:var(--font-mono);font-size:11px;color:var(--muted)">${esc(v.sub_state)}</td>
      <td class="col-ts" style="font-size:11px">${esc(since)}</td>
    </tr>`;
  }
  document.getElementById('svc-body').innerHTML = sb;

  // events
  let eb = '';
  for (const ev of [...e].reverse().slice(0, 60)) {
    eb += `<tr>
      <td class="col-ts">${esc((ev.ts || '').slice(11, 23))}</td>
      <td class="col-type">${esc(ev.type || '')}</td>
      <td class="col-payload">${esc(JSON.stringify(ev.payload || {}))}</td>
    </tr>`;
  }
  document.getElementById('ev-body').innerHTML = eb || '<tr><td colspan="3" style="color:var(--dim);text-align:center;padding:20px">нет данных</td></tr>';

  // metrics — m may be {source, turns} (orchestrator) or {source, turns} (file)
  const mRows = m && m.turns ? m.turns : [];
  const mSrc  = m && m.source ? m.source : '?';
  let mb = '';
  for (const r of [...mRows].reverse().slice(0, 20)) {
    mb += `<tr>
      <td class="col-ts">${esc((r.ts || '').slice(11, 19))}</td>
      <td class="col-ms" style="${msColor(r.asr_ms)}">${fmtMs(r.asr_ms)}</td>
      <td class="col-ms" style="${msColor(r.llm_ms)}">${fmtMs(r.llm_ms)}</td>
      <td class="col-ms" style="${msColor(r.tts_ms)}">${fmtMs(r.tts_ms)}</td>
      <td class="col-ms" style="${msColor(r.total_ms)}">${fmtMs(r.total_ms)}</td>
    </tr>`;
  }
  document.getElementById('mt-src').textContent  = mSrc;
  document.getElementById('mt-body').innerHTML = mb || '<tr><td colspan="5" style="color:var(--dim);text-align:center;padding:20px">нет данных</td></tr>';
}

load();
setInterval(load, 5000);

// Dashboard cross-link: activate when orchestrator is reachable
(function checkOrch() {
  const btn  = document.getElementById('dash-btn');
  const base = 'http://' + location.hostname + ':8080';
  function probe() {
    fetch(base + '/api/agent/status', { signal: AbortSignal.timeout(1000) })
      .then(r => {
        if (r.ok) {
          btn.href              = base;
          btn.style.opacity     = '1';
          btn.style.pointerEvents = '';
          btn.style.color       = 'var(--accent)';
          btn.title             = 'Открыть Dashboard';
        }
      })
      .catch(() => {
        btn.style.opacity       = '0.35';
        btn.style.pointerEvents = 'none';
        btn.style.color         = 'var(--muted)';
        btn.title               = 'Оркестратор недоступен';
      });
  }
  probe();
  setInterval(probe, 15000);
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
