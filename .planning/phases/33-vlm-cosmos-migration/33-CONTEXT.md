# Phase 33: VLM Migration to Cosmos - Context

**Gathered:** 2026-06-08
**Status:** STUB — decisions deferred (обсудить перед планированием)

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
