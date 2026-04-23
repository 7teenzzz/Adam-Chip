#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


HOST = os.environ.get("ADAM_HOST_UI_BIND", "0.0.0.0")
PORT = int(os.environ.get("ADAM_HOST_UI_PORT", "8080"))
ESP_BASE_URL = os.environ.get("ESP_BASE_URL", "http://192.168.0.171").rstrip("/")


def page_shell(title: str, body: str, script: str = "") -> bytes:
  return f"""<!doctype html><html><head><meta charset="utf-8"><title>{title}</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#060606;--card:#111;--line:#2a2a2a;--text:#f4f4f4;--muted:#a2a2a2;--ok:#1eba4f;--bad:#d43c3c}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.35 Segoe UI,Arial,sans-serif}}
.wrap{{max-width:1280px;margin:0 auto;padding:14px}} .card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-top:10px}}
.links{{display:flex;flex-wrap:wrap;gap:8px}} .links a{{color:var(--ok);text-decoration:none;border:1px solid #2d4d31;padding:6px 10px;border-radius:999px}}
.row{{display:flex;justify-content:space-between;gap:10px;padding:6px 0;border-bottom:1px solid #1f1f1f}} .row:last-child{{border-bottom:none}}
.muted{{color:var(--muted)}} iframe{{width:100%;aspect-ratio:4/3;border:1px solid var(--line);border-radius:10px;background:#000}}
body[data-profile="desktop_16_9"] .grid{{display:grid;grid-template-columns:2fr 1fr;gap:12px}}
body[data-profile="phone_portrait"] .grid, body[data-profile="other"] .grid{{display:grid;grid-template-columns:1fr;gap:12px}}
</style></head><body><div class="wrap">{body}</div><script>
function profile(){{const w=innerWidth,h=innerHeight,r=w/Math.max(h,1);if(w<=430&&h>=700)return 'phone_portrait';if(w>=1000&&r>1.55&&r<1.95)return 'desktop_16_9';return 'other';}}
function applyProfile(){{document.body.dataset.profile=profile();}} addEventListener('resize',applyProfile); addEventListener('orientationchange',applyProfile); applyProfile();
const ESP_BASE_URL = {json.dumps(ESP_BASE_URL)};
{script}
</script></body></html>""".encode("utf-8")


def dashboard_page() -> bytes:
  body = """
<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap"><div><h1 style="margin:0">AdamS Dashboard (Host UI)</h1><div class="muted">стримы + телеметрия</div></div>
<div class="links"><a href="/vision">/vision</a><a href="/hearing">/hearing</a><a href="/sensorics">/sensorics</a><a href="/motor_skills">/motor_skills</a><a href="/system">/system</a></div></div>
<div class="grid"><section class="card"><h3 style="margin:0 0 10px 0">Видео</h3><iframe src="/vision/live?embed=1"></iframe></section><section class="card"><h3 style="margin:0 0 10px 0">Сводка</h3><div id="out" class="muted">loading...</div></section></div>
"""
  script = """
async function j(path){const r=await fetch(path,{cache:'no-store'});if(!r.ok) throw new Error(await r.text()); return r.json();}
function row(k,v){return `<div class="row"><span>${k}</span><span>${v}</span></div>`;}
async function refresh(){try{const [sys,sns,vs,hs]=await Promise.all([j('/api/v1/system/status'),j('/api/v1/sensorics/status'),j('/api/v1/vision/status'),j('/api/v1/hearing/status')]);
out.innerHTML=row('IP',sys.ip||'0.0.0.0')+row('Wi‑Fi',String(sys.wifi_connected))+row('RSSI',String(sys.wifi_rssi_cached??sys.wifi_rssi??'n/a'))+row('Vision',`${vs.camera?.preset||'n/a'} | ${vs.dashboard?.fps||0} FPS`)+row('Hearing',hs.audio?.capture?.profile||'n/a')+row('Sensorics',`motion=${sns.motion} light=${sns.light_raw}`);}catch(e){out.textContent=String(e);}}
refresh(); setInterval(refresh,1000);
"""
  return page_shell("AdamS Dashboard", body, script)


