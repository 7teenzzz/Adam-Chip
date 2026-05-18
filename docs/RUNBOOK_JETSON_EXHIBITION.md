# Adam Chip Jetson Exhibition Runbook

## Power Gate

The exhibition runtime is designed for MAXN/Super. Apply it before starting
services:

```bash
./scripts/adam_power_maxn.sh
```

`ADAM_MODE=exhibition` will refuse startup when the power gate is not satisfied.

## Local Runtime

```bash
python3 -m pip install -r System/requirements.txt
python3 System/Orchestrator.py
```

Open:

```text
http://JETSON_IP:8080
```

## Docker Runtime

```bash
cp .env.example .env
docker compose up --build adam-orchestrator
```

Optional local Silero HTTP service:

```bash
docker compose --profile speech-local up --build adam-tts-silero
```

## Production Systemd Runtime

Install units:

```bash
./scripts/adam_install_systemd.sh
```

Start the exhibition target:

```bash
sudo systemctl start adam-exhibition.target
```

Inspect status:

```bash
./scripts/adam_service_status.sh
```

Compact exhibition gate:

```bash
curl -fsS http://127.0.0.1:8080/api/agent/gate | python3 -m json.tool
```

Follow logs:

```bash
./scripts/adam_service_logs.sh adam-orchestrator.service
./scripts/adam_service_logs.sh adam-tts-silero.service
```

Change runtime mode through the orchestrator API:

```bash
./scripts/adam_set_mode.sh maintenance
./scripts/adam_set_mode.sh exhibition
```

The generated systemd environment file is:

```text
/etc/adam-chip/adam.env
```

For current runtime defaults, see `System/Config.json`.

## Media Policy

- Preferred video input: CSI or USB/UVC camera connected directly to Jetson.
- Preferred ASR input: USB microphone or microphone array connected directly to Jetson.
- ESP32 media endpoints are diagnostic/fallback only.
- WebRTC is an operator preview path, not the inference path.
- Remote camera is acceptable only as hardware H.264 RTSP from an IP camera or encoder.

## TTS Dependencies

The orchestrator dependencies are intentionally small. Install them into the
project venv:

```bash
./scripts/adam_bootstrap_venv.sh
```

The Silero service needs Silero and a Jetson-compatible PyTorch build. Install
the NVIDIA/Jetson-compatible PyTorch wheel first, then install `silero` without
letting pip replace or auto-install `torch`:

NVIDIA's Jetson PyTorch guide states that the wheels are NVIDIA-provided
redistributables for JetPack with GPU acceleration and should be installed for
the matching JetPack release:

```text
https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html
```

Do not install a generic PyPI `torch` wheel as part of this project setup.

```bash
./.venv/bin/python -m pip install --no-deps "silero>=0.5.0"
```

If Silero reports another missing dependency after that, install that dependency
explicitly; do not allow dependency resolution to replace NVIDIA's PyTorch.

Doctor and smoke tests:

```bash
./scripts/adam_torch_doctor.sh
./scripts/adam_tts_doctor.sh
./scripts/adam_tts_smoke.sh
curl -fsS http://127.0.0.1:8090/health | python3 -m json.tool
```

## Gate-To-Green Sequence

```bash
./scripts/adam_bootstrap_venv.sh
./scripts/adam_torch_doctor.sh
sudo ./scripts/adam_install_systemd.sh
sudo systemctl start adam-tts-silero.service
sudo systemctl start adam-orchestrator.service
./scripts/adam_service_status.sh
./scripts/adam_set_mode.sh exhibition
```

If `adam_set_mode.sh exhibition` fails, inspect the compact gate first:

```bash
curl -fsS http://127.0.0.1:8080/api/agent/gate | python3 -m json.tool
```

## Smoke Checks

```bash
./scripts/adam_media_probe.sh
PYTHONPATH=System ./.venv/bin/python System/Orchestrator.py
curl -fsS http://127.0.0.1:8080/api/agent/status | python3 -m json.tool
curl -fsS http://127.0.0.1:8080/api/agent/gate | python3 -m json.tool
curl -fsS http://127.0.0.1:8080/api/agent/turn \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"Привет, Адам. Ты меня слышишь?"}' | python3 -m json.tool
```

## Reply hang diagnosis

**Симптом:** оркестратор перестал реагировать; UI VU-meter замёрз; events.jsonl
не пополняется. Пользователь говорит «Адам, …» — реакции нет.

**Базовая проверка (Phase 8+):** запустить heartbeat-аудит:

```bash
python3 scripts/adam_test_reply_hang.py --last-minutes 5
```

Возможные результаты:

- `OK: N heartbeats, max gap K.K sec (норма ≤ 6 sec)` — loop работает, hang НЕ воспроизведён.
- `WARN: max gap 7-29 sec ...` — был кратковременный stall; проверить нагрузку CPU/IO в этот момент.
- `ERROR: gap ≥30 sec ... voice_loop appears frozen` — подтверждённый hang.

**Действия при ERROR:**

1. Зафиксировать последний `voice_state_change` event перед gap — скрипт его печатает. Это покажет, в каком состоянии loop умер (обычно reply→standby).
2. Собрать последние 50 events из events.jsonl:

   ```bash
   tail -n 50 data/adam/events.jsonl > /tmp/hang-tail.jsonl
   ```

3. Если оркестратор всё ещё запущен и не отвечает — остановить через systemctl и сохранить journalctl:

   ```bash
   sudo systemctl stop adam-orchestrator.service
   sudo journalctl -u adam-orchestrator.service --since "10 min ago" > /tmp/hang-journal.log
   ```

4. **Завести follow-up фазу** под `SIGUSR1 → asyncio task stack dump mechanism` (Phase 8 CONTEXT §Deferred предусматривает эту работу). Прикрепить `/tmp/hang-tail.jsonl` и `/tmp/hang-journal.log` в `BRANCH.md` новой фазы — это будет первый воспроизводимый набор данных для root-cause анализа.

**Что Phase 8 уже устранил:**

- Избыточность reply mode (один таймер вместо двух) — повышает шанс что hang не воспроизведётся вообще.
- Heartbeat event — даёт точное место разрыва, если hang всё-таки повторится.

**Что ещё может вызывать hang (не покрыто Phase 8):**

- Lock contention в `event_log.append` (синхронный write под threading.Lock).
- Deadlock между `_vad_loop` consumer и `MicReader` producer (asyncio-уровневый).
- Зависание HTTP-вызова к ESP32 при mute / TTS post-playback restore.

Эти подозреваемые рассматриваются в follow-up фазе под SIGUSR1 dump.

Live-наблюдение во время работы (опционально):

```bash
python3 scripts/adam_test_reply_hang.py --follow
```

Печатает каждый новый heartbeat с пометкой OK/WARN/ERROR в реальном времени.
