# Memory Schema — спецификация памяти Адама

> Документ для разработчика. Описывает контракт episodic / semantic / Echoes gate. Не идёт в prompt.
>
> Связанные документы: `Action_Mapping.md`, план `~/.claude/plans/jiggly-gliding-lagoon.md`.

## Уровни памяти

| Слой | Где живёт | Срок жизни | Попадает в prompt |
|------|-----------|------------|-------------------|
| Working | RAM оркестратора (`dialogue_history`) | до конца сессии | да, всегда (last 8 turns) |
| Episodic | `{ADAM_DATA_DIR}/memory/episodes/YYYY-MM-DD.jsonl` | rolling 14 дней + pin | через retrieval по имени, max 1–2 |
| Semantic | `{ADAM_DATA_DIR}/memory/semantic.md` | растёт, обновляется ночью | да, всегда (если файл есть) |
| Echoes pool | `Agent Adam Chip/About/Echoes.md` (статика) | бессрочно | через gate, 0–1 фрагмент per turn |
| Chinese pool | `Agent Adam Chip/About/Chinese_lines.md` (статика) | бессрочно | через gate, более жёсткий cooldown |

## Episode schema

Один диалог посетителя = одна запись. Не каждый turn.

```json
{
  "id": "uuid-v4",
  "ts_start": "2026-05-05T18:32:14Z",
  "ts_end": "2026-05-05T18:35:21Z",
  "duration_s": 187,
  "session_id": "uuid-v4",
  "visitor": {
    "introduced_name": "Михаил",
    "estimated_count": 1,
    "recurring_signal": false
  },
  "themes": ["память", "Тесей"],
  "salience": 0.6,
  "tone_visitor": "curious",
  "adam_state": "Ac-Or",
  "highlights": [
    {"who": "visitor", "text": "...", "reason": "новая формулировка вопроса"},
    {"who": "adam",    "text": "...", "reason": "необычный ответ"}
  ],
  "echoes_used": ["echo_07"],
  "chinese_used": [],
  "scene_changes": ["interest", "warm"],
  "pinned": false,
  "consolidated": false
}
```

Поля:
- `tone_visitor` ∈ `[curious, hostile, sad, playful, neutral, confused]`
- `adam_state` — фиксируется AIIM-сигнатурой в момент закрытия сессии (например `Ac-Or`, `Pa-Ch`)
- `highlights` — отобранные оркестратором реплики; не весь diaglogue_history, только примечательные
- `pinned: true` — защита от декея (выставляется консолидатором или вручную через UI)
- `consolidated: true` — попало в semantic.md, можно удалять при следующем декее

## Salience formula

Rule-based, считается синхронно при закрытии сессии. Без LLM.

```
salience =
    0.30 * (introduced_name != null)
  + 0.20 * clamp(duration_s / 300, 0..1)
  + 0.15 * min(len(unique_themes), 5) / 5
  + 0.15 * (tone in [hostile, sad, playful])
  + 0.10 * (echoes_used != [] OR chinese_used != [])
  + 0.10 * has_new_question_pattern
```

`has_new_question_pattern` — простая эвристика: содержит ли transcript вопросительный знак с темой, не встречавшейся в last 20 эпизодах. Опциональный сигнал, можно отложить.

## Триггер записи

Записывать эпизод если:
- `salience >= TUNING.memory.episodic.salience_threshold` (default 0.4), **ИЛИ**
- `visitor.introduced_name != null`, **ИЛИ**
- `pinned == true`

Иначе — отбросить (большинство «привет — пока» уходят в /dev/null).

## Декей

Cron от systemd или вызов из consolidator:

```python
def decay(now: datetime, decay_days: int = 14):
    cutoff = now - timedelta(days=decay_days)
    for jsonl in episodes_dir.glob("*.jsonl"):
        for record in read_jsonl(jsonl):
            if record["pinned"]:
                continue
            if record["consolidated"] and record["ts_end"] < cutoff - timedelta(days=1):
                drop(record)
            elif record["ts_end"] < cutoff:
                drop(record)
        rewrite_jsonl_excluding_dropped(jsonl)
        if file_empty(jsonl):
            os.remove(jsonl)
```

Принципы:
- Записи в semantic стираются раньше (через 1 день после консолидации) — их информация уже сохранена
- Не-консолидированные но старше 14 дней — стираются как «забытое»
- Pinned — никогда не стираются автоматом

## Semantic schema

`semantic.md` — markdown с фиксированными секциями (для детерминированного merge):

```markdown
## Постоянные посетители
- **Михаил** (визиты: 2026-04-28, 2026-05-02). Темы: память, Тесей. Особо: спрашивал про сына.

## Цепляющие темы
- Парадокс Тесея — каждый 3-й посетитель формулирует по-разному. Адам обычно отвечает через `im` Ac-Ch.

## Опорные факты
- Куратор экспозиции — Анна.
- Группы школьников приходят в среду 14:00–15:00.
- Шум от вентиляции в зале 2 ломает VAD после 20:00.

## Нерешённые загадки
- Зрители часто спрашивают «ты помнишь меня?» — даже при первом визите. Адам пока отвечает уклончиво.
```

## Consolidator

**Где:** `Engineering/consolidator.py` (запускается systemd-таймером 03:00–05:00).

