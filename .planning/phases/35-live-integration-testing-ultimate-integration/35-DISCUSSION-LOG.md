# Phase 35 — Discussion Log

**Date:** 2026-06-09
**Mode:** discuss (default)

Human-reference audit trail. Not consumed by downstream agents (researcher/planner/executor read CONTEXT.md).

## Areas selected for discussion
Пользователь выбрал все 4: сеть/железо готовность, где крутятся сервисы, авто/ручное разделение + критерии pass, debug-луп + go/no-go.

## Decisions

### Test mode
- **Options:** exhibition only / both maintenance→exhibition / maintenance only
- **Selected:** Both maintenance → exhibition
- **Note:** smoke в maintenance (без power-gate), полный wake-тест в exhibition; послойная развязка дефектов → D-01

### Service source (как загрузить интегрированную версию)
- Первый заход: пользователь ответил «не понимаю вопроса — объясни проще» → переформулировано без жаргона (аналогия с проигрывателем/пластинкой)
- **Options (после переформулировки):** checkout ult в основной каталог / запуск из worktree вручную
- **Selected:** Checkout ultimate-integration в основной каталог + restart orchestrator, worktree убрать → D-02

### Evidence
- **Options:** turn_id трейсы + память / трейсы + запись аудио ESP / только pass-fail чеклист
- **Selected:** turn_id трейсы + память; звук ESP — устное подтверждение → D-03

### Debug loop + push gate
- **Options:** fix-в-worktree до push полный green / батч дефектов потом триаж / push checkpoint fix-forward
- **Selected:** Fix-в-worktree до push, полный green Wave 1-3 → push; full green + reflash → main → D-04

## Carried forward (не переспрашивалось)
Phase 30 D-01..D-05: ESP IP 10.10.10.171 / сеть 10.10.10.x (подтверждено живьём UP), TTS только esp32_speaker, флора=сосуществование, Ollama выпилена, сервисы через systemd.

## Live state snapshot (2026-06-09)
eno1 UP 10.10.10.1/24; ESP :80 OK; llama:8081/TTS:8082/ASR:8095/orch:8080/logviewer:8083 все healthy; Ollama отсутствует; основной каталог = voice-loop-recovery (flora:False, skills:False), mode=maintenance.

## Deferred
Reflash ESP под флору (после push); запись аудио ESP как артефакт; авто-тест физического голоса.
