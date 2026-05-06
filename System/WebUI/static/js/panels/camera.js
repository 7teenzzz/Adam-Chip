import { api } from "../api.js";
import { state } from "../state.js";
import { toast } from "../widgets/toast.js";

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

function placeholder(text, kind = "muted") {
  const colors = { muted: "var(--muted)", warn: "var(--warn)", bad: "var(--bad)" };
  return el("div", {
    style: `display:flex; align-items:center; justify-content:center; height:280px; background:var(--bg-2); border:1px dashed var(--line); border-radius:var(--radius-s); color:${colors[kind]}; font-family:var(--font-mono); font-size:13px; text-align:center; padding:24px`,
  }, text);
}

export function mount(target) {
  // ----- ESP card -----
  const espStatus = el("span", { class: "caps", id: "cam-esp-status", style: "color:var(--muted)" }, "проверка…");
  const espBody = el("div", { id: "cam-esp-body" });
  const espRefresh = el("button", { class: "btn btn-ghost", onclick: () => loadEsp(true) }, "Перепроверить");

  // ----- Jetson card (snapshot OR live VLM viewer) -----
  const jetStatus = el("span", { class: "caps", id: "cam-jet-status", style: "color:var(--muted)" }, "проверка…");
  const jetBody = el("div", { id: "cam-jet-body" });
  const jetRefresh = el("button", { class: "btn btn-ghost", onclick: () => loadJetson(true) }, "Перепроверить");
  const openLiveVlmBtn = el("a", {
    class: "btn btn-ghost", id: "cam-vlm-open", style: "display:none",
  }, "Открыть Live VLM →");

  // ----- Scene description from VLM -----
  const sceneText = el("div", { id: "cam-scene-text", style: "white-space:pre-wrap; line-height:1.5" }, "Сцена пока не описана.");
  const sceneMeta = el("span", { class: "caps mono", id: "cam-scene-meta", style: "color:var(--muted)" }, "—");

  target.appendChild(el("section", { class: "col" }, [
    el("div", { class: "grid-2", style: "gap:16px; align-items:start" }, [
      el("section", { class: "card" }, [
        el("div", { class: "card-header" }, [
          el("span", { class: "card-title" }, "ESP32 камера"),
          espStatus, espRefresh,
        ]),
        el("div", { class: "card-body" }, [espBody]),
      ]),
      el("section", { class: "card" }, [
        el("div", { class: "card-header" }, [
          el("span", { class: "card-title" }, "Jetson camera"),
          jetStatus, openLiveVlmBtn, jetRefresh,
        ]),
        el("div", { class: "card-body" }, [jetBody]),
      ]),
    ]),
    el("section", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Описание сцены (VLM)"),
        sceneMeta,
      ]),
      el("div", { class: "card-body" }, [sceneText]),
    ]),
  ]));

  // ===== ESP =================================================================
  async function loadEsp(force = false) {
    espStatus.textContent = "проверка…";
    espStatus.style.color = "var(--muted)";
    espBody.innerHTML = "";
    try {
      const status = await api.get("/api/ui/status");
      const espOk = !!status?.ok;
      const cam = status?.modules?.cam;
      const url = status?.esp?.camera_stream_url;
      const errors = status?.errors || {};

      if (!espOk || Object.keys(errors).length > 0) {
        const detail = Object.entries(errors).map(([k, v]) => `${k}: ${v.error || v.status}`).join("; ");
        espStatus.textContent = "ESP оффлайн";
        espStatus.style.color = "var(--bad)";
        espBody.appendChild(placeholder(`ESP не отвечает.\n${detail || "(connection refused / timeout)"}`, "bad"));
        return;
      }
      if (!cam) {
        espStatus.textContent = "камера не инициализирована";
        espStatus.style.color = "var(--warn)";
        espBody.appendChild(placeholder("ESP онлайн, но модуль камеры не готов.", "warn"));
        return;
      }
      if (!url) {
        espStatus.textContent = "нет URL стрима";
        espStatus.style.color = "var(--warn)";
        espBody.appendChild(placeholder("ESP онлайн, но camera_stream_url пуст.", "warn"));
        return;
      }
      const img = el("img", {
        alt: "ESP MJPEG",
        src: url + (url.includes("?") ? "&" : "?") + "_=" + Date.now(),
        style: "width:100%; max-height:60vh; object-fit:contain; background:var(--bg-2); border-radius:var(--radius-s); border:1px solid var(--line)",
      });
      img.addEventListener("load", () => {
        espStatus.textContent = "стрим активен";
        espStatus.style.color = "var(--accent)";
      });
      img.addEventListener("error", () => {
        espStatus.textContent = "ошибка стрима";
        espStatus.style.color = "var(--bad)";
        espBody.innerHTML = "";
        espBody.appendChild(placeholder("Не удалось загрузить MJPEG-кадр от ESP.", "bad"));
      });
      espStatus.textContent = "загрузка…";
      espStatus.style.color = "var(--muted)";
      espBody.appendChild(img);
    } catch (e) {
      espStatus.textContent = "ошибка";
      espStatus.style.color = "var(--bad)";
      espBody.appendChild(placeholder(`Ошибка проверки: ${e.message}`, "bad"));
      if (force) toast("ESP probe failed: " + e.message, "bad");
    }
  }

  // ===== Jetson camera (snapshot or Live VLM viewer) =========================
  let jetTimer = null;
  let jetInflight = false;

  function clearJetTimer() {
    if (jetTimer) { clearInterval(jetTimer); jetTimer = null; }
  }

  async function loadJetson(force = false) {
    clearJetTimer();
    jetStatus.textContent = "проверка…";
    jetStatus.style.color = "var(--muted)";
    jetBody.innerHTML = "";
    openLiveVlmBtn.style.display = "none";

    let vlm = null;
    try { vlm = await api.get("/api/live_vlm/status"); } catch (_) {}

    if (vlm?.running) {
      // Live VLM holds /dev/video0 exclusively; show viewer link instead of snapshot.
      const host = window.location.hostname || "127.0.0.1";
      const viewerUrl = `https://${host}:8050/`;
      openLiveVlmBtn.href = viewerUrl;
      openLiveVlmBtn.target = "_blank";
      openLiveVlmBtn.rel = "noopener";
      openLiveVlmBtn.style.display = "";
      jetStatus.textContent = "Live VLM активна";
      jetStatus.style.color = "var(--accent)";
      jetBody.appendChild(placeholder(
        `Камера занята контейнером adam-live-vlm.\nСтрим с подписями: ${viewerUrl}\n(self-signed cert — браузер попросит подтвердить)`,
        "warn",
      ));
      return;
    }

    // VLM не запущен — пробуем snapshot.
    refreshSnapshot(force);
    jetTimer = setInterval(refreshSnapshot, 1500);
  }

  function refreshSnapshot(force = false) {
    if (jetInflight) return;
    jetInflight = true;
    const url = "/api/camera/snapshot.jpg?_=" + Date.now();
    const probe = new Image();
    probe.onload = () => {
      jetBody.innerHTML = "";
      const img = el("img", {
        alt: "Jetson v4l2 snapshot",
        src: probe.src,
        style: "width:100%; max-height:60vh; object-fit:contain; background:var(--bg-2); border-radius:var(--radius-s); border:1px solid var(--line)",
      });
      jetBody.appendChild(img);
      jetStatus.textContent = "снимок свежий";
      jetStatus.style.color = "var(--accent)";
      jetInflight = false;
    };
    probe.onerror = () => {
      jetBody.innerHTML = "";
      jetBody.appendChild(placeholder("Камера недоступна (нет /dev/video0 или занята).", "bad"));
      jetStatus.textContent = "камера недоступна";
      jetStatus.style.color = "var(--bad)";
      jetInflight = false;
      clearJetTimer();
      if (force) toast("Snapshot недоступен", "warn");
    };
    probe.src = url;
  }

  // ===== VLM scene caption ===================================================
  function paintScene() {
    const status = state.get("status");
    const sc = status?.scene_cache;
    if (!sc?.text) {
      sceneText.textContent = "Сцена пока не описана.";
      sceneMeta.textContent = "—";
      return;
    }
    sceneText.textContent = sc.text;
    const meta = sc.meta || {};
    const parts = [];
    if (meta.vlm_ms != null) parts.push(`VLM ${Math.round(meta.vlm_ms)}мс`);
    if (sc.stale) parts.push("устарело");
    if (sc.updated_at) parts.push(String(sc.updated_at).slice(11, 19));
    sceneMeta.textContent = parts.join(" · ") || "—";
  }

  // ===== bootstrap ===========================================================
  loadEsp();
  loadJetson();
  paintScene();
  const unsub = state.subscribe("status", paintScene);

  return () => {
    clearJetTimer();
    unsub();
  };
}
