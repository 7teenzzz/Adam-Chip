// Minimal pub/sub store. Components subscribe to keys and re-render on change.

const store = new Map();
const subs = new Map();

export const state = {
  get(key, fallback) {
    return store.has(key) ? store.get(key) : fallback;
  },
  set(key, value) {
    const prev = store.get(key);
    if (prev === value) return;
    store.set(key, value);
    const list = subs.get(key);
    if (list) list.forEach((fn) => { try { fn(value, prev); } catch (e) { console.error(e); } });
  },
  patch(key, partial) {
    const cur = store.get(key) || {};
    const next = { ...cur, ...partial };
    store.set(key, next);
    const list = subs.get(key);
    if (list) list.forEach((fn) => { try { fn(next, cur); } catch (e) { console.error(e); } });
  },
  subscribe(key, fn) {
    if (!subs.has(key)) subs.set(key, new Set());
    subs.get(key).add(fn);
    return () => subs.get(key).delete(fn);
  },
};
