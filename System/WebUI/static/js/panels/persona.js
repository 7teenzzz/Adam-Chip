import { api } from "../api.js";
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

export function mount(target) {
  const status = el("div", { class: "muted", style: "font-size:12px; margin:4px 0" }, "загрузка…");
  const container = el("div", { class: "col", style: "gap:12px" });
  const reloadBtn = el("button", { class: "btn btn-ghost", onclick: () => load() }, "Обновить");

  target.appendChild(el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "row" }, [
      el("div", { class: "caps" }, "Личность агента · файлы загружаются при каждом диалоге"),
      el("span", { class: "spacer" }),
      reloadBtn,
    ]),
    status,
    container,
  ]));

  async function load() {
    status.textContent = "загрузка…";
    container.innerHTML = "";
    let data;
    try {
      data = await api.get("/api/persona");
    } catch (e) {
      status.textContent = "ошибка загрузки: " + e.message;
      return;
    }
    status.textContent = "";

    const baseTa = el("textarea", {
      class: "textarea", rows: 8, readonly: true,
      style: "font-size:12px; opacity:0.75",
    });
    baseTa.value = data.base_prompt || "";
    container.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card-header" }, [
        el("span", { class: "card-title" }, "Базовый промт"),
        el("span", { class: "dim", style: "font-size:11px" }, "встроен в код · только просмотр"),
      ]),
      el("div", { class: "card-body" }, [baseTa]),
    ]));

    (data.files || []).forEach((file) => {
      const ta = el("textarea", { class: "textarea", rows: 18, style: "font-size:12px" });
      ta.value = file.content || "";
      const st = el("span", { class: "badge", style: "margin-left:8px" });
      const saveBtn = el("button", {
        class: "btn btn-primary",
        style: "font-size:12px; padding:4px 12px",
        onclick: async () => {
          st.textContent = "сохранение…";
          st.classList.remove("ok", "bad");
          try {
            const res = await api.raw("/api/persona", { method: "PUT", body: { path: file.path, content: ta.value } });
            st.textContent = `ok · ${res.bytes} б`;
            st.classList.add("ok");
            toast(`${file.name}: сохранено`, "ok");
            setTimeout(() => { st.textContent = ""; st.classList.remove("ok"); }, 3000);
          } catch (e) {
            st.textContent = "ошибка";
            st.classList.add("bad");
            toast(`${file.name}: ${e.message}`, "bad", 5000);
          }
        },
      }, "Сохранить");

      container.appendChild(el("div", { class: "card" }, [
        el("div", { class: "card-header" }, [
          el("span", { class: "card-title" }, file.name),
          el("span", { class: "dim", style: "font-size:11px" }, file.path),
          el("span", { class: "spacer" }),
          st,
          saveBtn,
        ]),
        el("div", { class: "card-body" }, [ta]),
      ]));
    });
  }

  load();
  return () => {};
}
