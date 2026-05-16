// Панель «Tuning» — runtime-параметры персоны/памяти/эхо/сессии.
// Читает /api/tuning, собирает форму по группам, патчит через PUT /api/tuning.

import { api } from "../api.js";

function el(tag, attrs, children = []) {
  const node = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v != null && v !== false) node.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null || c === false) return;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  });
  return node;
}

// Описание полей по группам. Источник истины — Config.json (секция `tuning`) + tuning.py.
// Если добавляешь параметр в pydantic — добавь сюда же, иначе он не появится в UI.
const SPEC = [
  {
    key: "memory.episodic", title: "Память · эпизоды", fields: [
      { k: "enabled",                    label: "Запись эпизодов",            type: "bool",  hint: "включить или отключить сохранение эпизодов" },
      { k: "salience_threshold",         label: "Порог значимости",           type: "float", min: 0, max: 1, step: 0.05, hint: "0–1 · минимальный балл для записи эпизода" },
      { k: "decay_days",                 label: "Дней до забывания",          type: "int",   min: 1, max: 365, hint: "через сколько дней эпизод удаляется" },
      { k: "duration_normalize_seconds", label: "Норматив длительности (с)",  type: "int",   min: 30, max: 3600, hint: "знаменатель нормализации длины сессии" },
      { k: "highlights_max_per_episode", label: "Макс. маркеров на эпизод",   type: "int",   min: 1, max: 50 },
    ],
  },
  {
    key: "memory.episodic.weights", title: "Веса формулы значимости", fields: [
      { k: "introduced_name", label: "Имя зрителя",           type: "float", min: 0, max: 1, step: 0.05 },
      { k: "duration",        label: "Длительность",           type: "float", min: 0, max: 1, step: 0.05 },
      { k: "themes",          label: "Темы",                   type: "float", min: 0, max: 1, step: 0.05 },
      { k: "tone",            label: "Тональность",            type: "float", min: 0, max: 1, step: 0.05 },
      { k: "echoes_used",     label: "Использованные эхо",     type: "float", min: 0, max: 1, step: 0.05 },
      { k: "new_question",    label: "Новый вопрос",           type: "float", min: 0, max: 1, step: 0.05 },
    ],
  },
  {
    key: "memory.semantic", title: "Семантическая память", fields: [
      { k: "enabled",   label: "Активна",       type: "bool" },
      { k: "max_chars", label: "Макс. символов", type: "int", min: 200, max: 20000, hint: "сколько символов резюме хранится в промте" },
    ],
  },
  {
    key: "memory.recent_injection", title: "Инъекция недавних эпизодов", fields: [
      { k: "enabled",      label: "Активна",            type: "bool" },
      { k: "limit",        label: "Лимит эпизодов",     type: "int",  min: 0, max: 10, hint: "сколько эпизодов добавлять в промт" },
      { k: "strategy",     label: "Стратегия отбора",   type: "enum", options: ["by_name", "by_theme", "by_name_or_theme"] },
      { k: "max_age_days", label: "Макс. возраст (дней)", type: "int", min: 1, max: 365 },
    ],
  },
  {
    key: "memory.consolidator", title: "Консолидатор (ночное обновление)", fields: [
      { k: "enabled",                  label: "Активен",                    type: "bool" },
      { k: "model",                    label: "Модель LLM",                  type: "string", hint: "модель для консолидации эпизодов" },
      { k: "window_start",             label: "Начало окна",                 type: "string", hint: "формат ЧЧ:ММ" },
      { k: "window_end",               label: "Конец окна",                  type: "string", hint: "формат ЧЧ:ММ" },
      { k: "max_episodes_per_run",     label: "Макс. эпизодов за прогон",   type: "int",    min: 1 },
      { k: "temperature",              label: "Температура",                  type: "float",  min: 0, max: 2, step: 0.05 },
      { k: "max_runtime_minutes",      label: "Макс. время работы (мин)",    type: "int",    min: 1, max: 240 },
      { k: "retry_on_invalid_patch",   label: "Повтор при ошибке патча",     type: "bool" },
    ],
  },
  {
    key: "echoes", title: "Эхо (обрывки воспоминаний)", fields: [
      { k: "enabled",                  label: "Активны",                     type: "bool" },
      { k: "global_cooldown_turns",    label: "Перерыв между эхо (ходов)",   type: "int",   min: 0, hint: "не чаще раза в N диалоговых ходов" },
      { k: "per_echo_cooldown_days",   label: "Перерыв для одного эхо (дней)", type: "int", min: 0, hint: "конкретное эхо не чаще раза в N дней" },
      { k: "match_threshold",          label: "Порог совпадения",            type: "float", min: 0, max: 1, step: 0.05 },
      { k: "weight_multiplier",        label: "Множитель весов",             type: "float", min: 0, max: 5, step: 0.1, hint: "общий множитель для всех весов эхо" },
      { k: "matcher_type",             label: "Метод сравнения",             type: "enum",  options: ["tag", "embedding"] },
    ],
  },
  {
    key: "chinese", title: "Китайские вкрапления", fields: [
      { k: "enabled",               label: "Активны",             type: "bool" },
      { k: "global_cooldown_turns", label: "Перерыв (ходов)",     type: "int",   min: 0 },
      { k: "match_threshold",       label: "Порог совпадения",    type: "float", min: 0, max: 1, step: 0.05 },
      { k: "weight_multiplier",     label: "Множитель весов",     type: "float", min: 0, max: 5, step: 0.1 },
      { k: "audio_mode",            label: "Режим аудио",         type: "enum",  options: ["prerendered_only", "prerendered_with_text_fallback", "text_only"] },
    ],
  },
  {
    key: "session", title: "Сессия", fields: [
      { k: "end_strategy",        label: "Стратегия завершения",         type: "enum", options: ["vad_silence", "face_lost", "combined", "idle_with_grace", "event_signal"] },
      { k: "vad_silence_seconds", label: "Тишина для завершения (с)",    type: "int",  min: 5, hint: "рекомендуется 15–30" },
      { k: "face_lost_seconds",   label: "Лицо потеряно — задержка (с)", type: "int",  min: 2 },
      { k: "grace_message",       label: "Прощальная фраза",             type: "string" },
    ],
  },
  {
    key: "scene_director", title: "Сцены моторики", fields: [
      { k: "enabled",                              label: "Активен",                     type: "bool" },
      { k: "sustain_seconds",                      label: "Время удержания сцены (с)",   type: "int", min: 1 },
      { k: "cooldown_between_changes_seconds",     label: "Пауза между сменами (с)",     type: "int", min: 0 },
      { k: "hysteresis_seconds",                   label: "Гистерезис (с)",              type: "int", min: 0 },
    ],
  },
  {
    key: "llm", title: "LLM (runtime)", fields: [
      { k: "temperature",           label: "Температура",            type: "float", min: 0, max: 2, step: 0.05, hint: "0.7 рекомендуется · выше = творчески" },
      { k: "max_tokens",            label: "Макс. токенов ответа",   type: "int",   min: 10, max: 2000, hint: "60–100 рекомендуется" },
      { k: "response_word_target",  label: "Целевая длина (слов)",   type: "int",   min: 5, max: 200, hint: "рекомендуется 15–30" },
    ],
  },
  {
    key: "voice", title: "Голос (TTS, runtime)", fields: [
      { k: "speaker",          label: "Диктор",        type: "string", hint: "aidar, baya, kseniya, xenia, eugene, random" },
      { k: "speed_multiplier", label: "Скорость речи", type: "float",  min: 0.5, max: 2, step: 0.05, hint: "1.0 = нормально" },
      { k: "volume",           label: "Громкость",     type: "float",  min: 0, max: 2, step: 0.05, hint: "1.0 = нормально" },
    ],
  },
  {
    key: "prompt", title: "Сборка промта", fields: [
      { k: "history_turns",    label: "Ходов истории",              type: "int",  min: 0, max: 50, hint: "2–4 рекомендуется · меньше = быстрее" },
      { k: "include_scene",    label: "Включить описание сцены",    type: "bool", hint: "добавляет VLM-описание в промт" },
      { k: "include_sensors",  label: "Включить данные сенсоров",   type: "bool" },
    ],
  },
  {
    key: "diagnostics", title: "Диагностика", fields: [
      { k: "log_level",       label: "Уровень логирования",    type: "enum",  options: ["debug", "info", "warning", "error"] },
      { k: "metrics_enabled", label: "Сбор метрик",            type: "bool",  hint: "пишет inference_metrics.jsonl" },
      { k: "trace_prompts",   label: "Сохранять полный промт", type: "bool",  hint: "для панели Промты · потребляет память" },
    ],
  },
];

