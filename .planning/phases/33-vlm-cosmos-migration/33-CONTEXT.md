# Phase 33: VLM Migration to Cosmos - Context

**Gathered:** 2026-06-08
**Status:** STUB — decisions deferred (обсудить перед планированием)

**Update 2026-06-12:** Базовая инициализация Cosmos восстановлена вне рамок формального
планирования фазы (срочный bugfix-проход):

- `deploy/systemd/adam-vlm.service` переписан на `llama-server --model Cosmos-Reason2-2B-Q8_0.gguf
  --mmproj mmproj-Cosmos-Reason2-2B-F16.gguf` (тот же бинарь/паттерн, что и `adam-llm.service`),
  слушает `:8051`. Юнит **disabled** (как раньше) — ручной старт `sudo systemctl enable --now adam-vlm.service`.
- Порты сведены к единому значению `8051` везде: `Config.json`, `Config.schema.json`,
  `System/adam/config.py`, `System/adam/inference.py` (VLMClient default), `/etc/adam-chip/adam.env`,
  `scripts/adam_install_systemd.sh`, README Inference Stack. Раньше было 3 разных значения
  (Config.json=8051, schema doc=8084, старый systemd VILA=8050).
- Проверено живьём: `python3 scripts/test_cosmos_vlm.py --image data/adam/scene_snapshot.jpg` →
  корректный ответ в формате `Scene: ... Engagement: ...`. RAM-стоимость Cosmos Q8_0 + mmproj F16 ≈ 2.2 GB.
- **Не сделано (остаётся для планирования этой фазы):** старый VILA/Docker код-путь ещё жив и не убран —
  `scripts/adam_live_vlm.sh`, `scripts/adam_start.sh` (`--vlm`, `LIVE_VLM_CONTAINER`),
  `scripts/adam_stop.sh` (`adam-live-vlm`), `System/adam/api_runtime.py` (`_probe_live_vlm`,
  docker start/stop методы для `adam-live-vlm`) — всё это управляет Docker-контейнером VILA,
  который больше не запускается новым `adam-vlm.service`. Это "двойное управление", про которое
  написано в open questions ниже — закрыть явно при планировании Phase 33 (убрать или адаптировать
  под llama.cpp-юнит).

<domain>
## Phase Boundary

Заменить текущую VLM (VILA 1.5-3b через `nano_llm` Docker, :8050) на модель семейства NVIDIA **Cosmos** для анализа сцены инсталляции. Цель — лучшее качество/латентность восприятия сцены и/или меньший расход VRAM, чтобы снять нынешнее напряжение по памяти (VILA ест ~4-5.6 GB и душит llama.cpp на 16 GB Jetson — поэтому `scene_worker`/VLM сейчас off по умолчанию, Phase 30).

**Out of scope (предв.):** перестройка scene-director логики; смена камеры; промпт-инжиниринг сверх адаптации под Cosmos.

</domain>

<decisions>
## Implementation Decisions

**ОТЛОЖЕНО — обсудить перед /gsd-plan-phase 33.**

Open questions для обсуждения:
- Какая именно Cosmos-модель/вариант (Reason / Predict / Nano; размер; квантизация под Jetson Orin NX aarch64)?
- Runtime: Docker (jetson-containers) или нативно? CUDA-сборка под aarch64 (как ctranslate2 урок из ASR)?
- VRAM-бюджет: влезает ли Cosmos + llama.cpp(:8081) + Silero одновременно в 16 GB, или нужен on-demand/выгрузка? Решает судьбу `media.scene_worker_enabled` и `adam-vlm.service`.
- Управление сервисом: единый владелец (сейчас двойное — `adam-vlm.service` systemd-обёртка vs docker-контейнер; см. замечание #5 Phase 30). Здесь же закрыть это окончательно (mask/убрать дубль).
- API-контракт: сохранить ли текущий VLM-эндпоинт-формат (`services.vlm.base_url` :8050, prompt-структура Scene/Engagement) или адаптировать под Cosmos.

</decisions>

<canonical_refs>
- `System/Config.json` `services.vlm`, `media.scene_worker_enabled`, `media.scene_*`
- `deploy/systemd/adam-vlm.service`, `scripts/adam_live_vlm.sh` — текущий запуск VILA (двойное управление — закрыть)
- `System/adam/inference.py` — VLM-адаптер
- Phase 30 замечание #5 + `reference_jetson_mem_network` (memory) — VLM ест ~5.6 GB, OOM-ит llama; NOPASSWD adam-*.service
- README §Inference Stack — текущая VILA-строка
