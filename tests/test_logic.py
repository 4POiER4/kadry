"""Проверка бизнес-логики без внешних зависимостей: python3 tests/test_logic.py"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.calc import analyze, fmt, to_minutes  # noqa: E402

HEADER = [
    "Таб. №", "Сотрудник", "Подразделение", "Должность",
    "01.09.2026 Вторник[Вход]", "01.09.2026 Вторник[Выход]",
    "01.09.2026 Вторник[Присутствие]", "Всего",
]
FRI_HEADER = [
    "Таб. №", "Сотрудник", "Подразделение", "Должность",
    "04.09.2026 Пятница[Вход]", "04.09.2026 Пятница[Выход]",
    "04.09.2026 Пятница[Присутствие]", "Всего",
]

TITLE = ["Время прихода, ухода, присутствия за период с 01 сен, 2026 по 01 сен, 2026"]


def row(tab, name, tin, tout):
    return [tab, name, "Группа № 1", "Инженер", tin, tout, "", ""]


passed = failed = 0


def check(label, got, want):
    global passed, failed
    if got == want:
        passed += 1
        print(f"  ok   {label}: {got!r}")
    else:
        failed += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r}")


print("to_minutes:")
check("time 8:26", to_minutes(dt.time(8, 26)), 506)
check("str 17:33", to_minutes("17:33"), 1053)
check("excel frac", to_minutes(0.5), 720)
check("zero -> 0", to_minutes("00:00"), 0)
check("empty -> None", to_minutes(""), None)

print("\nПн–Чт (окно прихода 8:00–8:58, норма присутствия 9:02, зачёт 8:17):")
rows = [
    TITLE, [], HEADER,
    row("001", "Пришёл 8:45, ушёл 17:47 (ровно норма)", dt.time(8, 45), dt.time(17, 47)),
    row("002", "Пришёл 8:00, ушёл 17:10 (9:10 — норма)", dt.time(8, 0), dt.time(17, 10)),
    row("003", "Пришёл 8:30, ушёл 17:00 (8:30 — недоработка)", dt.time(8, 30), dt.time(17, 0)),
    row("004", "Пришёл 9:15 (поздно), отработал 9:30", dt.time(9, 15), dt.time(18, 45)),
    row("005", "Нет отметок", "00:00", "00:00"),
    row("006", "Только вход", dt.time(8, 10), ""),
]
res = analyze(rows, "auto")
m = res["meta"]
check("day_type", m["day_type"], "week")
check("weekday_name", m["weekday_name"], "вторник")
check("required_presence", m["required_presence"], "9:02")
check("required_net", m["required_net"], "8:17")
st = {r["tab"]: r["status"] for r in res["rows"]}
check("001 green", st["001"], "green")
check("002 green", st["002"], "green")
check("003 red", st["003"], "red")
check("004 red (late)", st["004"], "red")
check("005 nodata", st["005"], "nodata")
check("006 red (incomplete, past date)", st["006"], "red")
check("counts", m["counts"], {"total": 6, "green": 2, "red": 3, "onwork": 0, "nodata": 1})
r001 = next(r for r in res["rows"] if r["tab"] == "001")
check("001 can_leave 8:45+9:02", r001["can_leave"], "17:47")
r002 = next(r for r in res["rows"] if r["tab"] == "002")
check("002 can_leave (ранний приход не ускоряет)", r002["can_leave"], "17:02")
r003 = next(r for r in res["rows"] if r["tab"] == "003")
check("003 net", r003["net"], "7:45")
check("003 delta", r003["delta"], "-0:32")
r004 = next(r for r in res["rows"] if r["tab"] == "004")
check("004 reason has late", "Поздний приход" in r004["reason"], True)
check("004 can_leave от факта (9:15+9:02)", r004["can_leave"], "18:17")

print("\nУтренний файл за сегодня: пришёл, выхода ещё нет -> «на работе»:")
today = dt.date.today()
th = [
    "Таб. №", "Сотрудник", "Подразделение", "Должность",
    f"{today.strftime('%d.%m.%Y')} [Вход]", f"{today.strftime('%d.%m.%Y')} [Выход]",
    "[Присутствие]", "Всего",
]
trows = [
    TITLE, [], th,
    row("201", "Пришёл 8:30, ещё на работе", dt.time(8, 30), "00:00"),
    row("202", "Пришёл 9:20 поздно, ещё на работе", dt.time(9, 20), ""),
]
tres = analyze(trows, "week")
tst = {r["tab"]: r for r in tres["rows"]}
check("201 onwork", tst["201"]["status"], "onwork")
check("201 can_leave 8:30+9:02", tst["201"]["can_leave"], "17:32")
check("202 onwork", tst["202"]["status"], "onwork")
check("202 late flag", tst["202"]["late"], True)
check("202 can_leave от факта 9:20+9:02", tst["202"]["can_leave"], "18:22")
check("onwork в counts", tres["meta"]["counts"]["onwork"], 2)

print("\nПятница (окно прихода 8:00–8:58, норма присутствия 7:47, зачёт 7:02):")
frows = [
    TITLE, [], FRI_HEADER,
    row("101", "Пришёл 8:45, ушёл 17:00 (запас над нормой)", dt.time(8, 45), dt.time(17, 0)),
    row("102", "Пришёл 8:00, ушёл 15:30 (7:30 — недоработка)", dt.time(8, 0), dt.time(15, 30)),
]
fres = analyze(frows, "auto")
check("day_type fri", fres["meta"]["day_type"], "fri")
check("required_presence fri", fres["meta"]["required_presence"], "7:47")
check("required_net fri", fres["meta"]["required_net"], "7:02")
fst = {r["tab"]: r["status"] for r in fres["rows"]}
check("101 green", fst["101"], "green")
check("102 red", fst["102"], "red")
r101 = next(r for r in fres["rows"] if r["tab"] == "101")
check("101 can_leave 8:45+7:47 (пятница)", r101["can_leave"], "16:32")

samus_rows = [
    TITLE, [], FRI_HEADER,
    row("0000022044", "Самусь Елена Ивановна, пришла 8:21", dt.time(8, 21), "00:00"),
]
samus = analyze(samus_rows, "auto")["rows"][0]
check("Самусь can_leave 8:21+7:47 (пятница)", samus["can_leave"], "16:08")

print("\nРучной выбор дня перекрывает авто:")
mres = analyze(rows, "fri")
check("forced fri", mres["meta"]["day_type"], "fri")
check("source manual", mres["meta"]["day_type_source"], "manual")

print("\nПозиционный фолбэк (без заголовков):")
pos_rows = [
    ["001", "Иванов И.И.", "Отдел", "Инженер", dt.time(8, 40), dt.time(17, 50)],
]
pres = analyze(pos_rows, "week")
check("header_found False", pres["meta"]["header_found"], False)
check("row parsed green", pres["rows"][0]["status"], "green")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