function getNested(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

function setNested(obj, path, value) {
  const keys = path.split(".");
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    if (cur[keys[i]] == null || typeof cur[keys[i]] !== "object") cur[keys[i]] = {};
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return obj;
}

function fieldNode(group, field, current, dirtyState) {
  const path = `${group.key}.${field.k}`;
  const value = getNested(current, path);
  const id = `t_${path.replace(/\./g, "_")}`;
  let inputNode;
  if (field.type === "bool") {
    inputNode = el("input", { type: "checkbox", id, ...(value ? { checked: "checked" } : {}) });
  } else if (field.type === "enum") {
    inputNode = el("select", { id, class: "input mono" },
      (field.options || []).map((opt) => {
        const o = el("option", { value: opt }, opt);
        if (opt === value) o.setAttribute("selected", "selected");
        return o;
      })
    );
  } else if (field.type === "int" || field.type === "float") {
    const attrs = { id, type: "number", class: "input mono", value: value ?? "" };
    if (field.min != null) attrs.min = field.min;
    if (field.max != null) attrs.max = field.max;
    if (field.step != null) attrs.step = field.step;
    else if (field.type === "int") attrs.step = 1;
    inputNode = el("input", attrs);
  } else {
    inputNode = el("input", { id, type: "text", class: "input mono", value: value ?? "" });
  }
  inputNode.addEventListener("change", () => {
    let v;
    if (field.type === "bool") v = inputNode.checked;
    else if (field.type === "int") v = parseInt(inputNode.value, 10);
    else if (field.type === "float") v = parseFloat(inputNode.value);
    else v = inputNode.value;
    if ((field.type === "int" || field.type === "float") && Number.isNaN(v)) return;
    setNested(dirtyState.patch, path, v);
    dirtyState.touched = true;
    dirtyState.update();
  });
  const displayLabel = field.label || field.k;
  const isWide = field.type === "string" || (field.type === "enum" && (field.options || []).length > 4);
  const label = el("label", {
    for: id,
    class: isWide ? "field-wide" : "",
    style: "display:flex; flex-direction:column; gap:4px; padding:2px 0",
  }, [
    el("div", { style: "display:flex; flex-direction:column; gap:2px" }, [
      el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, displayLabel),
      field.hint ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, field.hint) : null,
    ]),
    inputNode,
  ]);
  return label;
}

