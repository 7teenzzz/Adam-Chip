# AIIM Editor Backend — Research Findings

Дата: 2026-06-11  
Ветка: ultimate-integration-v2

---

## 1. Точная структура AIIM formula

Файл: `Agent-Adam-Chip/About/Identity.md` — первый code block.

```
wi(P 4 Ac-Or)Δ0.65;  lo(S 4 Ac-Or)Δ0.70;  im(P 3 Ac-Ch)Δ0.65;
ho(I 3 Pa-Or)Δ0.60;  co(T 4 Ac-Or)Δ0.88;  em(B 3 Ac-Ch)Δ0.60;
be(S 3 Ac-Or)Δ0.65;  sp(T 4 Pa-Or)Δ0.85;  se(I 4 Ac-Ch)Δ0.92;
pe(T 3 Ac-Or)Δ0.70;  me(B 2 Pa-Ch)Δ0.30;  at(S 4 Ac-Or)Δ0.70
```

### Расшифровка формата: `aspect(plan level mode)Δweight`

| Поле | Тип | Возможные значения | Описание |
|------|-----|--------------------|----------|
| `aspect` | str | wi, lo, im, ho, co, em, be, sp, se, pe, me, at | Код аспекта (12 штук) |
| `plan` | str | B, S, P, I, T | Где аспект работает: Body, Social, Self, Inner-links, Transcendental |
| `level` | int | 1–4 | Зачаточный→Мастерский |
| `mode` | str | Ac-Or, Ac-Ch, Pa-Or, Pa-Ch | Activity-Order: Active/Passive, Ordered/Chaotic |
| `weight` (Δ) | float | 0.0–1.0 | Частота/сила влияния аспекта |

### Парсинг: regex `(\w+)\((\w) (\d) ([\w-]+)\)Δ(\d+\.\d+)`

Реализован в `System/adam/identity.py → parse_aiim_formula()`. Читает первый fenced code block из Identity.md.

---

## 2. Аспекты и их семантика

| Код | Название | plan | level | mode | weight | Роль |
|-----|----------|------|-------|------|--------|------|
| wi  | воля | P | 4 | Ac-Or | 0.65 | Рабочий |
| lo  | эмпатия | S | 4 | Ac-Or | 0.70 | Рабочий |
| im  | идеи | P | 3 | Ac-Ch | 0.65 | Рабочий |
| ho  | этика | I | 3 | Pa-Or | 0.60 | Вспомогательный |
| co  | логика | T | 4 | Ac-Or | 0.88 | **ЯДРО** (LOCKED) |
| em  | эмоция | B | 3 | Ac-Ch | 0.60 | Вспомогательный |
| be  | действие | S | 3 | Ac-Or | 0.65 | Рабочий |
| sp  | смысл | T | 4 | Pa-Or | 0.85 | Ядро |
| se  | самоосознание | I | 4 | Ac-Ch | 0.92 | **ЯДРО** (LOCKED) |
| pe  | восприятие | T | 3 | Ac-Or | 0.70 | Рабочий |
| me  | память | B | 2 | Pa-Ch | 0.30 | Едва заметен |
| at  | внимание | S | 4 | Ac-Or | 0.70 | Рабочий |

**LOCKED аспекты** (никогда не дрейфуют и не модулируются): `se`, `co`.  
Источник: `IdentityVector.LOCKED: frozenset({"se", "co"})` в `identity.py`.

---

## 3. AspectSpec fields (из identity.py)

```python
@dataclass
class AspectSpec:
    code: str       # "wi"
    plan: str       # "P" / "B" / "S" / "I" / "T"
    level: int      # 1–4
    mode: str       # "Ac-Or" / "Ac-Ch" / "Pa-Or" / "Pa-Ch"
    weight: float   # 0.0–1.0 (исходное значение из формулы)
```

---

## 4. Диапазоны значений

### Веса аспектов (weight / Δ)
- Диапазон: **0.0 – 1.0**
- Семантика: `<0.3` едва заметен, `0.3–0.5` вспомогательный, `0.5–0.8` рабочий, `>0.8` ядро

### Per-turn модуляция (AspectModulator, из tuning.py)
| Эмоция | Аспект | delta | aspect_min/max |
|--------|--------|-------|----------------|
| warm   | lo     | +0.08 | 0.20–0.95 |
| warm   | em     | +0.05 | |
| unease | me     | +0.10 | |
| unease | em     | +0.05 | |
| sharp  | wi     | +0.08 | |
| sharp  | im     | +0.05 | |
| curious| at     | +0.05 | |
| calm   | все    | decay –0.02 (×0.5 для Pa) | |

Пассивные аспекты (Pa-*) масштабируют delta × 0.5. Хаотичные (Ch) добавляют gaussian noise σ=0.008.

### Drift ceilings (AspectCeilingConfig, из tuning.py)
| Аспект | Потолок |
|--------|---------|
| lo | 0.85 |
| em | 0.75 |
| sp | 0.95 |
| ho | 0.75 |
| wi | 0.75 |
| me | 0.60 |
| at | 0.80 |

(se, co — LOCKED, ceiling не применяется)

