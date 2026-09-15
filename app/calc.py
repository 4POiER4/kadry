"""Бизнес-логика: расчёт присутствия и статуса по каждому сотруднику."""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from .config import settings
from .parser import cell, detect_day, find_layout

STATUS_GREEN = "green"
STATUS_RED = "red"
STATUS_NODATA = "nodata"
STATUS_ONWORK = "onwork"


def to_minutes(v: Any) -> int | None:
    """Значение ячейки времени -> минуты от полуночи. Пусто/None -> None."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.hour * 60 + v.minute
    if isinstance(v, dt.time):
        return v.hour * 60 + v.minute
    if isinstance(v, dt.timedelta):
        return int(v.total_seconds() // 60)
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        if f == 0:
            return 0
        if f < 2:  # доля суток (формат времени Excel)
            return int(round(f * 1440))
        return int(round((f % 1) * 1440))  # серийная дата-время Excel
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def fmt(minutes: int | None) -> str:
    if minutes is None:
        return ""
    sign = "-" if minutes < 0 else ""
    minutes = abs(int(round(minutes)))
    return f"{sign}{minutes // 60}:{minutes % 60:02d}"


def fmt_delta(minutes: int | None) -> str:
    if minutes is None:
        return ""
    return ("+" if minutes >= 0 else "-") + fmt(abs(minutes))


def _clean(m: int | None) -> int | None:
    """0 или None считаем отсутствием отметки."""
    return None if m in (None, 0) else m


def _can_leave(in_m: int, required_presence: int) -> int:
    """Во сколько можно уйти = приход (в пределах окна) + норма присутствия.

    Ранний приход не ускоряет уход (нижняя граница окна), поздний — считается
    от факта.
    """
    if in_m > settings.arrival_end:
        base = in_m
    else:
        base = max(in_m, settings.arrival_start)
    return base + required_presence


def _resolve_day_type(requested: str, detected: dict[str, Any]) -> tuple[str, str]:
    """Возвращает (day_type, source)."""
    requested = (requested or "auto").lower()
    if requested in ("week", "fri"):
        return requested, "manual"
    dt_ = detected.get("day_type")
    if dt_ == "fri":
        return "fri", "auto"
    if dt_ == "week":
        return "week", "auto"
    if dt_ == "weekend":
        return "week", "auto-weekend"  # выходной в отчёте — считаем по будней норме, предупреждаем
    return "week", "default"


def analyze(rows: list[list[Any]], day_type_request: str = "auto") -> dict[str, Any]:
    header_idx, cols = find_layout(rows)
    detected = detect_day(rows, header_idx, cols)
    day_type, source = _resolve_day_type(day_type_request, detected)

    required_presence = settings.required_fri if day_type == "fri" else settings.required_week
    lunch = settings.lunch_min
    required_net = required_presence - lunch

    report_date: dt.date | None = None
    if detected.get("date"):
        try:
            report_date = dt.date.fromisoformat(detected["date"])
        except ValueError:
            report_date = None
    report_is_today = report_date is None or report_date == dt.date.today()

    start_idx = (header_idx + 1) if header_idx is not None else 0
    out_rows: list[dict[str, Any]] = []

    for row in rows[start_idx:]:
        name = str(cell(row, cols.get("name")) or "").strip()
        tab = cell(row, cols.get("tab"))
        tab_s = "" if tab is None else str(tab).strip()
        if not name and not tab_s:
            continue
        if name.lower().startswith(("итого", "всего по", "среднее", "сотрудник")):
            continue

        in_cell = cell(row, cols.get("t_in"))
        out_cell = cell(row, cols.get("t_out"))
        in_raw = to_minutes(in_cell)
        out_raw = to_minutes(out_cell)

        # Фолбэк без заголовков: строка с текстом вместо времени — это шапка, пропускаем
        if header_idx is None and in_raw is None and out_raw is None:
            if str(in_cell or "").strip() or str(out_cell or "").strip():
                continue
        in_m = _clean(in_raw)
        out_m = _clean(out_raw)

        late = in_m is not None and in_m > settings.arrival_end
        can_leave_min = _can_leave(in_m, required_presence) if in_m is not None else None

        rec: dict[str, Any] = {
            "tab": tab_s,
            "name": name,
            "dep": str(cell(row, cols.get("dep")) or "").strip(),
            "pos": str(cell(row, cols.get("pos")) or "").strip(),
            "t_in": fmt(in_m),
            "t_out": fmt(out_m),
            "t_in_min": in_m,
            "t_out_min": out_m,
            "can_leave_min": can_leave_min,
            "can_leave": fmt(can_leave_min),
            "presence_min": None,
            "presence": "",
            "net_min": None,
            "net": "",
            "delta_min": None,
            "delta": "",
            "late": late,
            "status": STATUS_NODATA,
            "reason": "",
        }

        if in_m is None and out_m is None:
            rec["reason"] = "Нет отметок (отсутствие / отпуск / больничный)"
            out_rows.append(rec)
            continue

        if in_m is None:
            rec["status"] = STATUS_RED
            rec["reason"] = "Неполные отметки: нет входа"
            out_rows.append(rec)
            continue

        if out_m is None:
            # Пришёл, но выхода ещё нет
            if late:
                rec["status"] = STATUS_RED
                rec["reason"] = f"Поздний приход ({fmt(in_m)} позже {fmt(settings.arrival_end)})"
            elif report_is_today:
                rec["status"] = STATUS_ONWORK
                rec["reason"] = "На работе — ухода ещё нет"
            else:
                rec["status"] = STATUS_RED
                rec["reason"] = "Неполные отметки: нет выхода"
            out_rows.append(rec)
            continue

        if out_m <= in_m:
            rec["status"] = STATUS_RED
            rec["reason"] = "Выход раньше или равен входу — проверить вручную"
            out_rows.append(rec)
            continue

        presence = out_m - in_m
        net = presence - lunch
        enough = presence >= required_presence

        rec.update(
            presence_min=presence,
            presence=fmt(presence),
            net_min=net,
            net=fmt(net),
            delta_min=net - required_net,
            delta=fmt_delta(net - required_net),
            late=late,
        )

        reasons: list[str] = []
        if late:
            reasons.append(f"Поздний приход ({fmt(in_m)} позже {fmt(settings.arrival_end)})")
        if not enough:
            reasons.append(f"Недоработка {fmt(required_presence - presence)}")

        if reasons:
            rec["status"] = STATUS_RED
            rec["reason"] = "; ".join(reasons)
        else:
            rec["status"] = STATUS_GREEN
            rec["reason"] = "Норма"
            if in_m < settings.arrival_start:
                rec["reason"] = f"Норма (ранний приход {fmt(settings.arrival_start - in_m)})"

        out_rows.append(rec)

    counts = {
        "total": len(out_rows),
        "green": sum(1 for r in out_rows if r["status"] == STATUS_GREEN),
        "red": sum(1 for r in out_rows if r["status"] == STATUS_RED),
        "onwork": sum(1 for r in out_rows if r["status"] == STATUS_ONWORK),
        "nodata": sum(1 for r in out_rows if r["status"] == STATUS_NODATA),
    }

    meta = {
        "date": detected.get("date"),
        "weekday_name": detected.get("weekday_name"),
        "day_type": day_type,
        "day_type_label": "Пятница" if day_type == "fri" else "Понедельник–четверг",
        "day_type_source": source,
        "lunch_min": lunch,
        "lunch": fmt(lunch),
        "required_presence_min": required_presence,
        "required_presence": fmt(required_presence),
        "required_net_min": required_net,
        "required_net": fmt(required_net),
        "arrival_window": f"{fmt(settings.arrival_start)}–{fmt(settings.arrival_end)}",
        "arrival_start": fmt(settings.arrival_start),
        "arrival_end": fmt(settings.arrival_end),
        "header_found": header_idx is not None,
        "report_is_today": report_is_today,
        "generated_at": dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "counts": counts,
    }
    return {"meta": meta, "rows": out_rows}
