let stack = null;

function ensureStack() {
  if (stack) return stack;
  stack = document.createElement("div");
  stack.className = "toast-stack";
  document.body.appendChild(stack);
  return stack;
}

export function toast(message, kind = "ok", ttl = 3000) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  ensureStack().appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 200ms ease";
    setTimeout(() => el.remove(), 220);
  }, ttl);
}
