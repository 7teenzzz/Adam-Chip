export function mount(target) {
  target.innerHTML = `<div class="card"><div class="card-header"><span class="card-title">Логи</span></div><div class="card-body muted">Скоро: SSE event tail с фильтром.</div></div>`;
  return () => {};
}
