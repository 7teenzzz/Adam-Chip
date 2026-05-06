// Thin fetch + SSE wrapper. All paths are absolute API routes.

const BASE = "";

async function request(path, opts = {}) {
  const init = {
    method: opts.method || "GET",
    headers: opts.headers ? { ...opts.headers } : {},
  };
  if (opts.body !== undefined) {
    if (opts.body instanceof Blob || opts.body instanceof ArrayBuffer || opts.body instanceof Uint8Array) {
      init.body = opts.body;
    } else {
      init.body = JSON.stringify(opts.body);
      init.headers["Content-Type"] = "application/json";
    }
  }
  const res = await fetch(BASE + path, init);
  const ct = res.headers.get("content-type") || "";
  let data = null;
  if (ct.includes("application/json")) {
    data = await res.json().catch(() => null);
  } else if (ct.startsWith("image/") || ct.startsWith("audio/") || ct === "application/octet-stream") {
    data = await res.blob();
  } else {
    data = await res.text();
  }
  if (!res.ok) {
    const detail = data && typeof data === "object" && data.detail ? data.detail : data;
    const err = new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
    err.status = res.status;
    err.body = data;
    throw err;
  }
  return data;
}

export const api = {
  get:    (path) => request(path),
  post:   (path, body) => request(path, { method: "POST", body }),
  patch:  (path, body) => request(path, { method: "PATCH", body }),
  del:    (path) => request(path, { method: "DELETE" }),
  raw:    request,
};

// SSE subscription with automatic reconnect on network errors.
export function subscribeEvents(onEvent, onError) {
  let source = null;
  let closed = false;
  let backoff = 500;

  function open() {
    if (closed) return;
    source = new EventSource("/api/agent/stream");
    source.onopen = () => { backoff = 500; };
    source.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data);
        onEvent(event);
      } catch (e) {
        // ignore malformed
      }
    };
    source.addEventListener("error", () => {
      if (closed) return;
      try { source.close(); } catch (_) {}
      if (onError) onError();
      setTimeout(open, backoff);
      backoff = Math.min(backoff * 2, 8000);
    });
  }

  open();
  return () => {
    closed = true;
    if (source) try { source.close(); } catch (_) {}
  };
}
