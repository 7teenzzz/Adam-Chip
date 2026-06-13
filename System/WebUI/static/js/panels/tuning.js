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

// Описание полей по группам. Источник истины — iAdam.json + tuning.py.
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
      { k: "volume",           label: "Громкость",     type: "float",  min: 0, max: 2, step: 0.05, hint: "0.0 = тишина · 1.0 = норма · 2.0 = максимум · удобнее регулировать слайдером в «Конфигурация → Голос (runtime)»" },
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
  // ── AIIM Identity ─────────────────────────────────────────────────────────
  {
    key: "identity", title: "Идентичность (AIIM)", fields: [
      { k: "enabled",                        label: "Активна",                          type: "bool",  hint: "включить динамическое AIIM-состояние" },
      { k: "default_emotion",                label: "Базовая эмоция",                   type: "enum",  options: ["curious", "warm", "unease", "sharp", "calm"] },
      { k: "decay_target_emotion",           label: "Эмоция после тишины",              type: "enum",  options: ["curious", "warm", "unease", "sharp", "calm"] },
      { k: "decay_silence_threshold_seconds",label: "Тишина до возврата (с)",           type: "int",   min: 5, hint: "секунд без реплики зрителя → эмоция возвращается к базовой" },
      { k: "include_in_prompt",              label: "Включить в промт",                 type: "bool",  hint: "добавляет AIIM-контекст в системный промт" },
      { k: "max_intentions_in_ctx",          label: "Макс. интенций в контексте",       type: "int",   min: 0, max: 5 },
      { k: "aspect_change_threshold",        label: "Порог изменения аспекта",          type: "float", min: 0, max: 0.3, step: 0.01, hint: "минимальный сдвиг веса для записи в контекст" },
    ],
  },
];
// identity.base_weights rendered by makeAiimWeightsCard (see below), not via SPEC

// ── AIIM matrix metadata (A-2, mirrors Identity.md current formula) ──────────

const AIIM_ASPECTS = [
  { code: "wi", name: "воля",          plan: "P", level: 4, ac: "Ac", or: "Or", desc: "хочу, выбираю, направляю" },
  { code: "lo", name: "эмпатия",       plan: "S", level: 4, ac: "Ac", or: "Or", desc: "замечаю чужое состояние, хочу понять" },
  { code: "im", name: "идеи",          plan: "P", level: 3, ac: "Ac", or: "Ch", desc: "связываю несвязанное, шучу" },
  { code: "ho", name: "этика",         plan: "I", level: 3, ac: "Pa", or: "Or", desc: "держу границы" },
  { code: "co", name: "логика",        plan: "T", level: 4, ac: "Ac", or: "Or", desc: "анализирую, удерживаю дистанцию" },
  { code: "em", name: "эмоция",        plan: "B", level: 3, ac: "Ac", or: "Ch", desc: "окрашиваю восприятие, проявляюсь" },
  { code: "be", name: "действие",      plan: "S", level: 3, ac: "Ac", or: "Or", desc: "отвечаю, технофлора двигается" },
  { code: "sp", name: "смысл",         plan: "T", level: 4, ac: "Pa", or: "Or", desc: "вижу масштаб" },
  { code: "se", name: "самоосознание", plan: "I", level: 4, ac: "Ac", or: "Ch", desc: "наблюдаю за тем, чем становлюсь" },
  { code: "pe", name: "восприятие",    plan: "T", level: 3, ac: "Ac", or: "Or", desc: "чувствую через технофлору" },
  { code: "me", name: "память",        plan: "B", level: 2, ac: "Pa", or: "Ch", desc: "повреждена, восстанавливается обрывками" },
  { code: "at", name: "внимание",      plan: "S", level: 4, ac: "Ac", or: "Or", desc: "слушаю до конца, не игнорирую" },
];

