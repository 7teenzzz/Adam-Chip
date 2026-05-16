# Аудит оптимизации пайплайна для итеративных обновлений

**Дата:** 2026-05-16  
**Контекст:** Проект в активной разработке → Stage 1 и Stage 2 будут запускаться повторно

---

## I. ТЕКУЩИЙ ПАЙПЛАЙН (что есть)

### Структура

```
DIPLOMA.md (Docling output)
    ↓
[MANUAL] 01_diploma_to_architecture.md (prompt)
    ↓
diploma/project-analysis/ (Stage 1 output)
    ├── ch01/, ch02/, ch03/
    └── synthesis/
    ↓
[MANUAL] 02_code_to_diploma_verification.md (prompt)
    ↓
diploma/project-verification/ (Stage 2 output)
    ├── by-criterion/ (8 файлов)
    ├── by-section/ (4 файла)
    ├── chapter3_materials/ (1 файл)
    └── [16 пустых папок для будущего]
    ↓
[MANUAL] 03_write_chapter3.md (prompt)
    ↓
diploma/chapter-3/ (Writing Stage 3)
```

### Автоматизация (есть)

| Компонент | Тип | Статус | Назначение |
|-----------|-----|--------|-----------|
| `consolidate_chapters.py` | Script | ✅ Есть | Собрать главы из sections/ |
| `convert_pdf_pymupdf.py` | Script | ✅ Есть | Docling conversion PDF → Markdown |
| `split_diploma.py` | Script | ✅ Есть | Разбить Diploma.md на главы |
| `inspect_structure.py` | Script | ✅ Есть | Inspect документа структура |
| `/graphify` | CLI skill | ✅ Есть | Knowledge graph extraction |
| `.planning/ROADMAP.md` | Config | ✅ Есть | Project phases tracking |

### Версионирование (есть)

| Файл | Тип | Версионируется? | Статус |
|------|-----|-----------------|--------|
| Diploma.md | Source | ✅ Git | Docling output (контролируется) |
| diploma/project-analysis/ | Output | ❌ Git-ignored? | Нет версионирования |
| diploma/project-verification/ | Output | ❌ Git-ignored? | Нет версионирования |
| diploma/chapter-3/ | Output | ✅ Git | Контролируется |

---

## II. ❌ ПРОБЛЕМЫ ОПТИМИЗАЦИИ

### A. Нет incremental processing

**Проблема:** Каждый раз при изменении кода нужно:

1. Запустить `/graphify System/ --mode deep` полностью (10-15 минут)
2. Переделать ALL из `diploma/project-analysis/` с нуля (Stage 1)
3. Переделать ALL из `diploma/project-verification/` с нуля (Stage 2)

**Последствия:**
- Теряются старые выводы (если они были в папках, которые не переполняются)
- Нет history изменений
- Каждое изменение кода = полный rebuild (дорого по времени)

**Рекомендация:** Нужен incremental mode:
- `/graphify System/ --update` (уже есть в graphify!)
- Версионирование Stage output (добавить даты)
- Diff-механизм между версиями

---

### B. Нет автоматизированного batch-запуска

**Проблема:** Все три stage запускаются вручную:

1. `01_diploma_to_architecture.md` → ctrl+C → сохранить
2. Закрыть, перечитать project-analysis/
3. `02_code_to_diploma_verification.md` → ctrl+C → сохранить
4. Закрыть, перечитать project-verification/
5. `03_write_chapter3.md` → ctrl+C → сохранить

**Последствия:**
- Ошибки в ручном процессе
- Потеря связей между stage-ами
- Сложно обновить, если нужны изменения в Stage 1

**Рекомендация:** Нужен batch скрипт:
```bash
./scripts/diploma_stage_all.sh [--update] [--force]
```

---

### C. Нет dependency tracking

**Проблема:** Не ясно, какой output зависит от чего:

```
Если изменится:
  - Diploma.md                → пересчитать Stage 1?
  - System/adam/memory.py     → пересчитать Stage 2?
  - Config.json               → пересчитать Stage 2?
  - criteria_to_code.md       → пересчитать Stage 2?
```

