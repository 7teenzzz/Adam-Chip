# Phase 30: Voice Loop Recovery & Flora Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-07
**Phase:** 30-voice-loop-recovery-flora-integration
**Areas discussed:** ESP IP и сеть, Выход TTS, Flora-gate при мёрже, Ollama + рестарт сервисов

---

## ESP IP и сеть

| Option | Description | Selected |
|--------|-------------|----------|
| 192.168.0.171 | Канон из REQUIREMENTS, Jetson в 192.168.0.x; 10.10.10.171 — ошибка luxflora (рекомендация Claude) | |
| 10.10.10.171 | Выставочная сеть реально 10.10.10.x — оставить IP, чинить сеть Jetson | ✓ |
| Зависит от площадки | dev vs выставка разные IP по env/mode | |

**User's choice:** 10.10.10.171
**Notes:** Переопределяет рекомендацию Claude. Выставочная сеть — проводная 10.10.10.x (ESP по W5500 Ethernet). IP в Config ВЕРНЫЙ; чинить надо сеть Jetson (eno1 DOWN → поднять на 10.10.10.x). «192.168.0.171» — устаревший dev-IP.

---

## Выход TTS

| Option | Description | Selected |
|--------|-------------|----------|
| HDMI/монитор сейчас | Временно plughw:1,3 для быстрого живого теста (рекомендация Claude) | |
| Только ESP | Озвучка только через ESP-динамик; тест ждёт сети ESP | ✓ |
| HDMI авто-fallback | Авто-fallback на HDMI при ошибке ESP | |

**User's choice:** Только ESP
**Notes:** Переопределяет рекомендацию Claude. Никакого HDMI. Следствие: живой end-to-end тест голоса блокируется до восстановления сети 10.10.10.x → ESP. Вопрос виртуального дисплея для выхода снят.

---

## Flora-gate при мёрже

| Option | Description | Selected |
|--------|-------------|----------|
| Флора владеет каналами | Оставить gate как в 47fd0c5: action-layer заглушён, флора владеет PCA 0-14 (рекомендация Claude) | |
| Сосуществование | Переработать gate: моторика Адама overlay поверх флоры, флора фон | ✓ |
| Решить кодом при мёрже | Отложить до конфликт-резолюции | |

**User's choice:** Сосуществование
**Notes:** Переопределяет рекомендацию Claude. Требует более глубокой конфликт-резолюции при мёрже: переработать `_execute_action`/scene/stop-гейты на overlay-приоритет вместо полного подавления.

---

## Ollama + рестарт сервисов

| Option | Description | Selected |
|--------|-------------|----------|
| disable + systemd | Ollama stop+disable (обратимо), сервисы через systemd (рекомендация Claude) | |
| purge + systemd | Полное удаление Ollama + сервисы через systemd | ✓ |
| disable + bare | Ollama disable, сервисы bare-процессами без sudo | |

**User's choice:** purge + systemd
**Notes:** Решительное удаление Ollama (apt purge + бинарь + модели + unit). Сервисы — штатно через systemd (нужен sudo). Согласуется с инвариантом «никогда не Ollama».

## Claude's Discretion

- Конфликт порта 8095 (нативный systemd ASR vs Docker ASR) — выбрать один канонический путь при планировании/исполнении.
- Метод reflash ESP под флору (USB esptool / OTA).
- Конкретный механизм overlay «моторика поверх флоры».

## Deferred Ideas

- Виртуальный дисплей / dummy-EDID для headless HDMI-аудио (не нужен при TTS=ESP).
- «Флора единолично владеет каналами» (отвергнут в пользу сосуществования).
- Миграция на ESP-микрофон вместо USB.
- HDMI авто-fallback при ошибке ESP.
