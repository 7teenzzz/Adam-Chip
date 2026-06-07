# Phase 7: Comprehensive Diploma Analysis — CONTEXT

**Date:** 2026-05-16
**Branch:** `diploma-chapter3`
**Status:** Context gathered, ready for `/gsd-plan-phase 7`

---

## Domain

Структурный аудит всех 4 глав диплома (`diploma/chapters/ch00_introduction.md`, `ch01_chapter1.md`, `ch02_chapter2.md`, `ch03_chapter3.md`) на 5 измерений:

1. **Соответствия** — что согласовано между главами
2. **Расхождения** — где главы противоречат друг другу
3. **Дублирования** — повторные объяснения одного концепта с разной формулировкой
4. **Упущения** — концепты, заявленные но не раскрытые / упомянутые но не доведённые
5. **Терминологическая стабильность** — синонимические дрейфы, замена терминов без причины

Результат: приоритизированная матрица проблем для последующих фаз правок (Ф8 verification → Ф9 planning → Ф10 roadmap).

---

## Carrying forward from prior phases

- **Phase 6B (Memory Pipeline):** реализована 4-слойная память (session + episodic + semantic + search), которая отличается от 2-3-слойного описания в дипломе. Это известное расхождение → войдёт в DUPLICATIONS/GAPS отчёты.
- **Phase 5 (Agent Protocol):** установлена практика `graphify query` и cross-graph анализа (code/persona/esp32). Будем использовать для построения diploma-graph.
- **Phase 1 (Doc Refactor):** введён принцип "lean docs" и Config-First — те же принципы применяем к диплому: один источник истины для каждого термина.

### Существующие baseline-материалы

- `diploma/ANALYSIS-THEORY-vs-CODE.md` — частичный анализ (только гл.3) — будет использован как baseline, но НЕ как окончательная истина (перепроверим в Ф8)
- `diploma/ADDITIONS-FOR-CHAPTER3.md` — документация недавних правок гл.3
- `Knowledge-graphs/diploma/` — граф диплома (будет перестроен в этой фазе)

---

## Decisions

### Scope: все 4 главы

Анализ покрывает `ch00_introduction.md`, `ch01_chapter1.md`, `ch02_chapter2.md`, `ch03_chapter3.md` (исключая `ch99_bibliography.md` и `_drafts/`).

### Terminology depth: 30-50 терминов

TERMINOLOGY-MATRIX.md должна включать **30-50 терминов** — все технические термины + философские понятия. Не "только ключевые" (упускаем нюансы) и не "полный словарь" (избыточно).

Обязательно включить как минимум:
- **Философские/концептуальные:** субъектность, квазисубъектность, агентность, идентичность, симбионт, аффект, феноменология, метакогниция
- **AIIM-специфичные:** аспект, плоскость, уровень зрелости, состояние (Ac/Pa, Or/Ch), приоритет (Δ), формула кодирования, инварианты
- **Технические:** оркестратор, инференция, контекст, промпт (системный, пользовательский), память (сессионная, эпизодическая, семантическая, поисковая), консолидация, салиентность
- **Художественные:** инсталляция, технофлора, проактивность, режимы существования (диалог, бездействие, дремота)

### Report format: Hybrid (matrix + comments)

`07-SUMMARY.md` структура:

```
## Краткая матрица (топ-уровень)
| Глава | Тип проблемы | Серьёзность | Кол-во | Краткое описание |

## Детальные комментарии
### Глава X
- Проблема N: [описание] (Серьёзность: CRITICAL)
  - Где: ...
  - Почему важно: ...
  - Рекомендация: ...
```

### Priority criteria

| Severity | Тип проблемы | Включить в анализ |
|----------|--------------|-------------------|
| **CRITICAL** | Нарушения внутренней логики (противоречия в дипломе) | ✅ Да |
| **HIGH** | Пробелы в раскрытии концептов | ✅ Да |
| **MEDIUM** | Дублирования и синонимические дрейфы | ✅ Да |
| **LOW** | Стилистика, RLHF-признаки | ❌ Нет (отдельная фаза, если понадобится) |