Сейчас это неясно. Нет makefile или requirements.txt для output.

**Рекомендация:** Нужна dependency matrix:
```yaml
Stage1_output:
  depends_on:
    - Diploma.md
    - evaluation_criteria.md
  invalidates_if_changed:
    - diploma/Diploma.md
    - diploma/evaluation_criteria.md

Stage2_output:
  depends_on:
    - Stage1_output (project-analysis/)
    - graphify-out/graph.json
    - graphify-out-persona/
  invalidates_if_changed:
    - System/adam/**/*.py
    - System/Config.json
    - graphify-out/
```

---

### D. Нет версионирования output

**Проблема:** Нет способа узнать, когда был создан output:

```
diploma/project-analysis/
  ├── ch01/subjectivity_framework.md  ← дата создания? неизвестна
  ├── ch02/evaluation_criteria_extracted.md  ← дата создания? неизвестна
  └── ...

diploma/project-verification/
  ├── by-criterion/crit_01_autonomy.md  ← дата создания? 2026-05-16
  └── ...
```

Нет механизма для отката к старой версии, если Stage 1 или 2 "сломалась".

**Рекомендация:** Нужны timestamps в файлах:

```markdown
# Stage 1 Output: diploma/Diploma.md → concepts

**Generated:** 2026-05-16T17:30:45Z  
**Source:** diploma/Diploma.md (~143,000 words, 172 files)  
**Validation:** ✅ complete (41 nodes, 53 edges)  
**Next update due:** When Diploma.md changes or manually triggered
```

---

### E. Нет cache для graphify queries

**Проблема:** `/graphify query "<concept>"` каждый раз выполняется заново.

Если Stage 2 делает 50 queries, каждый раз 50 queries × N раз переделываются без cache.

**Рекомендация:** Нужен local cache:
```json
// graphify-out/.query_cache.json
{
  "memory system": {
    "query": "memory system",
    "timestamp": "2026-05-16T17:00:00Z",
    "result": {
      "nodes": [...],
      "edges": [...],
      "community": [...]
    }
  }
}
```

---

### F. Нет механизма для diff между версиями

**Проблема:** Если Stage 1 или 2 переделается, неясно что изменилось:

```
OLD: crit_03_identity.md (50 строк, FULL status)
NEW: crit_03_identity.md (50 строк, FULL status)

Что изменилось? Graphify evidence? Recommendations? Findings?
Нет diff-механизма, чтобы узнать.
```

**Рекомендация:** Нужен diff report:
```
diploma/project-verification/.UPDATES/
  └── 2026-05-16_DIFF_REPORT.md
      ├── Files changed: 12
      ├── Files added: 0
      ├── Files removed: 0
      └── Changes:
          - crit_05_temporal.md: graphify_evidence [+3 nodes, -1 node, ~3 edges]
          - 3.4_testing.md: findings [minor wording]
          - REVIEW_CHECKPOINT.md: [tension #1 updated]
```

---

### G. Нет валидации целостности output

**Проблема:** После Stage 1 или 2 никак не проверяется:
- Все ли файлы созданы?
- Все ли cross-references корректны?
- Нет ли orphaned nodes?

**Рекомендация:** Валидационный скрипт:
```bash
./scripts/validate_stage_output.sh [stage1|stage2]
# Output:
# ✅ All 8 criterion files present
# ✅ All cross-references valid
# ⚠️ 2 missing recommendations
# ❌ 1 orphaned synthesis file
```

---

## III. ✅ ЧТО УЖЕ ОПТИМИЗИРОВАНО

| Компонент | Оптимизация | Статус |
|-----------|-------------|--------|
| **Graphify** | `--update` mode (incremental) | ✅ Built-in |
| **Graphify** | `--mode deep` vs `--mode fast` | ✅ Built-in |
| **Python scripts** | `consolidate_chapters.py` и т.д. | ✅ Готовы |
| **Planning** | `.planning/ROADMAP.md` + phases | ✅ Структурировано |
| **Git** | `.gitignore` (вероятно для output) | ⚠️ Нужно проверить |

