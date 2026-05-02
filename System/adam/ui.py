from __future__ import annotations

import json
from typing import Any


def _json_script_value(value: dict[str, Any]) -> str:
    return json.dumps(value).replace("</", "<\\/")


def agent_page() -> str:
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>Adam Chip</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{margin:0;background:#070707;color:#f4f4f4;font:14px/1.4 system-ui,Segoe UI,Arial,sans-serif}
.wrap{max-width:1320px;margin:0 auto;padding:16px}.top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:12px}
.panel{border:1px solid #2a2a2a;background:#111;padding:12px;border-radius:8px;min-height:128px}
.panel h3{margin:0 0 8px 0;font-size:15px}.kv{display:grid;grid-template-columns:120px 1fr;gap:6px 10px}.k{color:#aaa}.v{overflow-wrap:anywhere}
.ok{color:#55d17a}.bad{color:#ff6868}.muted{color:#aaa}pre{white-space:pre-wrap;margin:0;max-height:280px;overflow:auto}
button,input{font:inherit}button{padding:8px 10px;background:#1d7f43;color:white;border:0;border-radius:6px;cursor:pointer}
button.secondary{background:#333}.row{display:flex;gap:8px;flex-wrap:wrap}.turn{display:flex;gap:8px;margin-top:12px}
input{flex:1;min-width:220px;padding:9px;background:#050505;color:#fff;border:1px solid #333;border-radius:6px}
@media(max-width:980px){.grid{grid-template-columns:1fr}.kv{grid-template-columns:96px 1fr}.turn{flex-direction:column}}
</style></head><body><div class="wrap">
<div class="top"><div><h1 style="margin:0">Adam Chip</h1><div class="muted" id="mode">mode</div></div>
<div class="row"><a href="/dash" style="color:#55d17a">/dash</a><a href="/debug" style="color:#55d17a">/debug</a><button onclick="setMode('maintenance')" class="secondary">maintenance</button><button onclick="setMode('exhibition')">exhibition</button><button onclick="listenStart()">listen start</button><button onclick="listenStop()" class="secondary">listen stop</button><button onclick="stopAgent()" class="secondary">stop/idle</button><button onclick="testVoice()" class="secondary">test voice</button></div></div>
<div class="turn"><input id="text" placeholder="Тестовая реплика зрителя"><button onclick="turn()">test turn</button></div>
<div class="grid">
  <section class="panel"><h3>Power</h3><div class="kv" id="power"></div></section>
  <section class="panel"><h3>Media</h3><div class="kv" id="media"></div></section>
  <section class="panel"><h3>LLM</h3><div class="kv" id="llm"></div></section>
  <section class="panel"><h3>TTS</h3><div class="kv" id="tts"></div></section>
  <section class="panel"><h3>ASR</h3><div class="kv" id="asr"></div></section>
  <section class="panel"><h3>VLM</h3><div class="kv" id="vlm"></div></section>
  <section class="panel"><h3>Voice Loop</h3><div class="kv" id="voice"></div></section>
  <section class="panel"><h3>Scene</h3><div class="kv" id="scene"></div></section>
  <section class="panel"><h3>ESP / MCU</h3><div class="kv" id="mcu"></div></section>
  <section class="panel"><h3>Exhibition Gate</h3><div class="kv" id="gate"></div></section>
</div>
<div class="grid"><section class="panel" style="grid-column:1/-1"><h3>Events</h3><pre id="events">loading</pre></section></div>
</div><script>
async function j(url, opts){const r=await fetch(url, opts); const t=await r.text(); try{return JSON.parse(t)}catch{return t}}
function yes(v){return v?'<span class="ok">ok</span>':'<span class="bad">fail</span>'}
function kv(root, rows){document.getElementById(root).innerHTML=rows.map(([k,v])=>`<div class="k">${k}</div><div class="v">${v}</div>`).join('')}
async function refresh(){const s=await j('/api/agent/status'); mode.textContent=`${s.agent.mode}${s.agent.speaking?' | speaking':''}`;
kv('power',[['gate',yes(s.power.ok)],['mode',yes(s.power.mode_ok)],['clocks',yes(s.power.clocks_ok)],['errors',(s.power.errors||[]).join(', ')||'none']]);
kv('media',[['video',`${yes(s.media.video.ready)} ${s.media.video.device||''}`],['input',`${yes(s.media.audio.input_ready)} ${s.media.audio.input_device}`],['output',`${yes(s.media.audio.output_ready)} ${s.media.audio.output_device}`]]);
kv('llm',[['state',yes(s.services.llm.ok)],['detail',s.services.llm.detail||'']]);
kv('tts',[['state',yes(s.services.tts.ok)],['detail',s.services.tts.detail||'']]);
kv('asr',[['state',yes(s.services.asr.ok)],['detail',s.services.asr.detail||'']]);
kv('vlm',[['state',yes(s.services.vlm.ok)],['detail',s.services.vlm.detail||''],['blocking',(s.exhibition_gate.non_blocking||[]).includes('vlm')?'no':'yes']]);
kv('voice',[['running',yes(s.voice_loop.running)],['vad',s.voice_loop.vad_state||'idle'],['muted',String(!!s.voice_loop.muted_by_tts)],['last',s.voice_loop.last_transcript||'none'],['error',s.voice_loop.last_asr_error||'none']]);
kv('scene',[['state',s.scene_cache.stale?'<span class="bad">stale</span>':'<span class="ok">fresh</span>'],['source',s.scene_cache.source||'manual'],['updated',s.scene_cache.updated_at||'never'],['summary',s.scene_cache.summary||'none']]);
kv('mcu',[['state',yes(s.mcu.ok)],['ip',s.mcu.data?.ip||'n/a'],['boot',s.mcu.data?.boot_stage||'n/a']]);
kv('gate',[['state',yes(s.exhibition_gate.ok)],['failed',(s.exhibition_gate.failed||[]).join(', ')||'none']]);
events.textContent=JSON.stringify(await j('/api/agent/events?limit=30'), null, 2)}
async function setMode(m){await j('/api/agent/mode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:m})}); refresh()}
async function listenStart(){await j('/api/agent/listen/start',{method:'POST'}); refresh()}
async function listenStop(){await j('/api/agent/listen/stop',{method:'POST'}); refresh()}
async function stopAgent(){await j('/api/agent/stop',{method:'POST'}); refresh()}
async function testVoice(){await j('/api/agent/say',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:'Проверка голоса Adam Chip.'})}); refresh()}
async function turn(){const transcript=document.getElementById('text').value; await j('/api/agent/turn',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({transcript})}); document.getElementById('text').value=''; refresh()}
refresh(); setInterval(refresh,3000)
</script></body></html>"""


def dash_page(settings_public: dict[str, Any]) -> str:
    config = _json_script_value(settings_public)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Adam Dash</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#0a0a0b;--panel:#151515;--panel2:#101010;--line:#303030;--text:#f2f2f2;--muted:#a8a8a8;--ok:#43d17a;--bad:#ff6363;--warn:#f0b84a;--cyan:#64c8ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.35 system-ui,Segoe UI,Arial,sans-serif}}
a{{color:var(--cyan);text-decoration:none}}button,input,select{{font:inherit}}button{{min-height:34px;border:1px solid #3b3b3b;border-radius:7px;background:#222;color:var(--text);cursor:pointer;padding:7px 10px}}button.primary{{background:#145a35;border-color:#247a4a}}button.danger{{background:#5a1d1d;border-color:#813030}}
input,select{{width:100%;min-height:34px;background:#0b0b0b;color:var(--text);border:1px solid #333;border-radius:7px;padding:7px 9px}}label{{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}}
.app{{min-height:100vh;display:grid;grid-template-rows:auto 1fr}}.top{{position:sticky;top:0;z-index:4;background:#111;border-bottom:1px solid var(--line);padding:10px 14px}}
.topline{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}.brand{{font-weight:700;font-size:16px}}.nav{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
.flags{{display:grid;grid-template-columns:repeat(6,minmax(78px,1fr));gap:8px;margin-top:10px}}.flag{{border:1px solid var(--line);background:#181818;border-radius:7px;padding:8px;min-width:0}}.flag b{{display:block;font-size:12px;text-transform:uppercase}}.dot{{display:inline-block;width:9px;height:9px;border-radius:99px;background:var(--bad);margin-right:6px}}.flag.ok .dot{{background:var(--ok)}}.flag .small{{font-size:12px;color:var(--muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.layout{{display:grid;grid-template-columns:290px minmax(0,1fr) 320px;gap:12px;padding:12px}}.panel{{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:12px;min-width:0}}.panel+ .panel{{margin-top:12px}}h1,h2,h3{{margin:0}}h2{{font-size:15px;margin-bottom:10px}}h3{{font-size:13px;color:var(--muted);margin-bottom:8px}}
.fields{{display:grid;gap:9px}}.twocol{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.actions{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}.kv{{display:grid;grid-template-columns:minmax(94px,auto) 1fr;gap:7px 10px;align-items:center}}.k{{color:var(--muted)}}.v{{overflow-wrap:anywhere}}.oktext{{color:var(--ok)}}.badtext{{color:var(--bad)}}.muted{{color:var(--muted)}}.mono{{font-family:Consolas,Menlo,monospace}}
.stream-grid{{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(240px,.9fr);gap:12px}}.streambox{{background:#050505;border:1px solid var(--line);border-radius:8px;overflow:hidden;min-height:220px}}.streambox img{{width:100%;aspect-ratio:4/3;display:block;object-fit:contain;background:#000}}audio{{width:100%;margin-top:8px}}
.pca-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}}.line{{border:1px solid #343434;border-radius:7px;background:#111;padding:8px;min-width:0}}.line-head{{display:flex;justify-content:space-between;gap:8px;font-size:12px}}.bar{{height:6px;background:#2b2b2b;border-radius:99px;overflow:hidden;margin-top:7px}}.bar span{{display:block;height:100%;background:var(--cyan);width:0%}}.err{{border-color:#693030;background:#241313;color:#ffc6c6}}
@media(max-width:1100px){{.layout{{grid-template-columns:1fr}}.stream-grid{{grid-template-columns:1fr}}.flags{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}@media(max-width:560px){{.flags{{grid-template-columns:repeat(2,minmax(0,1fr))}}.pca-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.twocol{{grid-template-columns:1fr}}}}
</style></head><body><div class="app">
<header class="top"><div class="topline"><div><div class="brand">Adam Dash</div><div id="sensorLine" class="muted">loading...</div></div><nav class="nav"><a href="/debug">/debug</a><a href="/agent">/agent</a><a id="espLink" target="_blank">ESP</a></nav></div><div id="flags" class="flags"></div></header>
<main class="layout">
<aside>
  <section class="panel"><h2>Camera Settings</h2><div class="fields"><div><label>Preset</label><select id="camPreset"></select></div><div class="twocol"><div><label>Framesize</label><select id="camFramesize"></select></div><div><label>Quality</label><input id="camQuality" type="number" min="4" max="63"></div></div></div><div class="actions"><button class="primary" id="applyCamPreset">Apply preset</button><button id="applyCam">Apply camera</button><button id="reloadCam">Reload stream</button></div><div id="camMsg" class="muted" style="margin-top:8px"></div></section>
  <section class="panel"><h2>Mic Settings</h2><div class="fields"><div><label>Profile</label><select id="micProfile"></select></div><div class="twocol"><div><label>Gain</label><input id="micGain" type="number" min="0.25" max="32" step="0.25"></div><div><label>DC Block</label><select id="micDc"><option value="true">on</option><option value="false">off</option></select></div></div><div class="twocol"><div><label>Slot</label><select id="micSlot"><option value="1">left</option><option value="2">right</option></select></div><div><label>Shift</label><input id="micShift" type="number" min="0" max="24"></div></div></div><div class="actions"><button class="primary" id="applyMic">Apply mic</button></div><div id="micMsg" class="muted" style="margin-top:8px"></div></section>
</aside>
<section>
  <section class="panel"><h2>Streams</h2><div class="stream-grid"><div><h3>Camera</h3><div class="streambox"><img id="camStream" alt="camera stream"></div><div id="camMeta" class="muted" style="margin-top:8px"></div></div><div><h3>Mic</h3><div class="panel" style="margin:0;background:var(--panel2)"><div id="micMeta" class="kv"></div><audio id="micStream" controls></audio><div class="actions"><a id="micOpen" target="_blank">open stream</a></div></div></div></div></section>
  <section class="panel"><h2>PCA</h2><div id="pcaSummary" class="kv"></div><div id="pcaLines" class="pca-grid" style="margin-top:10px"></div></section>
</section>
<aside>
  <section class="panel"><h2>ESP System</h2><div id="systemStatus" class="kv"></div><div class="actions"><a id="otaLink" target="_blank">OTA</a><button id="resetLatency">Reset video latency</button></div><div id="systemMsg" class="muted" style="margin-top:8px"></div></section>
  <section class="panel"><h2>Errors</h2><div id="errorStatus" class="kv"></div></section>
</aside>
</main></div>
<script>
const UI_CONFIG={config};
let state=null; let controlsReady=false;
const q=(id)=>document.getElementById(id);
async function api(path,opts){{const r=await fetch(path,opts);const text=await r.text();let data={{}};try{{data=JSON.parse(text)}}catch{{data={{raw:text}}}}if(!r.ok)throw new Error(data.detail||data.error||text||r.status);return data;}}
function esc(v){{return String(v??'n/a').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function okClass(v){{return v?'oktext':'badtext';}}function yn(v){{return `<span class="${{okClass(v)}}">${{v?'ok':'fail'}}</span>`;}}
function kv(id,rows){{q(id).innerHTML=rows.map(([k,v])=>`<div class="k">${{esc(k)}}</div><div class="v">${{v}}</div>`).join('');}}
function fmtBytes(v){{v=Number(v||0);if(v>1048576)return `${{(v/1048576).toFixed(1)}} MB`;if(v>1024)return `${{Math.round(v/1024)}} KB`;return `${{v}} B`;}}
function fmtMs(v){{v=Number(v||0);return v>999?`${{(v/1000).toFixed(1)}} s`:`${{v}} ms`;}}
function cameraObj(){{const c=state?.camera||{{}};return c.camera||c;}}function audioObj(){{return state?.audio||{{}};}}function pcaObj(){{const p=state?.pca||{{}};return p.pca9685||p;}}
function fillControls(){{const c=cameraObj();const preset=q('camPreset');preset.innerHTML='';(c.presets||[]).forEach(p=>{{const o=document.createElement('option');o.value=p.name;o.textContent=p.builtin?`${{p.name}} [builtin]`:p.name;preset.appendChild(o);}});if(c.preset)preset.value=c.preset;const fs=q('camFramesize');fs.innerHTML='';((c.capabilities||{{}}).framesize_options||[]).forEach(x=>{{const o=document.createElement('option');o.value=x.value;o.textContent=`${{x.name}} (${{x.value}})`;fs.appendChild(o);}});if(!fs.options.length)fs.appendChild(new Option(String(c.framesize??0),String(c.framesize??0)));if(c.framesize!==undefined)fs.value=String(c.framesize);if(c.quality!==undefined)q('camQuality').value=c.quality;
const a=audioObj().capture||{{}};const profile=q('micProfile');profile.innerHTML='';(a.profiles||[]).forEach(name=>profile.appendChild(new Option(name,name)));if(a.profile)profile.value=a.profile;q('micGain').value=Number(a.software_gain??1).toFixed(2);q('micDc').value=String(!!a.dc_block);q('micSlot').value=String(a.preferred_slot||1);q('micShift').value=a.sample_shift??0;controlsReady=true;}}
function render(){{if(!state)return;const mods=state.modules||{{}};q('flags').innerHTML=['mic','cam','pcm5102','pca9685','temt600','pir'].map(name=>`<div class="flag ${{mods[name]?'ok':''}}"><b><span class="dot"></span>${{name}}</b><div class="small">${{mods[name]?'ready':'offline'}}</div></div>`).join('');
const sensors=state.sensors||{{}};q('sensorLine').textContent=`light ${{sensors.light_raw??'n/a'}} / ${{sensors.light_norm??'n/a'}} | motion ${{sensors.motion?'yes':'no'}} | changed ${{fmtMs(sensors.motion_changed_ms_ago)}} ago`;
q('espLink').href=state.esp?.base_url||'#';q('otaLink').href=(state.esp?.base_url||'')+'/ota';const c=cameraObj();const a=audioObj();const cap=a.capture||{{}};const play=a.playback||{{}};const d=state.dashboard||{{}};const s=state.status||{{}};const p=pcaObj();
q('camMeta').textContent=`${{c.preset||d.camera_preset||'preset n/a'}} | ${{d.fps||c.capture_fps||0}} FPS | clients ${{d.video_clients??s.video_clients??0}}`;
kv('micMeta', [['capture',yn(!!cap.ready)],['profile',esc(cap.profile)],['signal',esc(cap.signal_state)],['peak / avg',`${{esc(cap.selected_peak)}} / ${{esc(cap.average_level)}}`],['clients',esc(a.clients??s.audio_clients)]]);
kv('pcaSummary', [['ready',yn(!!p.ready)],['scene',esc(p.active_scene)],['active',esc(p.active_channels)],['frequency',esc(p.frequency)],['address',esc(p.address)]]);
q('pcaLines').innerHTML=(p.channels||Array(16).fill(0)).map((v,i)=>{{const pct=Math.max(0,Math.min(100,Number(v||0)/4095*100));return `<div class="line"><div class="line-head"><b>CH ${{i}}</b><span class="mono">${{v}}</span></div><div class="bar"><span style="width:${{pct}}%"></span></div></div>`;}}).join('');
kv('systemStatus', [['Wi-Fi',yn(!!(d.wifi_connected??s.wifi_connected))],['IP',esc(d.ip||s.ip)],['RSSI',esc(d.wifi_rssi_cached??s.wifi_rssi_cached??s.wifi_rssi)],['Boot',esc(d.boot_stage||s.boot_stage)],['Heap',fmtBytes(s.heap_free)],['PSRAM',fmtBytes(s.psram_free)],['Camera',yn(!!(d.camera_ready??s.camera_ready))],['PCM5102',yn(!!(d.speaker_ready??s.speaker_ready??play.ready))]]);
kv('errorStatus', [['Init',esc(d.last_init_error||s.last_init_error||'none')],['Stream',esc(d.last_stream_error||s.last_stream_error||'none')],['Sound',esc(d.last_sound_result||s.last_sound_result||'idle')],['Upload bytes',esc(d.last_sound_bytes||s.last_sound_bytes||0)]]);
if(!controlsReady)fillControls();}}
async function refresh(){{try{{state=await api('/api/ui/status');render();}}catch(e){{q('systemMsg').textContent=String(e);}}}}
function reloadCamera(){{q('camStream').src=(state?.esp?.camera_stream_url||UI_CONFIG._ui.camera_stream_url)+'?ts='+Date.now();}}
q('micStream').src=UI_CONFIG._ui.mic_stream_url;q('micOpen').href=UI_CONFIG._ui.mic_stream_url;reloadCamera();
q('reloadCam').onclick=reloadCamera;q('applyCamPreset').onclick=async()=>{{try{{await api('/api/ui/camera/preset',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{preset:q('camPreset').value}})}});controlsReady=false;await refresh();reloadCamera();q('camMsg').textContent='applied';}}catch(e){{q('camMsg').textContent=String(e);}}}};
q('applyCam').onclick=async()=>{{try{{await api('/api/ui/camera',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{framesize:Number(q('camFramesize').value),quality:Number(q('camQuality').value)}})}});controlsReady=false;await refresh();reloadCamera();q('camMsg').textContent='applied';}}catch(e){{q('camMsg').textContent=String(e);}}}};
q('applyMic').onclick=async()=>{{try{{await api('/api/ui/audio',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{profile:q('micProfile').value,software_gain:Number(q('micGain').value),dc_block:q('micDc').value==='true',slot:Number(q('micSlot').value),shift:Number(q('micShift').value)}})}});controlsReady=false;await refresh();q('micMsg').textContent='applied';}}catch(e){{q('micMsg').textContent=String(e);}}}};
q('resetLatency').onclick=async()=>{{try{{await api('/api/ui/video-latency/reset',{{method:'POST'}});q('systemMsg').textContent='latency reset';}}catch(e){{q('systemMsg').textContent=String(e);}}}};
refresh();setInterval(refresh,1200);
</script></body></html>"""


def debug_page(settings_public: dict[str, Any]) -> str:
    config = _json_script_value(settings_public)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Adam Debug</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#090909;--panel:#151515;--line:#303030;--text:#f2f2f2;--muted:#a8a8a8;--ok:#43d17a;--bad:#ff6363;--warn:#f0b84a;--blue:#64c8ff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.35 system-ui,Segoe UI,Arial,sans-serif}}a{{color:var(--blue);text-decoration:none}}button,input,select{{font:inherit}}button{{border:1px solid #3b3b3b;border-radius:7px;background:#222;color:var(--text);cursor:pointer;padding:7px 10px;min-height:34px}}button.primary{{background:#145a35;border-color:#247a4a}}button.danger{{background:#5a1d1d;border-color:#813030}}button.warn{{background:#4b3617;border-color:#7c5720}}input,select{{width:100%;background:#0b0b0b;color:var(--text);border:1px solid #333;border-radius:7px;padding:7px 9px}}label{{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}}.top{{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;padding:12px 14px;background:#111;border-bottom:1px solid var(--line)}}.layout{{display:grid;grid-template-columns:minmax(0,1.2fr) 360px;gap:12px;padding:12px}}.panel{{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:12px;min-width:0}}h1,h2,h3{{margin:0}}h1{{font-size:18px}}h2{{font-size:15px;margin-bottom:10px}}.actions{{display:flex;gap:8px;flex-wrap:wrap}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.ch{{border:1px solid #343434;border-radius:8px;background:#111;padding:10px;min-width:0}}.ch-head{{display:flex;justify-content:space-between;gap:8px;margin-bottom:8px}}.ch input[type=range]{{padding:0}}.row{{display:grid;grid-template-columns:1fr 74px;gap:8px;align-items:center}}.small-actions{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:8px}}.kv{{display:grid;grid-template-columns:120px 1fr;gap:7px 10px}}.k{{color:var(--muted)}}.muted{{color:var(--muted)}}.mono{{font-family:Consolas,Menlo,monospace}}audio{{width:100%;margin-top:8px}}.msg{{margin-top:10px;color:var(--muted);overflow-wrap:anywhere}}@media(max-width:1040px){{.layout{{grid-template-columns:1fr}}.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:560px){{.grid{{grid-template-columns:1fr}}.small-actions{{grid-template-columns:1fr}}}}
</style></head><body>
<header class="top"><div><h1>Adam Debug</h1><div id="summary" class="muted">loading...</div></div><nav class="actions"><a href="/dash">/dash</a><a href="/agent">/agent</a><button id="refreshBtn">Refresh</button></nav></header>
<main class="layout"><section class="panel"><h2>PCA Lines</h2><div class="actions" style="margin-bottom:10px"><button data-scene="all_off" class="danger">all off</button><button data-scene="all_on" class="primary">all on</button><button data-scene="even_on_odd_off" class="warn">even on / odd off</button><button data-scene="invert">invert</button></div><div id="channels" class="grid"></div><div id="pcaMsg" class="msg"></div></section>
<aside><section class="panel"><h2>PCM5102</h2><div class="actions"><button data-sound="tone" class="primary">tone test</button><button data-sound="boot">boot sound</button><button data-sound="success">success sound</button></div><div style="margin-top:12px"><label>PC sound file</label><input id="fileInput" type="file" accept="audio/*,.wav,.mp3,.ogg,.flac"></div><div class="actions" style="margin-top:10px"><button id="uploadSound" class="primary">play selected file</button></div><audio id="preview" controls></audio><div id="pcmMsg" class="msg"></div></section><section class="panel" style="margin-top:12px"><h2>Raw PCA</h2><div id="rawPca" class="kv"></div></section></aside></main>
<script>
const UI_CONFIG={config};let state=null;
const q=(id)=>document.getElementById(id);
async function api(path,opts){{const r=await fetch(path,opts);const text=await r.text();let data={{}};try{{data=JSON.parse(text)}}catch{{data={{raw:text}}}}if(!r.ok)throw new Error(data.detail||data.error||text||r.status);return data;}}
function esc(v){{return String(v??'n/a').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));}}
function pcaObj(){{const p=state?.pca||{{}};return p.pca9685||p;}}
function kv(id,rows){{q(id).innerHTML=rows.map(([k,v])=>`<div class="k">${{esc(k)}}</div><div>${{v}}</div>`).join('');}}
async function refresh(){{state=await api('/api/ui/status');render();}}
function render(){{const p=pcaObj();q('summary').textContent=`ready ${{p.ready?'yes':'no'}} | scene ${{p.active_scene||'n/a'}} | active ${{p.active_channels??0}} | freq ${{p.frequency??'n/a'}}`;kv('rawPca',[['ready',esc(p.ready)],['scene',esc(p.active_scene)],['active',esc(p.active_channels)],['frequency',esc(p.frequency)],['speaker',esc(UI_CONFIG._ui.speaker_url)]]);const vals=p.channels||Array(16).fill(0);q('channels').innerHTML=vals.map((v,i)=>`<div class="ch"><div class="ch-head"><b>CH ${{i}}</b><span class="mono" id="valLabel${{i}}">${{v}}</span></div><div class="row"><input id="range${{i}}" type="range" min="0" max="4095" value="${{v}}" oninput="syncVal(${{i}},this.value)"><input id="num${{i}}" type="number" min="0" max="4095" value="${{v}}" oninput="syncVal(${{i}},this.value)"></div><div class="small-actions"><button onclick="setChannel(${{i}},0)">off</button><button onclick="setChannel(${{i}},4095)">on</button><button class="primary" onclick="applyChannel(${{i}})">apply</button></div></div>`).join('');}}
function syncVal(i,v){{v=Math.max(0,Math.min(4095,Number(v||0)));q('range'+i).value=v;q('num'+i).value=v;q('valLabel'+i).textContent=v;}}
async function setChannel(i,v){{syncVal(i,v);await applyChannel(i);}}
async function applyChannel(i){{try{{await api('/api/ui/pca/channel',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{channel:i,mode:'pwm',value:Number(q('num'+i).value)}})}});await refresh();q('pcaMsg').textContent=`CH ${{i}} applied`;}}catch(e){{q('pcaMsg').textContent=String(e);}}}}
document.querySelectorAll('[data-scene]').forEach(btn=>btn.onclick=async()=>{{try{{await api('/api/ui/pca/debug-scene',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{scene:btn.dataset.scene}})}});await refresh();q('pcaMsg').textContent=`${{btn.dataset.scene}} applied`;}}catch(e){{q('pcaMsg').textContent=String(e);}}}});
document.querySelectorAll('[data-sound]').forEach(btn=>btn.onclick=async()=>{{try{{const r=await api('/api/ui/pcm/system-sound',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:btn.dataset.sound}})}});q('pcmMsg').textContent=JSON.stringify(r);}}catch(e){{q('pcmMsg').textContent=String(e);}}}});
q('fileInput').onchange=()=>{{const f=q('fileInput').files[0];q('preview').src=f?URL.createObjectURL(f):'';}};
q('uploadSound').onclick=async()=>{{const f=q('fileInput').files[0];if(!f){{q('pcmMsg').textContent='select file';return;}}try{{q('pcmMsg').textContent='decoding...';const wav=await fileToWav(f);q('pcmMsg').textContent='uploading...';const r=await fetch('/api/ui/pcm/upload',{{method:'POST',headers:{{'Content-Type':'audio/wav','X-File-Name':encodeURIComponent(f.name)}},body:wav}});const text=await r.text();q('pcmMsg').textContent=text;if(!r.ok)throw new Error(text);}}catch(e){{q('pcmMsg').textContent=String(e);}}}};
async function fileToWav(file){{const ab=await file.arrayBuffer();try{{const ctx=new (window.AudioContext||window.webkitAudioContext)();const audio=await ctx.decodeAudioData(ab.slice(0));const wav=encodeWavMono16(audio,44100);await ctx.close();return wav;}}catch(e){{if(file.type.includes('wav')||file.name.toLowerCase().endsWith('.wav'))return ab;throw e;}}}}
function encodeWavMono16(buffer,targetRate){{const srcRate=buffer.sampleRate;const frames=Math.max(1,Math.floor(buffer.duration*targetRate));const out=new Int16Array(frames);for(let i=0;i<frames;i++){{const src=i*srcRate/targetRate;const i0=Math.floor(src);const i1=Math.min(i0+1,buffer.length-1);const frac=src-i0;let sample=0;for(let ch=0;ch<buffer.numberOfChannels;ch++){{const data=buffer.getChannelData(ch);sample+=data[i0]*(1-frac)+data[i1]*frac;}}sample/=buffer.numberOfChannels;sample=Math.max(-1,Math.min(1,sample));out[i]=sample<0?sample*32768:sample*32767;}}const bytes=44+out.byteLength;const dv=new DataView(new ArrayBuffer(bytes));writeStr(dv,0,'RIFF');dv.setUint32(4,bytes-8,true);writeStr(dv,8,'WAVE');writeStr(dv,12,'fmt ');dv.setUint32(16,16,true);dv.setUint16(20,1,true);dv.setUint16(22,1,true);dv.setUint32(24,targetRate,true);dv.setUint32(28,targetRate*2,true);dv.setUint16(32,2,true);dv.setUint16(34,16,true);writeStr(dv,36,'data');dv.setUint32(40,out.byteLength,true);for(let i=0;i<out.length;i++)dv.setInt16(44+i*2,out[i],true);return dv.buffer;}}
function writeStr(dv,off,s){{for(let i=0;i<s.length;i++)dv.setUint8(off+i,s.charCodeAt(i));}}
q('refreshBtn').onclick=()=>refresh().catch(e=>q('pcaMsg').textContent=String(e));refresh().catch(e=>q('pcaMsg').textContent=String(e));
</script></body></html>"""
