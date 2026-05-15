# BRANCH.md — шаблон и конвенция

## Конвенция

- BRANCH.md создаётся в корне репозитория при создании ветки от main
- Идентификатор = имя ветки (без личных имён, без привязки к конкретному человеку)
- При мёрже: `git rm BRANCH.md` — без архивирования, без следа в истории
- Обновляется по мере работы: статус, modified areas, условие мёржа
- **Поле "Global changes"** — ключевой сигнал для команды:
  - `нет` → чистый эксперимент, мёрж не затронет поведение main
  - описание → нужна координация перед мёржем (Config.json, API, схема данных, архитектурное решение)
- Агент, переключившийся на ветку, читает BRANCH.md первым

## Шаблон

```markdown
# Branch: {branch-name}

**Diverged from:** main @ {commit-hash}
**Goal:** {what this branch does — one line}
**Status:** experimenting | ready-for-review | blocked
**Merge target:** main
**Merge conditions:** {what must be true to merge}

**Modified areas:**
- {file or module}

**Global changes:** нет  ← или: описание того, что изменит поведение main при мёрже

**Notes for agents:**
{context a Claude agent needs when switching to this branch}
```

## Статусы

- `experimenting` — активный эксперимент, результат неизвестен
- `ready-for-review` — готова к мёржу, ждёт ревью
- `blocked` — заблокирована: HW, зависимость, тест
- `stale` — не обновлялась более двух недель, судьба неизвестна