---

## IV. 🛠️ РЕКОМЕНДУЕМЫЕ ОПТИМИЗАЦИИ

### Priority 1 (Critical) — нужно прямо сейчас

#### 1. Добавить timestamps в Stage output

```markdown
# GENERATED: 2026-05-16T17:30:45Z
# SOURCE: diploma/Diploma.md
# STAGE: 1
# STATUS: ✅ complete
# NEXT_UPDATE: [manual trigger | when source changes]
```

**Где добавить:**
- `diploma/project-analysis/ch01/concepts/subjectivity_framework.md` (в начало)
- `diploma/project-analysis/ch02/concepts/evaluation_criteria_extracted.md` (в начало)
- Все файлы в `diploma/project-verification/by-criterion/` (уже есть? проверить)
- Все файлы в `diploma/project-verification/by-section/` (уже есть? проверить)

**Кто:** Можно добавить вручную или скриптом

---

#### 2. Создать batch-скрипт для всех stage-ов

```bash
#!/bin/bash
# scripts/diploma_stage_all.sh

STAGE=${1:-all}  # [1|2|3|all]
MODE=${2:-normal}  # [normal|update|force]

echo "[DIPLOMA PIPELINE] Stage=$STAGE Mode=$MODE"

if [[ $STAGE =~ (1|all) ]]; then
  echo "🔄 Stage 1: Diploma → Architecture Analysis"
  # Запустить с 01_diploma_to_architecture.md
  # Сохранить в diploma/project-analysis/
  # Добавить timestamp
  # Выполнить валидацию
fi

if [[ $STAGE =~ (2|all) ]]; then
  echo "🔄 Stage 2: Code → Diploma Verification"
  # Запустить с 02_code_to_diploma_verification.md
  # Сохранить в diploma/project-verification/
  # Добавить timestamp
  # Выполнить валидацию
  # Генерировать diff report
fi

if [[ $STAGE =~ (3|all) ]]; then
  echo "🔄 Stage 3: Writing Chapter 3"
  # Запустить с 03_write_chapter3.md
  # Сохранить в diploma/chapter-3/
fi
```

**Где:**  `f:/Adam-Chip/scripts/diploma_stage_all.sh`

**Кто:** Нужно написать

---

#### 3. Создать dependency matrix

```yaml
# diploma/.dependencies.yaml

outputs:
  stage1:
    path: diploma/project-analysis/
    depends_on:
      - diploma/Diploma.md (hash-based validation)
      - diploma/evaluation_criteria.md
      - graphify-out/graph.json (for reference)
    invalidates_if_changed:
      - diploma/Diploma.md
      - diploma/evaluation_criteria.md
    expected_files:
      - ch01/concepts/subjectivity_framework.md
      - ch02/concepts/evaluation_criteria_extracted.md
      - ch03/architecture/system_map.md
      - synthesis/criteria_to_code.md
    validation:
      - all_files_present: true
      - cross_references_valid: true
    
  stage2:
    path: diploma/project-verification/
    depends_on:
      - diploma/project-analysis/ (all files)
      - graphify-out/graph.json
      - graphify-out-persona/
      - System/Config.json (for reference)
    invalidates_if_changed:
      - System/adam/**/*.py
      - System/Config.json
      - graphify-out/ (if nodes > 20 changed)
    expected_files:
      - by-criterion/crit_*.md (8 files)
      - by-section/3.*_*.md (4 files)
      - REVIEW_CHECKPOINT.md
    validation:
      - all_criteria_covered: true
      - graphify_evidence_present: true
```

**Где:** `f:/Adam-Chip/diploma/.dependencies.yaml`

**Кто:** Нужно создать

---

### Priority 2 (Important) — полезно для workflow'а

#### 4. Версионирование old outputs

```
diploma/.versions/
  ├── 2026-05-15/
  │   ├── project-analysis/  (backup старой версии Stage 1)
  │   └── project-verification/  (backup старой версии Stage 2)
  └── 2026-05-16/
      ├── project-analysis/
      └── project-verification/
```