**Контракт:**

```python
def main():
    cfg = load_tuning()
    new_episodes = load_episodes(since=cfg.consolidator.last_run)
    if not new_episodes:
        return
    current_semantic = read_semantic()

    patch = call_llm(
        model=cfg.consolidator.model,    # qwen2.5:7b
        system=CONSOLIDATOR_PROMPT,       # "ты редактор журнала наблюдений, не персонаж"
        user=build_user_message(new_episodes, current_semantic),
        format="json",                     # Ollama JSON mode
    )

    if not validate_patch_schema(patch):
        log.error("consolidator: invalid patch", patch)
        return  # никаких изменений, semantic.md не трогаем

    apply_patch(semantic_md, patch)
    mark_episodes_consolidated([ep.id for ep in patch.consumed])
    decay(now())
    save_run_marker()
```

**Patch schema:**

```json
{
  "add": [
    {"section": "Постоянные посетители", "entry": "- **Имя** ..."}
  ],
  "update": [
    {"section": "Опорные факты", "match": "Куратор экспозиции", "new": "Куратор — Анна."}
  ],
  "deprecate": [
    {"section": "Нерешённые загадки", "match": "..."}
  ],
  "pin_episodes": ["episode_id_1", "episode_id_2"]
}
```

**Failure mode:** любой промах валидации → no-op + лог в `consolidator.log`. Утренний запуск Адама не блокируется.

## Echoes / Chinese gate

**Где:** `System/adam/echoes_gate.py`. Общий механизм для обоих пулов — параметризуется типом.

```python
class EchoGate:
    def __init__(self, pool_path: Path, used_log_path: Path, tuning: Tuning, mode: str):
        # mode: "echoes" | "chinese"
        ...

    def maybe_inject(self, transcript: str, mood: str, adam_state: str) -> Optional[Echo]:
        if self._global_cooldown_active(): return None
        candidates = self._match_topic(transcript)            # tag-based или embedding
        candidates = [c for c in candidates if mood not in c.mood_block]
        candidates = [c for c in candidates if not self._per_echo_cooldown_active(c.id)]
        if not candidates: return None
        candidates.sort(key=lambda c: c.match_score, reverse=True)
        top = candidates[0]
        if random.random() > top.weight: return None
        self._record_use(top.id)
        return top
```

**Возврат в prompt:**

```
[сейчас можешь упомянуть, если уместно: «длинный коридор с лампами через одну…»]
```

Один такой блок per turn максимум. Если оба пула выдали кандидата — приоритет у Echoes (китайский всё-таки реже).

## Recent episodic injection

```python
def query_recent_by_name(name: str, limit: int = 2) -> list[str]:
    episodes = scan_episodes_with_name(name)
    episodes.sort(key=lambda e: e.ts_end, reverse=True)
    return [
        f"{ep.ts_end.date()} — {summarize(ep.themes, ep.highlights)}"
        for ep in episodes[:limit]
    ]
```

Инжект:

```
[прошлые встречи: 2026-04-28 — спрашивал про Тесея; 2026-05-02 — рассказывал про сына]
```

Только если `name` извлечён из transcript (regex/NER на «меня зовут X», «я X»).

## API для оркестратора

Минимальный публичный интерфейс модуля памяти:

```python
class EpisodicMemory:
    def start_session(self) -> SessionAccumulator: ...
    def commit_session(self, acc: SessionAccumulator) -> Optional[Episode]: ...
    def query_by_name(self, name: str, limit: int = 2) -> list[Episode]: ...
    def read_semantic(self) -> str: ...

class SessionAccumulator:
    def add_turn(self, who: str, text: str, salient: bool = False) -> None: ...
    def note_theme(self, theme: str) -> None: ...
    def note_echo_used(self, echo_id: str) -> None: ...
    def note_scene_change(self, scene: str) -> None: ...
    def set_visitor_name(self, name: str) -> None: ...
    def set_tone(self, tone: str) -> None: ...
    def finalize(self, end_ts: datetime) -> Episode: ...
```

## Конец сессии

Несколько стратегий, выбирается через `Tuning.json → session.end_strategy`. См. план Phase B5 + open questions. Default — `combined` (silence > 60s ИЛИ face_lost > 15s).

## Структура файлов на диске

```
{ADAM_DATA_DIR}/memory/
  episodes/
    2026-05-05.jsonl        # одна строка на эпизод
    2026-05-06.jsonl
    ...
  semantic.md                # markdown с фиксированными секциями
  echoes_used.jsonl          # {"id": "echo_07", "ts": "...", "pool": "echoes"}
  chinese_used.jsonl         # отдельный файл для китайского пула
  consolidator.log           # текстовый лог
  consolidator_state.json    # last_run, last_patch_hash, errors_count
```

## Тестирование

Unit:
- `salience_score()` — известные входы → известные выходы
- `decay()` — синтетические эпизоды разного возраста → корректное удаление
- `EchoGate.maybe_inject()` — cooldown, mood_block, weight

E2E (см. Verification в плане):
- Static persona inject
- Episodic write end-to-end
- Consolidator dry-run
- Echoes gate cooldown под нагрузкой
- Recent injection после 2-х визитов
- Декей старого jsonl
