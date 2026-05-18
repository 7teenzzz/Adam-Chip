# Branch: V-S09.1-Audio_out

**Diverged from:** main @ e254a09
**Goal:** Phase 21A — переделать «эквалайзер» на странице чата в реальный FFT-спектр + цвет-по-уровню + починить SSE-утечку виджета.
**Status:** experimenting
**Merge target:** main
**Merge conditions:**
- Phase 21A артефакты созданы (`21A-CONTEXT.md` → `21A-PLAN.md` → execute → verify)
- ROADMAP.md обновлён: Phase 21A зафиксирована как слайс Phase 21
- Backend: FFT-публикация спектра не ломает существующий `audio_level` event
- Frontend: OWW score / threshold / drag (на settings) работают как раньше
- В Config.json вынесены параметры: число bands, cadence публикации, масштаб (lin/log), normalisation
- Smoke-тест на чат-панели: бары следуют за голосом, при пике бар становится красным, при тишине плоско

**Modified areas:**
- `System/adam/` — источник звука (MicReader / audio worker) + event bus (новое событие или расширение `audio_level`)
- `System/Config.json` + `System/Config.schema.json` — новые параметры FFT
- `System/WebUI/static/js/widgets/wakeMeter.js` — рендер реального спектра, градиент цвета, fix SSE leak
- `System/WebUI/static/js/panels/chat.js` — подпись/подсказка под виджетом
- `.planning/phases/21-ui-rebuild/` или `.planning/phases/21A-chat-eq-real-spectrum/` — артефакты фазы
- `.planning/ROADMAP.md` — фиксация Phase 21A как подфазы Phase 21

**Global changes:**
- Новое SSE-событие (или новое поле в `audio_level`) — фронт-код, который слушает `audio_level`, обязан игнорировать неизвестные поля. Координация: проверить settings.js / chat.js / любых других consumer'ов перед мёржем.
- Новые ключи в Config.json (FFT bands, cadence). Hot-reload должен подхватить без рестарта.

**Notes for agents:**
- Базовый отчёт по текущему коду «эквалайзера» — см. историю чата сессии 2026-05-18, или просто перечитать [System/WebUI/static/js/widgets/wakeMeter.js](System/WebUI/static/js/widgets/wakeMeter.js): бары — иллюзия (фиксированная Gaussian EQ_SHAPE × один скаляр `audioLevel` × `sin(Date.now())`).
- OWW score (голубая линия) и threshold (оранжевый пунктир) — НЕ ТРОГАТЬ, логика отображения сохраняется.
- Decay/peak-hold с баров убираем полностью: бары следуют за FFT-кадрами без сглаживания (решение пользователя — «максимально честно»).
- Цвет бара = градиент по его уровню (зелёный → жёлтый → красный). `mic_source` остаётся индикатором в VU-meter и в badge, в эквалайзер не дублируется.
- FFT источник: исключительно серверный (Jetson, MicReader или audio worker). Web Audio в браузере не подходит — будет микрофон ноутбука оператора, не Adam'a.
