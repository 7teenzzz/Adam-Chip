// Panel: #/agent/instructions
// Displays System.md / Lore.md / Abilities.md as rendered markdown with edit toggle.
// Identity.md is intentionally excluded — it belongs to the Persona (agent/persona) panel.

import { api } from "../../api.js";
import { toast } from "../../widgets/toast.js";

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

// Persona files shown in this panel (Identity.md is NOT included).
const INSTRUCTION_FILES = ["System.md", "Lore.md", "Abilities.md"];

function fileMatchesInstructions(path) {
  return INSTRUCTION_FILES.some((name) => path.endsWith(name));
}

// Build a markdown render+edit toggle card for a single persona file.
function buildMarkdownEditor(file, onSave) {
  let isEditing = false;
  let currentContent = file.content || "";

  // Render view: marked.parse() if available, otherwise raw <pre> fallback.
  function buildRenderedView(content) {
    if (window.marked) {
      return el("div", {
        class: "rendered-md",
        style: "font-size:14px; line-height:1.6; padding:16px; overflow:auto; min-height:120px",
        html: window.marked.parse(content || ""),
      });
    }
    // Offline / CDN blocked fallback — show raw text.
    const pre = el("pre", {
      class: "textarea",
      style: "font-size:13px; white-space:pre-wrap; min-height:120px; margin:0",
    });
    pre.textContent = content || "";
    return pre;
  }

  const renderedContainer = el("div", {});
  renderedContainer.appendChild(buildRenderedView(currentContent));

  const textarea = el("textarea", {
    class: "textarea",
    style: "display:none; font-size:13px; min-height:240px; resize:vertical; width:100%; box-sizing:border-box",
  });
  textarea.value = currentContent;

  const saveBadge = el("span", { class: "badge", style: "margin-left:8px" });

  const saveBtn = el("button", {
    class: "btn btn-primary",
    style: "display:none; font-size:12px; padding:4px 14px",
    onclick: async () => {
      const newContent = textarea.value;
      saveBadge.classList.remove("ok", "bad");
      saveBadge.classList.add("warn");
      saveBadge.textContent = "сохранение…";
      try {
        await onSave(file.path, newContent);
        currentContent = newContent;
        // Switch back to view mode with updated content.
        renderedContainer.innerHTML = "";
        renderedContainer.appendChild(buildRenderedView(currentContent));
        isEditing = false;
        renderedContainer.style.display = "";
        textarea.style.display = "none";
        editBtn.textContent = "Редактировать";
        saveBtn.style.display = "none";
        cancelBtn.style.display = "none";
        saveBadge.classList.remove("warn");
        saveBadge.classList.add("ok");
        saveBadge.textContent = "сохранено ✓";
        setTimeout(() => { saveBadge.textContent = ""; saveBadge.classList.remove("ok"); }, 2500);
      } catch (e) {
        saveBadge.classList.remove("warn");
        saveBadge.classList.add("bad");
        saveBadge.textContent = "ошибка";
        toast(`Ошибка сохранения: ${e.message}`, "bad", 5000);
      }
    },
  }, "Сохранить");

  const cancelBtn = el("button", {
    class: "btn btn-ghost",
    style: "display:none; font-size:12px; padding:4px 14px",
    onclick: () => {
      // Cancel edit — restore textarea to current saved content and go back to view.
      textarea.value = currentContent;
      isEditing = false;
      renderedContainer.style.display = "";
      textarea.style.display = "none";
      editBtn.textContent = "Редактировать";
      saveBtn.style.display = "none";
      cancelBtn.style.display = "none";
      saveBadge.textContent = "";
      saveBadge.classList.remove("ok", "bad", "warn");
    },
  }, "Отмена");

  const editBtn = el("button", {
    class: "btn btn-ghost",
    style: "font-size:12px; padding:4px 14px",
    onclick: () => {
      isEditing = !isEditing;
      if (isEditing) {
        textarea.value = currentContent;
        renderedContainer.style.display = "none";
        textarea.style.display = "";
        editBtn.textContent = "Редактировать";
        saveBtn.style.display = "";
        cancelBtn.style.display = "";
        // Auto-focus textarea on edit entry.
        setTimeout(() => textarea.focus(), 0);
      } else {
        // Pressing Редактировать while in edit acts like cancel.
        renderedContainer.style.display = "";
        textarea.style.display = "none";
        saveBtn.style.display = "none";
        cancelBtn.style.display = "none";
      }
    },
  }, "Редактировать");

  const card = el("section", { class: "card" }, [
    el("div", { class: "card-header" }, [
      el("span", { class: "card-title" }, file.name),
      el("span", { class: "dim", style: "font-size:11px; margin-left:8px" }, file.path),
      el("span", { class: "spacer" }),
      saveBadge,
      cancelBtn,
      saveBtn,
      editBtn,
    ]),
    el("div", { class: "card-body", style: "padding:0" }, [
      renderedContainer,
      textarea,
    ]),
  ]);

  return card;
}

export function mount(target) {
  const loadingMsg = el("div", {
    class: "muted",
    style: "font-size:12px; padding:12px 0",
    text: "Загрузка…",
  });

  const container = el("div", { class: "col", style: "gap:12px" });

  const reloadBtn = el("button", {
    class: "btn btn-ghost",
    onclick: () => load(),
  }, "Обновить");

  target.appendChild(el("section", { class: "col", style: "gap:12px" }, [
    el("div", { class: "row" }, [
      el("div", { class: "caps" }, "Инструкции агента · System.md / Lore.md / Abilities.md"),
      el("span", { class: "spacer" }),
      reloadBtn,
    ]),
    loadingMsg,
    container,
  ]));

  async function load() {
    loadingMsg.textContent = "Загрузка…";
    loadingMsg.style.display = "";
    container.innerHTML = "";

    let data;
    try {
      data = await api.get("/api/persona");
    } catch (e) {
      loadingMsg.textContent = "Ошибка загрузки: " + e.message;
      return;
    }
    loadingMsg.style.display = "none";

    const files = (data.files || []).filter((f) => fileMatchesInstructions(f.path));

    if (files.length === 0) {
      container.appendChild(el("div", {
        class: "muted",
        style: "font-size:12px; padding:12px",
        text: "Файлы инструкций не найдены (System.md / Lore.md / Abilities.md).",
      }));
      return;
    }

    files.forEach((file) => {
      const card = buildMarkdownEditor(file, async (path, content) => {
        await api.raw("/api/persona", {
          method: "PUT",
          body: { path, content },
        });
        toast(`${file.name}: сохранено`, "ok");
      });
      container.appendChild(card);
    });
  }

  load();

  // No SSE subscriptions in this panel — teardown is a no-op.
  return () => {};
}
