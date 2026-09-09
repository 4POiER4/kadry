from __future__ import annotations

import datetime as dt
import io
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .calc import analyze
from .config import settings
from .excel_export import build_xlsx
from .parser import load_rows
from .store import clear as store_clear
from .store import get_latest, set_latest

BASE = Path(__file__).parent
STATIC = BASE / "static"

app = FastAPI(title="Кадры — контроль присутствия", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_hours * 3600,
    same_site="lax",
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _user(request: Request) -> str | None:
    return request.session.get("user")


def _require(request: Request) -> None:
    if not _user(request):
        raise HTTPException(status_code=401, detail="Требуется вход")


# --------------------------------------------------------------------------- #
# Страницы
# --------------------------------------------------------------------------- #
@app.get("/")
def home():
    """Публичная страница для сотрудников: во сколько я пришёл / когда уйти."""
    return FileResponse(STATIC / "employee.html")


@app.get("/hr")
def hr_page(request: Request):
    if not _user(request):
        return RedirectResponse("/login", status_code=302)
    return FileResponse(STATIC / "index.html")


@app.get("/login")
def login_page(request: Request):
    if _user(request):
        return RedirectResponse("/hr", status_code=302)
    return FileResponse(STATIC / "login.html")


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == settings.username and password == settings.password:
        request.session["user"] = username
        return RedirectResponse("/hr", status_code=302)
    return RedirectResponse("/login?e=1", status_code=302)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# --------------------------------------------------------------------------- #
# API кадровика (требует вход)
# --------------------------------------------------------------------------- #
@app.post("/api/process")
async def api_process(
    request: Request,
    file: UploadFile = File(...),
    day_type: str = Form("auto"),
):
    _require(request)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")
    try:
        rows = load_rows(file.filename or "", data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать файл: {exc}")
    if not rows:
        raise HTTPException(status_code=400, detail="В файле нет строк")
    try:
        result = analyze(rows, day_type)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Ошибка обработки: {exc}")

    result["meta"]["source_filename"] = file.filename
    set_latest(
        {
            "meta": result["meta"],
            "rows": result["rows"],
            "published_at": dt.datetime.now().strftime("%d.%m.%Y %H:%M"),
            "filename": file.filename,
            "by": _user(request),
        }
    )
    return JSONResponse(result)


@app.post("/api/export")
def api_export(request: Request, payload: dict = Body(...)):
    _require(request)
    if not payload.get("rows"):
        raise HTTPException(status_code=400, detail="Нет данных для выгрузки")
    xlsx = build_xlsx(payload)
    fname = "kadry_prisutstvie.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.get("/api/latest")
def api_latest(request: Request):
    """Последняя обработанная таблица — чтобы страница кадров не теряла её
    при переходах и перезагрузке."""
    _require(request)
    latest = get_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="Нет обработанных данных")
    return {"meta": latest.get("meta", {}), "rows": latest.get("rows", [])}


@app.post("/api/clear")
def api_clear(request: Request):
    _require(request)
    store_clear()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Публичное API для сотрудников
# --------------------------------------------------------------------------- #
def _status_payload() -> dict:
    latest = get_latest()
    if not latest:
        return {"has_data": False}
    m = latest.get("meta", {})
    return {
        "has_data": True,
        "date": m.get("date"),
        "weekday_name": m.get("weekday_name"),
        "day_type_label": m.get("day_type_label"),
        "required_presence": m.get("required_presence"),
        "required_net": m.get("required_net"),
        "lunch": m.get("lunch"),
        "arrival_window": m.get("arrival_window"),
        "report_is_today": m.get("report_is_today"),
        "published_at": latest.get("published_at"),
        "filename": latest.get("filename"),
        "count": m.get("counts", {}).get("total"),
    }


@app.get("/api/status")
def api_status():
    return _status_payload()


@app.get("/api/lookup")
def api_lookup(q: str = ""):
    q = (q or "").strip().lower()
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="Введите минимум 3 символа (фамилию или табельный номер)")
    latest = get_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="Данные ещё не загружены. Загляните позже.")

    matches = []
    for r in latest.get("rows", []):
        if q in r.get("name", "").lower() or q in r.get("tab", "").lower():
            matches.append(
                {
                    "name": r.get("name", ""),
                    "tab": r.get("tab", ""),
                    "t_in": r.get("t_in", ""),
                    "t_out": r.get("t_out", ""),
                    "can_leave": r.get("can_leave", ""),
                    "status": r.get("status", ""),
                    "reason": r.get("reason", ""),
                    "late": r.get("late", False),
                }
            )
    matches.sort(key=lambda x: x["name"])
    return {
        "matches": matches[:30],
        "truncated": len(matches) > 30,
        "status": _status_payload(),
    }


@app.exception_handler(HTTPException)
async def _http_exc(request: Request, exc: HTTPException):
    if exc.status_code == 401 and not request.url.path.startswith("/api/"):
        return RedirectResponse("/login", status_code=302)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
