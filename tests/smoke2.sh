#!/usr/bin/env bash
set -u
BASE=http://localhost:8163
J=$(mktemp)

echo "# public status (before)"
curl -s $BASE/api/status; echo

echo "# pages"
curl -s -o /dev/null -w "GET /      -> %{http_code}\n" $BASE/
curl -s -o /dev/null -w "GET /hr    -> %{http_code} (expect 302)\n" $BASE/hr
curl -s -o /dev/null -w "GET /login -> %{http_code}\n" $BASE/login

echo "# hr login + process (auto-publish)"
curl -s -c $J -o /dev/null $BASE/login
curl -s -b $J -c $J -o /dev/null -w "login  -> %{http_code}\n" \
  --data-urlencode username=kadry --data-urlencode password=kadry $BASE/login
curl -s -b $J -F file=@samples/sample.xlsx -F day_type=auto \
  -o /tmp/r.json -w "process -> %{http_code}\n" $BASE/api/process
python3 -c "import json;d=json.load(open('/tmp/r.json'));print(' counts:',d['meta']['counts']);print(' row0:',d['rows'][0]['name'],'| can_leave',d['rows'][0]['can_leave'])"

echo "# public status (after publish)"
curl -s $BASE/api/status; echo

echo "# public lookup"
curl -s "$BASE/api/lookup?q=%D0%90%D0%B2%D0%B3%D1%83%D1%81%D1%82%D0%B8%D0%BD%D0%BE%D0%B2%D0%B8%D1%87" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);m=d['matches'][0] if d['matches'] else {};print(' match:',m.get('name'),'| пришёл',m.get('t_in'),'| уйти не раньше',m.get('can_leave'),'| статус',m.get('status'))"
curl -s -o /dev/null -w " lookup q=ab -> %{http_code} (expect 400)\n" "$BASE/api/lookup?q=ab"
curl -s -o /dev/null -w " lookup q=zzzz -> %{http_code} (200, 0 matches)\n" "$BASE/api/lookup?q=zzzz"

echo "# export"
curl -s -b $J -H 'Content-Type: application/json' --data-binary @/tmp/r.json \
  -o /tmp/r.xlsx -w "export -> %{http_code} %{size_download}b\n" $BASE/api/export

echo "# clear (auth) + status"
curl -s -b $J -X POST -o /dev/null -w "clear -> %{http_code}\n" $BASE/api/clear
curl -s $BASE/api/status; echo

rm -f $J /tmp/r.json /tmp/r.xlsx