function groupCard(group, current, dirtyState) {
  const fields = group.fields.map((f) => fieldNode(group, f, current, dirtyState));
  return el("div", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, group.title)),
    el("div", { class: "card-body" }, [
      el("div", { class: "field-grid" }, fields),
    ]),
  ]);
}

export function mount(target) {
  const status = el("div", { class: "muted", style: "font-size:12px" }, "загрузка…");
  const applyBtn = el("button", { class: "btn", disabled: "disabled" }, "Применить");
  const resetBtn = el("button", { class: "btn btn-ghost" }, "Сбросить к defaults");
  const reloadBtn = el("button", { class: "btn btn-ghost" }, "Перечитать");
  const groupsRoot = el("div", { class: "col", style: "gap:12px" });

  const dirtyState = { patch: {}, touched: false, update: null };

  function setApplyState() {
    applyBtn.disabled = dirtyState.touched ? null : "disabled";
    applyBtn.textContent = dirtyState.touched ? "Применить (несохранённые изменения)" : "Применить";
  }
  dirtyState.update = setApplyState;

  async function load() {
    status.textContent = "загрузка…";
    try {
      const data = await api.get("/api/tuning");
      groupsRoot.innerHTML = "";
      dirtyState.patch = {};
      dirtyState.touched = false;
      const cardGrid = el("div", { class: "card-grid" });
      SPEC.forEach((group) => {
        const card = groupCard(group, data, dirtyState);
        if (group.key === "memory.consolidator") card.classList.add("card-full");
        cardGrid.appendChild(card);
      });
      groupsRoot.appendChild(cardGrid);
      status.textContent = "загружено";
      setApplyState();
    } catch (e) {
      status.textContent = "ошибка загрузки: " + e.message;
    }
  }

  applyBtn.addEventListener("click", async () => {
    if (!dirtyState.touched) return;
    status.textContent = "применяю…";
    try {
      await api.raw("/api/tuning", { method: "PUT", body: dirtyState.patch });
      status.textContent = "сохранено ✓";
      await load();
    } catch (e) {
      status.textContent = "ошибка: " + e.message;
    }
  });

  resetBtn.addEventListener("click", async () => {
    if (!confirm("Сбросить ВСЕ tuning-параметры к defaults?")) return;
    try {
      await api.post("/api/tuning/reset", {});
      status.textContent = "сброшено ✓";
      await load();
    } catch (e) {
      status.textContent = "ошибка: " + e.message;
    }
  });

  reloadBtn.addEventListener("click", () => load());

  target.appendChild(el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Runtime-параметры персоны"),
      ]),
      el("div", { class: "card-body", style: "display:flex; gap:12px; align-items:center; flex-wrap:wrap" }, [
        applyBtn, resetBtn, reloadBtn, status,
      ]),
    ]),
    groupsRoot,
  ]));

  load();
  return () => {};
}