---

## 5. Cross-session drift (identity_drift.py)

### DriftRecord (`data/adam/identity/drift.json`)
```json
{
  "schema_version": 1,
  "aspect_drift": {"lo": 0.012, "em": 0.005, ...},
  "session_counts": {"deep_contact": 3, "witnessed": 7, ...},
  "total_sessions": 10,
  "created_at": "2026-01-01T00:00:00+00:00",
  "last_updated": "2026-06-10T12:00:00+00:00"
}
```

### SessionExperienceType (как classify_session работает)
| Тип | Условие | Drift table entries |
|-----|---------|---------------------|
| deep_contact | warm > 0 AND salience ≥ 0.5 | lo+0.005, em+0.002, sp+0.001 |
| confrontation | sharp > 0 | ho+0.003, wi+0.002 |
| memory_surfacing | unease ≥ 2 | me+0.005, sp+0.002 |
| witnessed | turns ≥ 2 AND salience ≥ 0.2 | at+0.001 |
| void | всё остальное | (пусто) |

### Формула: `delta = base_delta × salience`
- Применяется один раз в конце сессии
- Потолок: `max_accum = ceiling - base_weight`
- Пол: drift не может уменьшить вес ниже 50% от base

---

## 6. Текущие endpoints (что уже есть)

В `System/adam/api_runtime.py`:

- `GET /api/persona` — возвращает полный сырой текст всех persona_paths файлов (включая Identity.md). **Нет структурированного парсинга AIIM формулы.**
- `PUT /api/persona` — перезаписывает файл целиком (по пути). Identity.md можно писать через него.
- `GET /api/config` — все runtime параметры включая `tuning.identity.*`
- `PATCH /api/config` — hot-reload патч для tuning.identity (base_weights, transitions, ceilings, etc.)

**AIIM-specific API отсутствует.** `runtime_state["aiim_state"]` доступен только внутри Orchestrator.

---

## 7. Что нужно для генерации новой Identity.md формулы

### Формат записи (строго)
1. Первый code block файла — это формула. Парсер читает только его.
2. Формат строки: `code(plan level mode)Δweight`
3. Разделитель между аспектами: `;  ` (точка с запятой + 2 пробела)
4. 3 аспекта в строке, потом перенос

Пример генерации из dict:
```python
ASPECT_ORDER = ["wi","lo","im","ho","co","em","be","sp","se","pe","me","at"]

def format_formula(specs: dict[str, AspectSpec]) -> str:
    tokens = []
    for code in ASPECT_ORDER:
        s = specs[code]
        tokens.append(f"{s.code}({s.plan} {s.level} {s.mode})Δ{s.weight:.2f}")
    lines = []
    for i in range(0, len(tokens), 3):
        lines.append(";  ".join(tokens[i:i+3]))
    return "\n".join(lines)
```

### Сохранение в Identity.md
PUT /api/persona уже умеет перезаписывать файл. Нужно:
1. Прочитать текущий Identity.md
2. Заменить первый code block на новую формулу
3. Сохранить через PUT /api/persona или напрямую через Path.write_text

---

## 8. Спецификация API для AIIM Editor

### GET /api/aiim/formula
Возвращает текущее состояние AIIM формулы как структурированный JSON.

**Response:**
```json
{
  "aspects": {
    "wi": {"code":"wi","plan":"P","level":4,"mode":"Ac-Or","weight":0.65},
    "lo": {"code":"lo","plan":"S","level":4,"mode":"Ac-Or","weight":0.70},
    ...
  },
  "locked": ["se", "co"],
  "base_weights": {"wi":0.65,"lo":0.70,...},
  "formula_raw": "wi(P 4 Ac-Or)Δ0.65;  lo(S 4 Ac-Or)Δ0.70; ...",
  "source_path": "Agent-Adam-Chip/About/Identity.md"
}
```

**Логика:**
- Читает Identity.md через `parse_aiim_formula()`
- base_weights берёт из `tuning.identity.base_weights` (для сравнения с текущим drift)
- Возвращает обе версии (formula = источник истины, base_weights = tuning дефолт)

---

### PUT /api/aiim/formula
Принимает изменённые параметры и перезаписывает формулу в Identity.md.

**Request body:**
```json
{
  "aspects": {
    "wi": {"plan":"P","level":4,"mode":"Ac-Or","weight":0.70},
    "lo": {"plan":"S","level":4,"mode":"Ac-Or","weight":0.75}
  },
  "sync_base_weights": true
}
```

**Валидация:**
- Нельзя изменить `se`, `co` (LOCKED)
- plan: одна из {B, S, P, I, T}
- level: 1–4
- mode: одна из {Ac-Or, Ac-Ch, Pa-Or, Pa-Ch}
- weight: 0.0–1.0