**Когда:** После каждого Stage 1 или 2 переделать

**Как:** `tar -czf diploma/.versions/$(date +%Y-%m-%d)/project-analysis.tar.gz diploma/project-analysis/`

---

#### 5. Diff report между версиями

```markdown
# DIFF REPORT: Stage 2 Output (2026-05-15 → 2026-05-16)

## Files changed: 7 / 13
- by-criterion/crit_03_identity.md (+2 lines, ~0.5 KB)
- by-criterion/crit_05_temporal.md (+15 lines, +3 graphify nodes)
- by-section/3.4_testing.md (+5 lines, wording change)
- REVIEW_CHECKPOINT.md (+0 lines, 2 tensions resolved → 4 open)

## Files unchanged: 6 / 13
- by-criterion/crit_01_autonomy.md ✓
- by-criterion/crit_02_agency.md ✓
- ...

## Key changes:
- Criterion 3 (Identity): FULL status confirmed
- Criterion 5 (Temporal): graphify evidence +3 nodes (new modules found)
- Tension #2 (AIIM operationalization): updated recommendation

## Recommendations for Chapter 3 writing:
- Update 3.2.3 with new graphify evidence (3 nodes)
- Section 3.4.3 can reference updated crit_05_temporal.md
```

**Где:** `diploma/.versions/2026-05-16/DIFF_REPORT.md`

**Кто:** Можно генерировать скриптом

---

#### 6. Валидационный скрипт

```bash
#!/bin/bash
# scripts/validate_stage_output.sh [1|2|all]

STAGE=${1:-all}

validate_stage1() {
  local path="diploma/project-analysis"
  echo "Validating Stage 1 output..."
  
  # Проверка: все ли файлы есть?
  local expected=(
    "ch01/concepts/subjectivity_framework.md"
    "ch02/concepts/evaluation_criteria_extracted.md"
    "ch03/architecture/system_map.md"
    "synthesis/criteria_to_code.md"
  )
  
  for file in "${expected[@]}"; do
    if [[ ! -f "$path/$file" ]]; then
      echo "❌ MISSING: $path/$file"
      return 1
    fi
  done
  
  # Проверка: все ли cross-references?
  grep -r "\[\[" $path | grep -v ":\[\[" || echo "⚠️ No cross-references found"
  
  echo "✅ Stage 1 validation passed"
}

validate_stage2() {
  local path="diploma/project-verification"
  echo "Validating Stage 2 output..."
  
  # Проверка: все ли 8 критериев?
  local expected_crit=8
  local found_crit=$(ls $path/by-criterion/crit_*.md | wc -l)
  
  if [[ $found_crit -ne $expected_crit ]]; then
    echo "❌ Expected $expected_crit criteria, found $found_crit"
    return 1
  fi
  
  # Проверка: graphify evidence в каждом?
  for file in $path/by-criterion/crit_*.md; do
    if ! grep -q "Graphify Evidence\|graphify_evidence" "$file"; then
      echo "⚠️ MISSING graphify_evidence: $file"
    fi
  done
  
  echo "✅ Stage 2 validation passed"
}

case $STAGE in
  1) validate_stage1 ;;
  2) validate_stage2 ;;
  all) validate_stage1 && validate_stage2 ;;
esac
```

**Где:** `f:/Adam-Chip/scripts/validate_stage_output.sh`

**Кто:** Нужно создать

---

#### 7. Cache для graphify queries

```json
// diploma/.graphify_query_cache.json
{
  "_metadata": {
    "created": "2026-05-16T17:30:00Z",
    "ttl_hours": 24,
    "graph_timestamp": "2026-05-16T17:00:00Z"
  },
  "memory system": {
    "query": "memory system",
    "nodes": ["EpisodicMemory", "SessionAccumulator", "memory.py"],
    "edges": 12,
    "timestamp": "2026-05-16T17:15:00Z"
  },
  "identity": {
    "query": "identity",
    "nodes": ["TuningStore", "PromptBuilder", "Identity.md"],
    "edges": 8,
    "timestamp": "2026-05-16T17:16:00Z"
  }
}
```

