"use strict";

const $ = (s) => document.querySelector(s);

const STATUS = {
  green: { label: "Норма", cls: "green" },
  onwork: { label: "На работе", cls: "onwork" },
  red: { label: "Внимание", cls: "red" },
  nodata: { label: "Нет отметок", cls: "nodata" },
};

let hasData = false;

async function loadStatus() {
  try {
    const r = await fetch("/api/status");
    const s = await r.json();
    hasData = !!s.has_data;
    const line = $("#status-line");
    if (!s.has_data) {
      line.textContent = "Данные за сегодня ещё не загружены. Загляните позже.";
      $("#q").disabled = true;
      $("#lookup-form").querySelector("button").disabled = true;
      return;
    }
    const bits = [];
    if (s.date) bits.push(`Данные за ${s.date}`);
    if (s.weekday_name) bits.push(s.weekday_name);
    if (s.day_type_label) bits.push(s.day_type_label);
    bits.push(`норма присутствия ${s.required_presence} (обед ${s.lunch} включён)`);
    if (s.published_at) bits.push(`загружено ${s.published_at}`);
    line.textContent = bits.join(" · ");
    if (s.report_is_today === false) {
      line.textContent += " — отчёт не за сегодняшнюю дату";
    }
  } catch {
    $("#status-line").textContent = "Не удалось получить статус данных.";
  }
}

function showErr(msg) {
  const e = $("#err");
  e.textContent = msg;
  e.hidden = false;
}
function hideErr() {
  $("#err").hidden = true;
}

$("#lookup-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  hideErr();
  const q = $("#q").value.trim();
  if (q.length < 3) {
    showErr("Введите минимум 3 символа.");
    return;
  }
  $("#results").innerHTML = "";
  try {
    const r = await fetch("/api/lookup?q=" + encodeURIComponent(q));
    const body = await r.json();
    if (!r.ok) throw new Error(body.detail || "Ошибка запроса");
    render(body.matches, body.truncated);
  } catch (e) {
    showErr(e.message);
  }
});

function render(matches, truncated) {
  const wrap = $("#results");
  wrap.innerHTML = "";
  if (!matches.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.style.marginTop = "1rem";
    p.textContent =
      "Ничего не найдено. Проверьте написание фамилии или попробуйте табельный номер.";
    wrap.appendChild(p);
    return;
  }

  if (matches.length > 1) {
    const h = document.createElement("p");
    h.className = "muted";
    h.style.margin = "1rem 0 .25rem";
    h.textContent = `Найдено совпадений: ${matches.length}${truncated ? "+ (показаны первые 30)" : ""}`;
    wrap.appendChild(h);
  }

  const tpl = $("#card-tpl");
  for (const m of matches) {
    const node = tpl.content.firstElementChild.cloneNode(true);
    node.querySelector(".rc-name").textContent = m.name || "—";
    node.querySelector(".rc-tab").textContent = m.tab ? "таб. № " + m.tab : "";

    const st = STATUS[m.status] || STATUS.nodata;
    const chip = node.querySelector(".chip");
    chip.textContent = st.label;
    chip.classList.add(st.cls);

    node.querySelector(".rc-in").textContent = m.t_in || "—";

    const outCell = node.querySelector(".rc-leave");
    const outVal = node.querySelector(".rc-out");
    if (m.can_leave) {
      outVal.textContent = m.can_leave;
      if (m.late) outCell.classList.add("warn-cell");
    } else {
      outVal.textContent = "—";
      outCell.classList.add("dim");
    }

    const reason = node.querySelector(".rc-reason");
    let txt = m.reason || "";
    if (m.status === "green" && m.t_out) txt = `Ушли в ${m.t_out}. ${txt}`;
    reason.textContent = txt;
    reason.hidden = !txt;

    wrap.appendChild(node);
  }
}

loadStatus();