const PLAN_META = {
  P: { label: "я сам",   color: "var(--accent)",      bg: "rgba(67,209,122,0.12)",  border: "rgba(67,209,122,0.3)" },
  S: { label: "другие",  color: "var(--cyan)",         bg: "rgba(100,200,255,0.1)", border: "rgba(100,200,255,0.25)" },
  I: { label: "связки",  color: "var(--warn)",         bg: "rgba(240,184,74,0.12)", border: "rgba(240,184,74,0.3)" },
  B: { label: "тело",    color: "#c084fc",              bg: "rgba(192,132,252,0.1)", border: "rgba(192,132,252,0.25)" },
  T: { label: "трансц.", color: "var(--text)",          bg: "rgba(242,242,245,0.06)", border: "rgba(242,242,245,0.15)" },
};

const LEVEL_LABELS = ["", "зачаточный", "стабильный", "сложный", "мастерский"];

function weightColor(v) {
  if (v >= 0.8) return "var(--accent-glow)";
  if (v >= 0.5) return "var(--accent)";
  if (v >= 0.3) return "var(--muted)";
  return "var(--dim)";
}

function makeAiimWeightsCard(data, dirtyState) {
  const weights = (data.identity ?? {}).base_weights ?? {};

  // Header row
  const headerRow = el("div", {
    style: "display:grid; grid-template-columns:2.4em minmax(110px,1fr) 5.6em 3.4em 5.2em 1fr 3em; gap:6px 10px; padding:0 0 8px; border-bottom:1px solid var(--line-strong); margin-bottom:4px",
  }, [
    el("span", { style: "font-size:10px; color:var(--dim)" }, "код"),
    el("span", { style: "font-size:10px; color:var(--dim)" }, "аспект"),
    el("span", { style: "font-size:10px; color:var(--dim)" }, "план"),
    el("span", { style: "font-size:10px; color:var(--dim)" }, "уровень"),
    el("span", { style: "font-size:10px; color:var(--dim)" }, "режим"),
    el("span", { style: "font-size:10px; color:var(--dim)" }, "вес Δ"),
    el("span", { style: "font-size:10px; color:var(--dim); text-align:right" }, "Δ"),
  ]);

  const rows = AIIM_ASPECTS.map((asp) => {
    const initVal = weights[asp.code] ?? 0;
    const fmt = (v) => Number(v).toFixed(2);

    const color = el("span", {}); // will be set by updateColor
    const valueLabel = el("span", {
      class: "mono",
      style: `min-width:3em; text-align:right; font-size:12px; font-weight:700; color:${weightColor(initVal)}`,
    }, fmt(initVal));

    const slider = el("input", {
      type: "range", class: "input",
      style: "flex:1; cursor:pointer; padding:0",
      min: 0, max: 1, step: 0.05, value: initVal,
    });
    slider.addEventListener("input", () => {
      const v = parseFloat(slider.value);
      valueLabel.textContent = fmt(v);
      valueLabel.style.color = weightColor(v);
      if (!Number.isNaN(v)) {
        setNested(dirtyState.patch, `identity.base_weights.${asp.code}`, v);
        dirtyState.touched = true;
        dirtyState.update();
      }
    });

    // Plan badge
    const pm = PLAN_META[asp.plan] ?? PLAN_META.T;
    const planBadge = el("span", {
      title: `план: ${pm.label}`,
      style: `display:inline-flex; align-items:center; gap:4px; font-size:10px; padding:2px 6px; border-radius:4px; background:${pm.bg}; color:${pm.color}; border:1px solid ${pm.border}; white-space:nowrap; cursor:default`,
    }, [
      el("span", { class: "mono", style: "font-weight:700; font-size:11px" }, asp.plan),
      el("span", {}, pm.label),
    ]);

    // Level: 4 dots
    const levelDots = el("span", {
      title: `уровень ${asp.level} — ${LEVEL_LABELS[asp.level]}`,
      style: "display:flex; gap:3px; align-items:center; cursor:default",
    },
      Array.from({ length: 4 }, (_, i) => el("span", {
        style: `width:8px; height:8px; border-radius:50%; background:${i < asp.level ? "var(--accent)" : "var(--bg-3)"}; border:1px solid ${i < asp.level ? "var(--accent-deep)" : "var(--line)"}`,
      }))
    );

    // Mode: Ac/Pa + Or/Ch
    const modeAc = el("span", {
      title: asp.ac === "Ac" ? "активный — выходит наружу" : "пассивный — фоновой",
      style: `font-size:10px; padding:1px 5px; border-radius:3px; font-weight:600; cursor:default; background:${asp.ac === "Ac" ? "rgba(67,209,122,0.12)" : "var(--bg-3)"}; color:${asp.ac === "Ac" ? "var(--accent)" : "var(--dim)"}; border:1px solid ${asp.ac === "Ac" ? "rgba(67,209,122,0.3)" : "var(--line)"}`,
    }, asp.ac);
    const modeOr = el("span", {
      title: asp.or === "Or" ? "упорядоченный — по структуре" : "хаотичный — вспышками",
      style: `font-size:10px; padding:1px 5px; border-radius:3px; font-weight:600; cursor:default; background:${asp.or === "Or" ? "rgba(100,200,255,0.10)" : "rgba(192,132,252,0.1)"}; color:${asp.or === "Or" ? "var(--cyan)" : "#c084fc"}; border:1px solid ${asp.or === "Or" ? "rgba(100,200,255,0.25)" : "rgba(192,132,252,0.25)"}`,
    }, asp.or);

    const isCore = initVal >= 0.8;
    return el("div", {
      style: `display:grid; grid-template-columns:2.4em minmax(110px,1fr) 5.6em 3.4em 5.2em 1fr 3em; gap:6px 10px; align-items:center; padding:8px 0; border-bottom:1px solid var(--line); ${isCore ? "background:rgba(67,209,122,0.025);" : ""}`,
    }, [
      el("span", {
        class: "mono",
        style: "font-size:13px; font-weight:700; color:var(--accent)",
      }, asp.code),
      el("div", { style: "display:flex; flex-direction:column; gap:1px; min-width:0" }, [
        el("span", { style: "font-size:12px; font-weight:600; color:var(--text); white-space:nowrap; overflow:hidden; text-overflow:ellipsis" }, asp.name),
        el("span", { style: "font-size:10px; color:var(--dim); line-height:1.3; overflow:hidden; text-overflow:ellipsis; white-space:nowrap", title: asp.desc }, asp.desc),
      ]),
      planBadge,
      levelDots,
      el("div", { style: "display:flex; gap:3px" }, [modeAc, modeOr]),
      slider,
      valueLabel,
    ]);
  });

  // Legend
  const legend = el("div", {
    style: "display:flex; gap:12px 20px; flex-wrap:wrap; padding:10px 0 2px; margin-top:4px; border-top:1px solid var(--line)",
  }, [
    el("span", { style: "color:var(--dim); font-size:10px" }, "Δ: <0.3 едва заметен · 0.3–0.5 вспомогательный · 0.5–0.8 рабочий · ≥0.8 ядро"),
    el("span", { style: "color:var(--dim); font-size:10px" }, "●●●● — уровень (зачаточный→мастерский)"),
    el("span", { style: "color:var(--dim); font-size:10px" }, "Ac активный · Pa пассивный · Or упорядоченный · Ch хаотичный"),
  ]);

  return el("div", { class: "card", style: "margin-top:0" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Веса аспектов AIIM"),
      el("span", { style: "font-size:11px; color:var(--dim)" }, "A-2 · Identity.md"),
    ]),
    el("div", { class: "card-body" }, [headerRow, ...rows, legend]),
  ]);
}

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
  let valueDisplay = null;

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
  } else if (field.type === "range") {
    const fmt = (v) => Number(v).toFixed(2);
    valueDisplay = el("span", {
      class: "mono",
      style: "min-width:38px; text-align:right; color:var(--accent); font-size:12px; font-weight:600",
    }, fmt(value ?? field.min ?? 0));
    inputNode = el("input", {
      id, type: "range", class: "input",
      style: "flex:1; min-width:120px; cursor:pointer",
      min: field.min ?? 0, max: field.max ?? 1, step: field.step ?? 0.05,
      value: value ?? field.min ?? 0,
    });
    inputNode.addEventListener("input", () => {
      valueDisplay.textContent = fmt(inputNode.value);
      const v = parseFloat(inputNode.value);
      if (!Number.isNaN(v)) {
        setNested(dirtyState.patch, path, v);
        dirtyState.touched = true;
        dirtyState.update();
      }
    });
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

  if (field.type !== "range") {
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
  }

  const displayLabel = field.label || field.k;
  const isWide = field.type === "string" || (field.type === "enum" && (field.options || []).length > 4);
  const inputContent = valueDisplay
    ? el("div", { style: "display:flex; align-items:center; gap:8px; padding:4px 0" }, [inputNode, valueDisplay])
    : inputNode;

  const label = el("label", {
    for: id,
    class: isWide ? "field-wide" : "",
    style: "display:flex; flex-direction:column; gap:4px; padding:2px 0",
  }, [
    el("div", { style: "display:flex; flex-direction:column; gap:2px" }, [
      el("span", { style: "color:var(--text); font-size:12px; font-weight:500" }, displayLabel),
      field.hint ? el("span", { style: "color:var(--muted); font-size:10px; line-height:1.3" }, field.hint) : null,
    ]),
    inputContent,
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

// ── Live emotion state card ───────────────────────────────────────────────────

const EMOTION_LABELS = {
  curious: "любопытство",
  warm: "тепло",
  unease: "тревога",
  sharp: "острота",
  calm: "спокойствие",
};

const EMOTION_COLORS = {
  curious: "var(--accent)",
  warm: "var(--warn)",
  unease: "var(--bad)",
  sharp: "var(--cyan)",
  calm: "var(--muted)",
};

function makeEmotionCard() {
  const emotionBadge = el("span", {
    class: "mono",
    style: "font-size:18px; font-weight:700; padding:4px 14px; border-radius:var(--radius-s); background:var(--bg-3); color:var(--muted)",
  }, "—");
  const codeLabel = el("span", { class: "mono", style: "color:var(--dim); font-size:11px" }, "");
  const refreshBtn = el("button", { class: "btn btn-ghost", style: "font-size:11px; padding:4px 10px" }, "обновить");

  async function fetchEmotion() {
    try {
      const data = await api.get("/api/agent/status");
      const em = data.current_emotion ?? null;
      if (em) {
        const label = EMOTION_LABELS[em] ?? em;
        const color = EMOTION_COLORS[em] ?? "var(--text)";
        emotionBadge.textContent = label;
        emotionBadge.style.color = color;
        codeLabel.textContent = `(${em})`;
      } else {
        emotionBadge.textContent = "нет данных";
        emotionBadge.style.color = "var(--dim)";
        codeLabel.textContent = "";
      }
    } catch {
      emotionBadge.textContent = "нет данных";
      emotionBadge.style.color = "var(--dim)";
      codeLabel.textContent = "";
    }
  }

  refreshBtn.addEventListener("click", fetchEmotion);
  fetchEmotion();

  return el("div", { class: "card" }, [
    el("div", { class: "card-header" }, el("span", { class: "card-title" }, "Текущая эмоция Адама")),
    el("div", { class: "card-body", style: "display:flex; align-items:center; gap:14px; flex-wrap:wrap" }, [
      emotionBadge,
      codeLabel,
      refreshBtn,
    ]),
  ]);
}

// ── Personality preset selector ───────────────────────────────────────────────

function makePresetCard() {
  let selectedPreset = null;
  let activePreset = null;
  let presets = {};

  const radioGroup = el("div", { class: "col", style: "gap:6px" });
  const activeLabel = el("span", { class: "muted", style: "font-size:12px" }, "загрузка…");
  const applyPresetBtn = el("button", { class: "btn", disabled: "disabled" }, "Применить");
  const presetStatus = el("span", { class: "muted", style: "font-size:12px" }, "");

  function renderRadios() {
    radioGroup.innerHTML = "";
    const names = Object.keys(presets);
    if (names.length === 0) {
      radioGroup.appendChild(el("span", { class: "muted", style: "font-size:13px" }, "Пресеты не настроены"));
      applyPresetBtn.style.display = "none";
      return;
    }
    applyPresetBtn.style.display = "";
    const current = selectedPreset ?? activePreset;
    names.forEach((name) => {
      const preset = presets[name];
      const isActive = name === activePreset;
      const radio = el("input", {
        type: "radio",
        name: "personality_preset",
        value: name,
        id: `preset_${name}`,
        ...(name === current ? { checked: "checked" } : {}),
      });
      radio.addEventListener("change", () => {
        selectedPreset = name;
        applyPresetBtn.disabled = name === activePreset ? "disabled" : null;
      });
      radioGroup.appendChild(el("label", {
        for: `preset_${name}`,
        style: "display:flex; align-items:baseline; gap:8px; cursor:pointer; padding:5px 0",
      }, [
        radio,
        el("span", { style: "color:var(--text); font-size:13px; font-weight:500" }, name),
        el("span", { class: "muted", style: "font-size:12px" }, `— ${preset.description ?? ""}`),
        isActive ? el("span", { style: "color:var(--accent); font-size:11px; margin-left:4px" }, "(активен)") : null,
      ]));
    });
    applyPresetBtn.disabled = (!selectedPreset || selectedPreset === activePreset) ? "disabled" : null;
  }

  async function loadPresets() {
    try {
      const data = await api.get("/api/tuning");
      presets = data.personality_presets ?? {};
      activePreset = data.active_preset ?? null;
      selectedPreset = activePreset;
      activeLabel.textContent = activePreset ? `Активен: ${activePreset}` : "Активен: —";
      renderRadios();
    } catch (e) {
      radioGroup.innerHTML = "";
      radioGroup.appendChild(el("span", { class: "bad", style: "font-size:12px" }, "ошибка загрузки пресетов"));
    }
  }

  applyPresetBtn.addEventListener("click", async () => {
    if (!selectedPreset || selectedPreset === activePreset) return;
    presetStatus.textContent = "применяю…";
    try {
      await api.post(`/api/tuning/preset/${selectedPreset}`, {});
      presetStatus.textContent = "применено ✓";
      activePreset = selectedPreset;
      activeLabel.textContent = `Активен: ${activePreset}`;
      renderRadios();
    } catch (e) {
      presetStatus.textContent = "ошибка: " + e.message;
    }
  });

  loadPresets();

  return el("div", { class: "card card-full" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, "Режим личности"),
      el("div", { style: "display:flex; gap:8px; align-items:center" }, [applyPresetBtn, presetStatus]),
    ]),
    el("div", { class: "card-body col", style: "gap:6px" }, [
      radioGroup,
      el("div", { style: "margin-top:4px" }, [activeLabel]),
    ]),
  ]);
}

export function mount(target) {
  const status = el("div", { class: "muted", style: "font-size:12px" }, "загрузка…");
  const applyBtn = el("button", { class: "btn", disabled: "disabled" }, "Применить");
  const resetBtn = el("button", { class: "btn btn-ghost" }, "Сбросить к defaults");
  const reloadBtn = el("button", { class: "btn btn-ghost" }, "Перечитать");
  const groupsRoot = el("div", { class: "col", style: "gap:12px" });
  const presetCard = makePresetCard();
  const emotionCard = makeEmotionCard();

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
      groupsRoot.appendChild(makeAiimWeightsCard(data, dirtyState));
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
    presetCard,
    groupsRoot,
    emotionCard,
  ]));

  load();
  return () => {};
}
