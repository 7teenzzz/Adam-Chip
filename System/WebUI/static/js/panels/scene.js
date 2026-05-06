export function mount(target) {
  target.innerHTML = `<div class="card"><div class="card-header"><span class="card-title">Сцена</span></div><div class="card-body muted">Скоро: PCA каналы + сцены моторики.</div></div>`;
  return () => {};
}
