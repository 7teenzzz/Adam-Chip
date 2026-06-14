// Hash-based router. Maps #/route → dynamic import of panels/<route>.js.
// Nested routes use "/" delimiter: "agent/persona" → panels/agent/persona.js

const ROUTES = {
  // Top-level direct routes
  chat:     { file: "chat",     label: "Чат" },
  flora:    { file: "flora",    label: "Технофлора" },

  // Настройки → Агент sub-routes (Wave 1 — new nested structure)
  "agent/persona":        { file: "agent/persona",          label: "Личность" },
  "agent/instructions":   { file: "agent/instructions",     label: "Инструкции" },
  "agent/memory":         { file: "agent/memory",           label: "Память" },

  // Система sub-routes (Wave 1 — new nested structure)
  "system/audio":         { file: "system/audioAndVideo",   label: "Аудио и видео" },
  "system/services":      { file: "system/servicesModels",  label: "Сервисы и модели" },
  "system/esp32":         { file: "system/esp32",           label: "Подсистема ESP32" },

  // Диагностика sub-routes (Wave 1 — new nested structure)
  "diagnostics/metrics":  { file: "diagnostics/metricsLogs",  label: "Метрики и логи" },
  "diagnostics/system":   { file: "diagnostics/systemHealth", label: "Система" },
  "diagnostics/esp32":    { file: "diagnostics/esp32Health",  label: "Подсистема" },

  // Legacy flat routes — kept as fallback until Wave 4 migration (plan 42-08)
  settings:  { file: "settings",   label: "Конфигурация" },
  audioInput: { file: "audioInput", label: "Аудио-вход" },
  models:    { file: "models",     label: "Модели" },
  tuning:    { file: "tuning",     label: "Тюнинг" },
  services:  { file: "services",   label: "Сервисы" },
  persona:   { file: "persona",    label: "Личность агента" },
  metrics:   { file: "metrics",    label: "Метрики" },
  prompts:   { file: "prompts",    label: "Промты" },
  subsystem: { file: "subsystem",  label: "Подсистема" },
  // backward-compat aliases (not in nav)
  voice:     { file: "voice",      label: "Голос" },
  camera:    { file: "camera",     label: "Камера" },
  scene:     { file: "scene",      label: "Сцена" },
  logs:      { file: "logs",       label: "Логи" },
};
const DEFAULT_ROUTE = "chat";

let currentRoute = null;
let currentTeardown = null;
let mountTarget = null;

function parseHash() {
  // Strip "#/" prefix, then split only on "?" to remove query string.
  // This preserves nested keys like "agent/persona" intact.
  const hash = window.location.hash.replace(/^#\/?/, "").split("?")[0];
  return ROUTES[hash] ? hash : DEFAULT_ROUTE;
}

async function activate(route) {
  if (route === currentRoute) return;
  if (currentTeardown) { try { currentTeardown(); } catch (e) {} currentTeardown = null; }
  currentRoute = route;
  mountTarget.innerHTML = "";
  const cfg = ROUTES[route];
  try {
    const module = await import(`./panels/${cfg.file}.js`);
    if (typeof module.mount === "function") {
      const teardown = module.mount(mountTarget);
      if (typeof teardown === "function") currentTeardown = teardown;
    }
  } catch (err) {
    mountTarget.innerHTML = `<div class="card"><div class="card-body bad">Ошибка загрузки панели <code>${route}</code>: ${err.message}</div></div>`;
    console.error("panel mount error:", err);
  }
  document.querySelectorAll("[data-route]").forEach((el) => {
    el.classList.toggle("active", el.dataset.route === route);
  });
}

export const router = {
  init(target) {
    mountTarget = target;
    window.addEventListener("hashchange", () => activate(parseHash()));
    activate(parseHash());
  },
  routes: ROUTES,
  go(route) {
    window.location.hash = `#/${route}`;
  },
  current() { return currentRoute; },
};
