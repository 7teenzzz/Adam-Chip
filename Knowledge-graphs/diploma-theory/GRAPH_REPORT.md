# Graph Report - diploma  (2026-05-16)

## Corpus Check
- 74 files · ~98,989 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 41 nodes · 53 edges · 11 communities (6 shown, 5 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Диплом - документация|Диплом - документация]]
- [[_COMMUNITY_Критерии и верификация|Критерии и верификация]]
- [[_COMMUNITY_Архитектура системы|Архитектура системы]]
- [[_COMMUNITY_Оценка и тестирование|Оценка и тестирование]]
- [[_COMMUNITY_Речевой контур|Речевой контур]]
- [[_COMMUNITY_Память и контекст|Память и контекст]]
- [[_COMMUNITY_Моторное управление|Моторное управление]]
- [[_COMMUNITY_Выставочный сценарий|Выставочный сценарий]]
- [[_COMMUNITY_Технические инструменты|Технические инструменты]]
- [[_COMMUNITY_Проактивность|Проактивность]]
- [[_COMMUNITY_Конфигурация|Конфигурация]]

## God Nodes (most connected - your core abstractions)
1. `split_diploma()` - 7 edges
2. `build_markdown()` - 4 edges
3. `main()` - 4 edges
4. `numbered_level()` - 4 edges
5. `detect_heading_style()` - 4 edges
6. `parse_headings()` - 4 edges
7. `extract_figures()` - 3 edges
8. `extract_bibliography()` - 3 edges
9. `convert()` - 3 edges
10. `extract_text_with_pages()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `extract_text_with_pages()`  [EXTRACTED]
  convert_pdf_pymupdf.py → convert_pdf_pymupdf.py  _Bridges community 8 → community 6_
- `main()` --calls--> `build_markdown()`  [EXTRACTED]
  convert_pdf_pymupdf.py → convert_pdf_pymupdf.py  _Bridges community 3 → community 6_
- `split_diploma()` --calls--> `slugify()`  [EXTRACTED]
  split_diploma.py → split_diploma.py  _Bridges community 10 → community 2_
- `parse_headings()` --calls--> `numbered_level()`  [EXTRACTED]
  split_diploma.py → split_diploma.py  _Bridges community 4 → community 9_
- `split_diploma()` --calls--> `detect_heading_style()`  [EXTRACTED]
  split_diploma.py → split_diploma.py  _Bridges community 4 → community 2_

## Communities (11 total, 5 thin omitted)

### Community 0 - "Диплом - документация"
Cohesion: 0.38
Nodes (6): convert(), extract_bibliography(), extract_figures(), Docling PDF → Markdown конвертер с дополнительной экстракцией.  Использование:, Walk pictures and tables, dump captions to markdown., Heuristic: take everything from biblio trigger to EOF.

### Community 1 - "Критерии и верификация"
Cohesion: 0.53
Nodes (5): analyze(), main(), numbered_level(), Diploma structure inspector — read-only валидация Docling output.  Проверяет кач, recommend()

### Community 2 - "Архитектура системы"
Cohesion: 0.53
Nodes (5): extract_block(), Diploma splitter — разбивает Diploma.md на иерархические фрагменты.  Поддерживае, sec_idx_total(), split_diploma(), sub_idx_total()

### Community 3 - "Оценка и тестирование"
Cohesion: 0.5
Nodes (4): build_markdown(), looks_like_heading(), Detect Russian numbered headings. Returns (level, normalized_text) or None., Build markdown with heading detection and page markers.

### Community 4 - "Речевой контур"
Cohesion: 0.5
Nodes (4): detect_heading_style(), numbered_level(), 1' → 1, '1.1' → 2, '1.1.1' → 3, '1.1.1.1' → 4., Returns one of: markdown, russian_numbered, bold_numbered.     Picks the style y

### Community 6 - "Моторное управление"
Cohesion: 0.67
Nodes (3): extract_bibliography(), main(), Heuristic: take everything after a bibliography trigger heading.

## Knowledge Gaps
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `split_diploma()` connect `Архитектура системы` to `Проактивность`, `Конфигурация`, `Речевой контур`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `numbered_level()` connect `Речевой контур` to `Проактивность`, `Архитектура системы`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Why does `detect_heading_style()` connect `Речевой контур` to `Архитектура системы`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **What connects `Consolidate fragmented chapter files into canonical 4-chapter layout.  PyMuPDF-b`, `Docling PDF → Markdown конвертер с дополнительной экстракцией.  Использование:`, `Walk pictures and tables, dump captions to markdown.` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._