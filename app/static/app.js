"use strict";

const $ = (s) => document.querySelector(s);

const state = {
  file: null,
  data: null,          // { meta, rows }
  sortKey: null,
  sortDir: 1,
};

const fileInput = $("#file");
const drop = $("#drop");
const goBtn = $("#go");
const errBox = $("#err");

// ---------- выбор файла ----------
drop.addEventListener("click", () => fileInput.click());
["dragenter", "dragover"].forEach((ev) =>
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.add("drag");
  })
);
["dragleave", "drop"].forEach((ev) =>
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
  })
);
drop.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) setFile(fileInput.files[0]);
});

function setFile(f) {
  state.file = f;
  $("#fname").textContent = f.name;
  goBtn.disabled = false;
  hideErr();
}

function showErr(msg) {
  errBox.textContent = msg;
  errBox.hidden = false;
}
function hideErr() {
  errBox.hidden = true;
}

// ---------- обработка ----------
goBtn.addEventListener("click", async () => {
  if (!state.file) return;
  goBtn.disabled = true;
  goBtn.textContent = "Обработка…";
  hideErr();
  try {
    const fd = new FormData();
    fd.append("file", state.file);
    fd.append("day_type", $("#daytype").value);
    const resp = await fetch("/api/process", { method: "POST", body: fd });
    if (resp.status === 401) {
      location.href = "/login";
      return;
    }
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || "Ошибка обработки");
    state.data = body;
    render();
    loadPublishBanner();
  } catch (e) {
    showErr(e.message);
  } finally {
    goBtn.disabled = false;
    goBtn.textContent = "Обработать";
  }
});

$("#reset").addEventListener("click", () => {
  state.file = null;
  state.data = null;
  fileInput.value = "";
  $("#fname").textContent = "";
  goBtn.disabled = true;
  $("#result").hidden = true;
  $("#upload-card").hidden = false;
});

$("#search").addEventListener("input", renderRows);
$("#statusfilter").addEventListener("change", renderRows);

document.querySelectorAll("#tbl thead th").forEach((th) => {
  th.addEventListener("click", () => {
    const k = th.dataset.k;
    if (state.sortKey === k) state.sortDir *= -1;
    else {
      state.sortKey = k;
      state.sortDir = 1;
    }
    renderRows();
  });
});

$("#download").addEventListener("click", async () => {
  if (!state.data) return;
  const resp = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.data),
  });
  if (!resp.ok) {
    showErr("Не удалось сформировать Excel");
    return;
  }
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "kadry_prisutstvie.xlsx";
  a.click();
  URL.revokeObjectURL(a.href);
});

// ---------- отрисовка ----------
function render() {
  const m = state.data.meta;
  $("#upload-card").hidden = true;
  $("#result").hidden = false;

  const parts = [];
  if (m.date) parts.push(`<b>Дата:</b> ${m.date}`);
  if (m.weekday_name) parts.push(m.weekday_name);
  parts.push(`<b>Режим:</b> ${m.day_type_label}`);
  parts.push(`норма присутствия <b>${m.required_presence}</b>`);
  parts.push(`обед ${m.lunch}`);
  parts.push(`зачётная норма <b>${m.required_net}</b>`);
  parts.push(`окно прихода ${m.arrival_window}`);
  $("#meta-line").innerHTML = parts.join(" &nbsp;·&nbsp; ");

  const warns = [];
  if (!m.header_found)
    warns.push("Не найдена строка заголовков — колонки взяты по позициям A–F. Проверьте результат.");
  if (m.day_type_source === "default")
    warns.push("Не удалось определить день недели из файла. Выбран режим «Пн–Чт». При необходимости выберите день вручную и обработайте заново.");
  if (m.day_type_source === "auto-weekend")
    warns.push("В отчёте выходной день. Расчёт выполнен по будней норме.");
  if (m.day_type_source === "manual")
    warns.push("День недели задан вручную.");
  const wl = $("#warn-line");
  if (warns.length) {
    wl.innerHTML = warns.join("<br>");
    wl.hidden = false;
  } else {
    wl.hidden = true;
  }

  $("#c-total").textContent = m.counts.total;
  $("#c-green").textContent = m.counts.green;
  $("#c-onwork").textContent = m.counts.onwork ?? 0;
  $("#c-red").textContent = m.counts.red;
  $("#c-nodata").textContent = m.counts.nodata;

  renderRows();
}

function renderRows() {
  if (!state.data) return;
  const q = $("#search").value.trim().toLowerCase();
  const sf = $("#statusfilter").value;

  let rows = state.data.rows.filter((r) => {
    if (sf !== "all" && r.status !== sf) return false;
    if (!q) return true;
    return (
      (r.name || "").toLowerCase().includes(q) ||
      (r.tab || "").toLowerCase().includes(q)
    );
  });

  if (state.sortKey) {
    const k = state.sortKey;
    rows = rows.slice().sort((a, b) => {
      let x = a[k], y = b[k];
      if (x === null || x === undefined || x === "") x = -Infinity;
      if (y === null || y === undefined || y === "") y = -Infinity;
      if (typeof x === "string" || typeof y === "string")
        return String(x).localeCompare(String(y), "ru") * state.sortDir;
      return (x - y) * state.sortDir;
    });
  }

  const tb = $("#tbl tbody");
  tb.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.className = r.status;
    tr.innerHTML =
      `<td>${esc(r.tab)}</td>` +
      `<td>${esc(r.name)}</td>` +
      `<td class="num">${esc(r.t_in)}</td>` +
      `<td class="num">${esc(r.t_out)}</td>` +
      `<td class="num">${esc(r.can_leave)}</td>` +
      `<td class="num">${esc(r.net)}</td>` +
      `<td class="num">${esc(r.delta)}</td>` +
      `<td class="reason">${esc(r.reason)}</td>`;
    tb.appendChild(tr);
  }
  $("#empty").hidden = rows.length > 0;
}

function esc(v) {
  return String(v ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}

// ---------- баннер «опубликовано для сотрудников» ----------
async function loadPublishBanner() {
  try {
    const r = await fetch("/api/status");
    const s = await r.json();
    const banner = $("#publish-banner");
    if (!s.has_data) {
      banner.hidden = true;
      return;
    }
    const bits = [];
    if (s.date) bits.push(`за ${s.date}`);
    if (s.weekday_name) bits.push(s.weekday_name);
    if (s.filename) bits.push(`файл «${s.filename}»`);
    if (s.published_at) bits.push(`загружено ${s.published_at}`);
    $("#publish-text").textContent =
      "Доступно сотрудникам: " + bits.join(" · ") + `; записей: ${s.count ?? "?"}`;
    banner.hidden = false;
  } catch {
    /* молча */
  }
}

$("#clear-publish").addEventListener("click", async () => {
  if (!confirm("Убрать текущие данные со страницы сотрудников?")) return;
  await fetch("/api/clear", { method: "POST" });
  state.data = null;
  $("#result").hidden = true;
  $("#upload-card").hidden = false;
  loadPublishBanner();
});

// ---------- восстановление последней обработанной таблицы ----------
async function restoreLatest() {
  try {
    const r = await fetch("/api/latest");
    if (!r.ok) return;
    const body = await r.json();
    if (body && Array.isArray(body.rows) && body.rows.length) {
      state.data = body;
      render();
    }
  } catch {
    /* тихо */
  }
}

loadPublishBanner();
restoreLatest();
