// Hash-based router. Maps #/route → dynamic import of panels/<route>.js.

const ROUTES = {
  chat:     { file: "chat",     label: "Чат" },
  settings: { file: "settings", label: "Конфигурация" },
  models:   { file: "models",   label: "Модели" },
  tuning:   { file: "tuning",   label: "Тюнинг" },
  services: { file: "services", label: "Сервисы" },
  persona:  { file: "persona",  label: "Личность агента" },
  metrics:  { file: "metrics",  label: "Метрики" },
  prompts:  { file: "prompts",  label: "Промты" },
  subsystem: { file: "subsystem", label: "Подсистема" },
  // backward-compat aliases (not in nav)
  voice:    { file: "voice",    label: "Голос" },
  camera:   { file: "camera",   label: "Камера" },
  scene:    { file: "scene",    label: "Сцена" },
  logs:     { file: "logs",     label: "Логи" },
  prompts:  { file: "prompts",  label: "Промты" },
};
const DEFAULT_ROUTE = "chat";

let currentRoute = null;
let currentTeardown = null;
let mountTarget = null;

function parseHash() {
  const hash = window.location.hash.replace(/^#\/?/, "").split(/[/?]/)[0];
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
