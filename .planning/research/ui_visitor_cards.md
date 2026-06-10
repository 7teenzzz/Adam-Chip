# UI: Страница "Зрители" — исследование

**Дата:** 2026-06-11  
**Цель:** Проектирование страницы с карточками посетителей для проверки работоспособности VisitorRegistry

---

## 1. АРХИТЕКТУРА WebUI

### Добавление новой панели — три шага

1. `router.js` — добавить в `ROUTES`:
```javascript
visitors: { file: "visitors", label: "Зрители" },
```

2. `main.js` — добавить в `NAV_STRUCTURE` на корневом уровне (как "Метрики", не в подменю):
```javascript
{ key: "visitors", label: "Зрители" },
```

3. Создать `System/WebUI/static/js/panels/visitors.js` с `export function mount(target)`

### Макет

SPA, hash-based routing. Панель монтируется в `<main class="main">`. Возвращает опциональную teardown-функцию.

---

## 2. ПАТТЕРН JS КОМПОНЕНТА

Стандартный паттерн всех панелей Adam Chip:

```javascript
function el(tag, attrs, children = []) { /* DOM builder */ }

export function mount(target) {
  const grid = el("div", { class: "card-grid" });
  
  async function render() {
    grid.innerHTML = "";
    const { visitors } = await api.get("/api/visitors");
    visitors.forEach(v => grid.appendChild(visitorCard(v)));
  }
  
  target.appendChild(el("section", { class: "col" }, [
    el("div", { class: "row" }, [
      el("div", { class: "caps" }, "Зрители"),
      el("span", { class: "spacer" }),
      el("button", { class: "btn", onclick: render }, "Обновить"),
    ]),
    grid,
  ]));
  
  render();
  return () => {};
}
```

### CSS-компоненты (готовые, из components.css):
- `.card-grid` — auto-fill, minmax(320px, 1fr)
- `.card` + `.card-header` + `.card-body` — контейнер карточки
- `.badge` — теги тем, статусы
- `.dot.ok/.warn/.bad` — индикатор настроения
- Переменные: `--accent: #43d17a`, `--muted: #aaaaaa`, `--dim: #606070`

---

## 3. ДИЗАЙН КАРТОЧКИ ПОСЕТИТЕЛЯ

```
┌─────────────────────────────────────────┐
│ Иван                Визит 3  2 дня назад │
├─────────────────────────────────────────┤
│ память · страх · творчество             │  теги тем
│                                          │
│ Первый визит: 10 июня · 15:32            │
│ Последний:    сегодня · 15:45            │
│                                          │
│ Тон: ● тёплый  ○ любознательный          │
│                                          │
│ "Рассказал о своём первом мотоцикле..."  │
│  ← память                               │
│                                          │
│                      [Открыть →]         │
└─────────────────────────────────────────┘
```

**Поля карточки из VisitorRegistry:**
- `name` — заголовок
- `visit_count` + `last_visit_ts` — бейдж + время
- `all_themes` — теги (`.badge` с зелёным фоном)
- `first_visit_ts` / `last_visit_ts` — даты
- `tone_profile` — dict emotion→count, показывать top-2
- `highlights[0]` — последний момент (excerpt 60 символов + тема)

---

## 4. API ENDPOINTS (создать в api_runtime.py)

```python
@router.get("/api/visitors")
# → { "visitors": [{ name, name_slug, visit_count, last_visit_ts, themes[:3], tone_top }], "total": N }

@router.get("/api/visitors/{slug}")
# → полный профиль из visitors/{slug}.json

@router.get("/api/visitors/stats")
# → { total_visitors, total_visits, most_common_themes, last_visit_ts }
```

### Существующие связанные endpoints:
- `GET /api/memory/status` — diary_chars, episodes_total, last_consolidation
- `GET /api/metrics/sessions` — сессии с временными метками

---

## 5. СТРУКТУРА ДАННЫХ (Phase 37)

```
data/adam/visitors/
  _index.json          { "ivan": "2026-06-10T15:45:00Z", ... }
  ivan.json            { name, name_slug, visit_count, first/last_visit_ts,
                         all_themes, tone_profile, highlights[5], episode_ids }
```

---

## 6. СТРАТЕГИЯ РАЗРАБОТКИ

**Вариант C (параллельный):** разрабатывать страницу одновременно с Phase 37-01 (VisitorRegistry):
- На Phase 37-01 определить интерфейс VisitorRegistry
- Параллельно написать visitors.js с mock API (`/api/visitors` → читает статический JSON)
- После готовности VisitorRegistry — подключить реальный endpoint

**Сложность:** LOW (фронтенд ~150–200 строк) + MEDIUM (бэкенд Phase 37)

---

## 7. ОТКРЫТЫЕ ВОПРОСЫ

- Сортировка по умолчанию: last_visit или visit_count?
- Клик на карточку → modal с полным профилем или отдельный роут `/visitors/{slug}`?
- Поиск/фильтр по имени или темам?
- Пагинация (когда посетителей > 50)?
- Иконки для эмоций (emoji или кастомные SVG)?