**Логика:**
1. Прочитать текущий Identity.md
2. Спарсить formula через `parse_aiim_formula()`
3. Применить изменения (не затрагивая LOCKED)
4. Регенерировать code block и вставить обратно в текст файла (regex replace первого ``` блока)
5. Записать через `(PROJECT_ROOT / path).write_text()`
6. Если `sync_base_weights=true` → патчнуть `tuning.identity.base_weights` через TuningStore
7. Эмитировать event `aiim_formula_updated`

**Response:**
```json
{
  "ok": true,
  "updated_aspects": ["wi", "lo"],
  "formula_raw": "...",
  "synced_base_weights": true
}
```

---

### GET /api/aiim/drift
Возвращает текущее состояние cross-session drift.

**Response:**
```json
{
  "aspect_drift": {"lo": 0.012, "em": 0.005, "me": 0.008},
  "session_counts": {"deep_contact": 3, "witnessed": 7, "void": 2},
  "total_sessions": 12,
  "created_at": "2026-01-01T00:00:00+00:00",
  "last_updated": "2026-06-10T12:00:00+00:00",
  "effective_weights": {
    "wi": 0.65,
    "lo": 0.712,
    "em": 0.605,
    "me": 0.308,
    ...
  },
  "ceilings": {"lo":0.85,"em":0.75,"sp":0.95,"ho":0.75,"wi":0.75,"me":0.60,"at":0.80}
}
```

**Логика:**
- Читает `data/adam/identity/drift.json` через `DriftAccumulator.load()`
- Вычисляет effective_weights = base_weights + aspect_drift (через `apply_to_vector`)
- Ceilings из `tuning.identity.ceilings.as_dict()`

---

### POST /api/aiim/drift/reset
Сбрасывает накопленный drift (опасная операция, требует явного confirm).

**Request:**
```json
{ "confirm": true }
```

**Логика:**
- Записывает свежий DriftRecord с пустым aspect_drift через `DriftAccumulator.save()`
- Эмитирует event `aiim_drift_reset`

---

### GET /api/aiim/session
Возвращает текущее runtime-состояние AIIM для активной сессии.

**Response (когда сессия активна):**
```json
{
  "active": true,
  "emotion": "curious",
  "emotion_src": "",
  "turn": 5,
  "vector": {
    "wi": 0.65, "lo": 0.78, "im": 0.65, "ho": 0.60,
    "co": 0.88, "em": 0.65, "be": 0.65, "sp": 0.85,
    "se": 0.92, "pe": 0.70, "me": 0.35, "at": 0.72
  },
  "active_intentions": ["flora_symbiosis"],
  "emotion_history": ["curious", "warm", "curious", "unease", "curious"],
  "emotion_distribution": {"curious": 3, "warm": 1, "unease": 1}
}
```

**Response (нет активной сессии):**
```json
{ "active": false }
```

**Логика:** читает `runtime_state["aiim_state"]` из RuntimeDeps.

---

## 9. Реализация — что нужно добавить

### В `System/adam/api_runtime.py`:
1. Добавить импорты `DriftAccumulator, DriftRecord` из `adam.identity_drift`
2. Добавить импорты `parse_aiim_formula, IdentityVector` из `adam.identity`
3. Добавить `get_aiim_state` в `RuntimeDeps` (callable или прямой доступ к `runtime_state`)
4. Реализовать 4 endpoint-а в `build_router()`

### Вспомогательная функция для перезаписи формулы в Identity.md:
```python
def _rewrite_aiim_formula_in_md(content: str, new_formula: str) -> str:
    """Replace the first fenced code block with new_formula."""
    return _CODE_BLOCK_RE.sub(
        f"```\n{new_formula}\n```",
        content,
        count=1
    )
```
(импортировать `_CODE_BLOCK_RE` из `adam.identity` или дублировать)

### В `RuntimeDeps`:
```python
@dataclass
class RuntimeDeps:
    ...
    runtime_state: dict[str, Any]   # уже есть
    data_dir: Path                  # нужно добавить (сейчас берётся из settings)
```

### Где взять data_dir в api_runtime.py:
```python
data_dir = Path(deps.settings.section("agent")["data_dir"])
```

---

## 10. Edge cases для реализации

1. **Identity.md содержит ``` блок не первым** — парсер ищет только первый match `_CODE_BLOCK_RE`. Если редактор человек сдвинул формулу — нужна валидация.

2. **sync_base_weights** — tuning.identity.base_weights должны оставаться в sync с Identity.md. PUT formula должен предлагать синхронизацию.

3. **Активная сессия + PUT formula** — formula читается ОДИН РАЗ при старте сессии (Orchestrator.py строки 3276-3284). Изменение Identity.md не повлияет на текущую сессию, только на следующую. Нужно документировать в response: `"takes_effect": "next_session"`.

4. **LOCKED защита** — если редактор пытается изменить `se` или `co`, вернуть 400 с понятным сообщением про ядро личности.

5. **Drift ceiling валидация** — если новый weight > ceiling, это не ошибка (ceiling применяется к drift, не к base), но предупреждение полезно.

---

## 11. Порядок файлов в реализации

```
System/adam/identity.py          # parse_aiim_formula, IdentityVector — уже есть
System/adam/identity_drift.py    # DriftAccumulator, DriftRecord — уже есть
System/adam/api_runtime.py       # добавить 4-5 новых endpoint-ов
```

Никаких новых модулей не нужно — вся логика уже в `identity.py` и `identity_drift.py`.
