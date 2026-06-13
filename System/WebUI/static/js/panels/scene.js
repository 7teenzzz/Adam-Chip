import { router } from "../router.js";

export function mount(target) {
  const btn = document.createElement("button");
  btn.className = "btn";
  btn.textContent = "Открыть Технофлору";
  btn.addEventListener("click", () => router.go("flora"));

  target.innerHTML = "";
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `<div class="card-header"><span class="card-title">Сцена</span></div>`;
  const body = document.createElement("div");
  body.className = "card-body col";
  body.style.gap = "12px";

  const note = document.createElement("p");
  note.className = "muted";
  note.style.fontSize = "13px";
  note.textContent = "Управление Flora-сценами и секвенциями перенесено в панель «Технофлора».";

  body.appendChild(note);
  body.appendChild(btn);
  card.appendChild(body);
  target.appendChild(card);
  return () => {};
}