def vision_live_page() -> bytes:
  body = """
<h1 style="margin:0">/vision/live</h1><div class="links"><a href="/vision">/vision</a><a href="/">/</a></div>
<div class="card"><img id="img" style="width:100%;aspect-ratio:4/3;object-fit:contain;border:1px solid #2a2a2a;border-radius:10px;background:#000" alt="stream"></div>
<div class="card"><div style="display:flex;gap:8px;flex-wrap:wrap"><select id="preset"></select><button id="apply">apply preset</button></div><div id="msg" class="muted" style="margin-top:8px"></div></div>
"""
  script = """
function load(){img.src=`${ESP_BASE_URL.replace(/\\/$/,'').replace('http://','http://')}:81/stream?ts=${Date.now()}`;}
img.onerror=()=>setTimeout(load,500); load();
async function j(path,o){const r=await fetch(path,o);if(!r.ok) throw new Error(await r.text());return r.json();}
async function fill(){const s=await j('/api/v1/vision/camera'); preset.innerHTML=''; (s.camera?.presets||[]).forEach(p=>{const o=document.createElement('option');o.value=p.name;o.textContent=p.name;preset.appendChild(o);}); if(s.camera?.preset) preset.value=s.camera.preset;}
apply.onclick=async()=>{try{await j('/api/v1/vision/preset/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset:preset.value})}); msg.textContent='applied'; load();}catch(e){msg.textContent=String(e);}};
fill().catch(e=>msg.textContent=String(e));
"""
  return page_shell("Vision Live", body, script)


class HostUIHandler(BaseHTTPRequestHandler):
  def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
    self.send_response(status)
    self.send_header("Content-Type", content_type)
    self.send_header("Cache-Control", "no-store")
    self.send_header("Access-Control-Allow-Origin", "*")
    self.end_headers()
    self.wfile.write(body)

  def _send_json(self, status: int, obj: dict) -> None:
    self._send(status, json.dumps(obj).encode("utf-8"), "application/json")

  def _proxy_api(self) -> None:
    target = urljoin(ESP_BASE_URL + "/", self.path.lstrip("/"))
    payload = None
    if self.command == "POST":
      length = int(self.headers.get("Content-Length", "0"))
      payload = self.rfile.read(length) if length > 0 else b""
    req = Request(target, data=payload, method=self.command)
    req.add_header("Content-Type", self.headers.get("Content-Type", "application/json"))
    try:
      with urlopen(req, timeout=5) as resp:
        body = resp.read()
        self._send(resp.status, body, resp.headers.get_content_type() or "application/json")
    except HTTPError as e:
      self._send(e.code, e.read(), "application/json")
    except URLError as e:
      self._send_json(502, {"error": "esp_unreachable", "details": str(e)})

  def do_GET(self) -> None:
    if self.path.startswith("/api/v1/"):
      self._proxy_api()
      return
    if self.path == "/":
      self._send(200, dashboard_page())
      return
    if self.path in ("/vision", "/hearing", "/sensorics", "/motor_skills", "/system", "/hearing/live", "/sensorics/live", "/system/status", "/system/ota"):
      # Host UI keeps these pages lightweight and points heavy debug to ESP pages.
      location = ESP_BASE_URL + self.path
      self.send_response(302)
      self.send_header("Location", location)
      self.end_headers()
      return
    if self.path.startswith("/vision/live"):
      self._send(200, vision_live_page())
      return
    self._send_json(404, {"error": "not_found", "path": self.path})

  def do_POST(self) -> None:
    if self.path.startswith("/api/v1/"):
      self._proxy_api()
      return
    self._send_json(404, {"error": "not_found", "path": self.path})

  def log_message(self, format: str, *args) -> None:
    print(f"[host-ui] {self.address_string()} - {format % args}")


def main() -> None:
  print(f"Host UI listening on http://{HOST}:{PORT}")
  print(f"Proxying /api/v1/* to {ESP_BASE_URL}")
  HTTPServer((HOST, PORT), HostUIHandler).serve_forever()


if __name__ == "__main__":
  main()

