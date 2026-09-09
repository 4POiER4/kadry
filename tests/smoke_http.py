"""HTTP-смоук для API. Запуск внутри контейнера:
   docker compose exec -T web python tests/smoke_http.py
"""
import http.cookiejar
import io
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.getenv("BASE", "http://127.0.0.1:8000")
SAMPLE = os.getenv("SAMPLE", "samples/sample.xlsx")

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = []

ok = bad = 0


def check(label, cond, extra=""):
    global ok, bad
    if cond:
        ok += 1
        print(f"  ok   {label} {extra}")
    else:
        bad += 1
        print(f"  FAIL {label} {extra}")


def get(path):
    try:
        r = opener.open(BASE + path)
        return r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post_form(path, fields, allow_redirect=True):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        r = opener.open(req)
        return r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post_multipart(path, filename, filebytes, extra):
    boundary = "----smoke1234"
    buf = io.BytesIO()

    def w(s):
        buf.write(s.encode() if isinstance(s, str) else s)

    for k, v in extra.items():
        w(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
    w(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n")
    w("Content-Type: application/octet-stream\r\n\r\n")
    w(filebytes)
    w(f"\r\n--{boundary}--\r\n")
    req = urllib.request.Request(BASE + path, data=buf.getvalue(), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    try:
        r = opener.open(req)
        return r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post_json(path, obj):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        r = opener.open(req)
        return r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


import urllib.parse  # noqa: E402

print("status before:")
code, body = get("/api/status")
s0 = json.loads(body)
check("GET /api/status 200", code == 200, str(s0))

print("pages:")
check("GET / 200 (employee)", get("/")[0] == 200)
check("GET /login 200", get("/login")[0] == 200)

print("hr login + process:")
code, _ = post_form("/login", {"username": "kadry", "password": "kadry"})
check("login ok", code in (200, 302), f"code={code}")
with open(SAMPLE, "rb") as f:
    fb = f.read()
code, body = post_multipart("/api/process", "sample.xlsx", fb, {"day_type": "auto"})
check("process 200", code == 200, f"code={code}")
res = json.loads(body)
counts = res["meta"]["counts"]
check("counts has onwork key", "onwork" in counts, str(counts))
check("row0 has can_leave", bool(res["rows"][0].get("can_leave")), res["rows"][0].get("can_leave"))

print("status after publish:")
code, body = get("/api/status")
s1 = json.loads(body)
check("has_data true", s1.get("has_data") is True, str(s1))

print("latest restore (hr):")
code, body = get("/api/latest")
lt = json.loads(body) if code == 200 else {}
check("GET /api/latest 200", code == 200, f"code={code}")
check("latest has rows", bool(lt.get("rows")), f"n={len(lt.get('rows', []))}")
check("latest meta has counts", "counts" in lt.get("meta", {}), str(lt.get("meta", {}).get("counts")))

print("public lookup:")
q = urllib.parse.quote("Августинович")
code, body = get(f"/api/lookup?q={q}")
check("lookup 200", code == 200, f"code={code}")
lk = json.loads(body)
m = lk["matches"][0] if lk["matches"] else {}
check("lookup match found", bool(m), str(m)[:120])
check("match has can_leave", bool(m.get("can_leave")), m.get("can_leave"))
code, _ = get("/api/lookup?q=ab")
check("lookup q=ab -> 400", code == 400, f"code={code}")
code, body = get("/api/lookup?q=zzzzz")
check("lookup no match -> 200 empty", code == 200 and json.loads(body)["matches"] == [])

print("export:")
code, body = post_json("/api/export", res)
check("export 200 + xlsx magic", code == 200 and body[:2] == b"PK", f"code={code} len={len(body)}")

print("clear:")
code, _ = post_json("/api/clear", {})
check("clear 200", code == 200, f"code={code}")
check("status has_data false after clear", json.loads(get("/api/status")[1])["has_data"] is False)
check("latest 404 after clear", get("/api/latest")[0] == 404)

print(f"\n{ok} ok, {bad} failed")
sys.exit(1 if bad else 0)
