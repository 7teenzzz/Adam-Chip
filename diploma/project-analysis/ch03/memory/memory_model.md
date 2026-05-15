# Memory Model — Глава 3.2.4

## Многоуровневая структура памяти (как заявлено)

### Level 1: Working History
- **Role.** Краткосрочная память сессии.
- **Format.** История последних реплик в рабочем виде.
- **Limit.** Ограниченное окно (для скорости).
- **Function.** Удерживать тему, не повторяться, сохранять тон.

### Level 2: Session Summarization
- **File.** `Summarized.json`
- **Role.** Интервальные обобщения сессий.
- **Format.** Краткие резюме: что произошло, как менялось состояние, темы.
- **Function.** Долгая связность между сессиями.

### Level 3: Notes
- **File.** `Notes.json`
- **Role.** Фрагментарная заметочная память.
- **Selection.** Не все события, а специально отобранные (системой или оператором).
- **Function.** Точечная память: характерные реплики, мотивы, реакции.

### Level 4: State Memory
- **Role.** Аффективная непрерывность.
- **Content.** Внутренний режим агента (тревога, спокойствие, активация).
- **Function.** Контекст для интерпретации следующего события.

### Level 5: Permanent Biography
- **File.** `Bio.md` + другие постоянные текстовые основания.
- **Role.** Долговременная идентичность.
- **Content.** Происхождение, общая логика существования, ключевые черты.
- **Stability.** Не стирается при очистке рабочей памяти.

---

## Retrieval Strategy

**Approach.** RAG-подобный, но не внешний поиск, а внутренняя выборка.

**Logic.** Orchestrator не передаёт всё содержимое памяти в LLM, а извлекает только то, что **может повлиять на текущее решение**.

**Constraint.** Контекст компактный (для скорости), память полезная (не накопительная).

---

## Cycle of Knowledge Promotion

```text
Raw event (reply / observation)
  ↓
Working history
  ↓ (при необходимости)
Summary OR Note OR State change
  ↓ (если глубокий уровень)
Permanent biography
```

---

## Theoretical Foundation

- **Episodic memory** → Level 1 + Level 2
- **Semantic memory** → Level 5 (Bio)
- **Narrative continuity** (Ricoeur) → cumulative through all levels
- **Salience selection** → Level 3 (Notes) + Level 4 (State)

---

## Expected Code Correspondences

| Diploma concept | Adam Chip код |
|---|---|
| Working history | `episodic.py` (SessionAccumulator) |
| Summarized.json | `consolidator.py` (Engineering/) + summaries in data/adam/summaries/ |
| Notes.json | `episodic.py` (notes) + data/adam/notes/ |
| State memory | (?) tuning.py state? — проверить в Stage 2 |
| Bio.md | `Agent Adam Chip/About/*.md` (Identity, Lore, Abilities) |
| RAG retrieval | `prompt.py` (PromptBuilder) + `memory.py` |