### Subagent strategy: Hybrid (4 parallel + 1 synthesis)

**Wave 1 (parallel):** 4 Explore subagents — по одному на главу. Каждый извлекает:
- Структуру главы (H1/H2/H3/H4)
- Введённые термины с определениями
- Cross-references (на другие главы, разделы, источники)
- Заявленные но не раскрытые концепты

Output: `STRUCTURE-ch{N}.md` (4 файла)

**Wave 2 (sequential):** 1 synthesis subagent читает все 4 STRUCTURE-ch*.md и строит:
- `STRUCTURE.md` — объединённая структура диплома
- `TERMINOLOGY-MATRIX.md` — 30-50 терминов × где введён × где используется × дрейфы
- `DUPLICATIONS.md` — повторные определения
- `GAPS.md` — упущения
- `XREF-AUDIT.md` — целостность cross-references

**Wave 3 (synthesis):** main agent (Sonnet) составляет `07-SUMMARY.md` на основе всех артефактов.

### Graphify

Перед началом Wave 1: `/graphify diploma/chapters/ --mode deep` → перестроить `Knowledge-graphs/diploma/`. Граф используется на Wave 2 для подтверждения связей между терминами.

---

## Canonical refs

- `.planning/ROADMAP.md` — Phase 7 определение
- `diploma/chapters/ch00_introduction.md` — введение
- `diploma/chapters/ch01_chapter1.md` — глава 1 (теория субъектности)
- `diploma/chapters/ch02_chapter2.md` — глава 2 (концептуальная архитектура)
- `diploma/chapters/ch03_chapter3.md` — глава 3 (реализация)
- `diploma/ANALYSIS-THEORY-vs-CODE.md` — частичный baseline (только гл.3)
- `diploma/ADDITIONS-FOR-CHAPTER3.md` — недавние правки гл.3 (контекст)
- `Knowledge-graphs/diploma/GRAPH_REPORT.md` — текущий diploma-граф (будет перестроен)
- `diploma/CLAUDE.md` — инструкции работы над дипломом (forensic researcher mode)

---

## Out of scope (Deferred Ideas)

- **Стилистический аудит (RLHF-маркеры, пустые усилители)** → отдельная мини-фаза, если понадобится после Ф7
- **Сравнение с кодом** → Phase 8 (Theory-Code Verification)
- **Правка текстов диплома** → отдельные фазы из Phase 9 драфтов
- **Анализ библиографии (ch99)** → отдельная фаза, если в Ф7 найдены упущенные источники

---

## Code context (для downstream)

- **Не применимо:** Ф7 — чисто аналитическая фаза, без code-changes
- **graphify** — единственный инструмент, который касается кода/файлов: команда `/graphify diploma/chapters/ --mode deep`
- **subagent type:** Explore (read-only) для Wave 1, general-purpose для Wave 2 synthesis

---

## Success criteria

- [ ] `Knowledge-graphs/diploma/` перестроен с актуальным графом
- [ ] 4 файла `STRUCTURE-ch{N}.md` созданы (один на главу)
- [ ] `STRUCTURE.md` синтезирован
- [ ] `TERMINOLOGY-MATRIX.md` содержит 30-50 терминов с полной матрицей
- [ ] `DUPLICATIONS.md`, `GAPS.md`, `XREF-AUDIT.md` созданы с конкретными находками (не общими наблюдениями)
- [ ] `07-SUMMARY.md` структурирован как Hybrid (матрица + детальные комментарии)
- [ ] Все находки классифицированы по severity (CRITICAL / HIGH / MEDIUM)
- [ ] Артефакты готовы как input для Phase 8 (verification)

---

## Next step

`/gsd-plan-phase 7`