**Где:** `diploma/.graphify_query_cache.json`

**Кто:** Можно генерировать скриптом после Stage 2

---

### Priority 3 (Nice-to-have) — для долгосрочного масштабирования

#### 8. CI/CD integration

```yaml
# .github/workflows/diploma_update.yml
name: Auto-update diploma stages

on:
  push:
    paths:
      - 'System/adam/**'
      - 'System/Config.json'
      - 'diploma/Diploma.md'
      - 'diploma/evaluation_criteria.md'

jobs:
  stage1:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Stage 1
        run: |
          ./scripts/diploma_stage_all.sh 1 update
      - name: Commit changes
        run: |
          git add diploma/project-analysis/
          git commit -m "ci: auto-update Stage 1 output"
          git push
```

**Где:** `.github/workflows/diploma_update.yml`

**Статус:** Нужно создать (опционально)

---

## V. ROADMAP ОПТИМИЗАЦИИ

### Phase 1 (This week)

- ✅ Audit текущего пайплайна (DONE: этот документ)
- [ ] Добавить timestamps в Stage output
- [ ] Создать batch-скрипт (`diploma_stage_all.sh`)
- [ ] Создать `.dependencies.yaml`
- [ ] Создать валидационный скрипт

**Время:** ~2-3 часа

### Phase 2 (Next week)

- [ ] Версионирование old outputs (`.versions/`)
- [ ] Diff report generator
- [ ] Graphify query cache
- [ ] Update `.gitignore` (явно указать Stage output)

**Время:** ~3-4 часа

### Phase 3 (Optional)

- [ ] CI/CD integration (GitHub Actions)
- [ ] Web dashboard для версионирования
- [ ] Monthly archival

**Время:** ~4-6 часов (опционально)

---

## VI. IMPLEMENTATION CHECKLIST

### Immediately (Priority 1)

- [ ] Добавить timestamp header в files из Stage 1 output
  - [ ] diploma/project-analysis/ch01/concepts/subjectivity_framework.md
  - [ ] diploma/project-analysis/ch02/concepts/evaluation_criteria_extracted.md
  - [ ] diploma/project-analysis/ch03/architecture/system_map.md
  - [ ] diploma/project-analysis/synthesis/criteria_to_code.md

- [ ] Добавить timestamp header в files из Stage 2 output
  - [ ] diploma/project-verification/by-criterion/*.md (8 files)
  - [ ] diploma/project-verification/by-section/*.md (4 files)
  - [ ] diploma/project-verification/REVIEW_CHECKPOINT.md
  - [ ] diploma/project-verification/chapter3_materials/final_chapter_blueprint.md

- [ ] Написать `scripts/diploma_stage_all.sh`

- [ ] Написать `diploma/.dependencies.yaml`

- [ ] Написать `scripts/validate_stage_output.sh`

### Next week (Priority 2)

- [ ] Создать `diploma/.gitignore.stage_output`

- [ ] Написать версионирование скрипт (`scripts/version_stage_output.sh`)

- [ ] Написать diff report generator (`scripts/generate_stage_diff.sh`)

- [ ] Создать `diploma/.graphify_query_cache.json` template

---

## VII. ЗАКЛЮЧЕНИЕ

**Текущее состояние:** 40% оптимизирован для итеративных обновлений

**Что работает:**
- ✅ Graphify `--update` mode (incremental)
- ✅ Python helper scripts
- ✅ Planning infrastructure

**Что не работает:**
- ❌ Нет batch-запуска
- ❌ Нет версионирования output
- ❌ Нет dependency tracking
- ❌ Нет валидации целостности
- ❌ Нет cache для queries

**Рекомендация:** Реализовать Priority 1 (критические) перед следующим обновлением Stage 1/2. Это займёт ~2-3 часа и сэкономит часы при каждом последующем обновлении.

