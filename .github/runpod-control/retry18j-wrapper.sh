#!/usr/bin/env bash
set -euo pipefail

: "${AQLEVON_EXPECTED_W03_HEAD:?required}"
: "${RESULT_TOKEN:?required}"

ROOT=/workspace
REPO="$ROOT/MUS-AI"
EXPORT="$ROOT/export"
PAYLOAD="$EXPORT/payload"
CONSOLE="$ROOT/retry18j-console.log"
PROGRESS="$EXPORT/progress.json"

mkdir -p "$EXPORT" "$PAYLOAD"

python - <<'PY'
import json,datetime
out={
  "schema_version":1,
  "run":"Retry18J",
  "phase":"wrapper_started",
  "started_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()
}
with open("/workspace/export/progress.json","w",encoding="utf-8") as f:
    json.dump(out,f,sort_keys=True); f.write("\n")
PY

cat > /tmp/serve_result.py <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
TOKEN=os.environ["RESULT_TOKEN"]
ROOT=Path("/workspace/export")
class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return
    def do_GET(self):
        path=self.path.split("?",1)[0]
        mapping={
          f"/{TOKEN}/health.json": (ROOT/"progress.json","application/json"),
          f"/{TOKEN}/result.tgz": (ROOT/"result.tgz","application/octet-stream"),
          f"/{TOKEN}/result.tgz.sha256": (ROOT/"result.tgz.sha256","text/plain"),
        }
        item=mapping.get(path)
        if item is None or not item[0].is_file():
            self.send_response(404); self.end_headers(); return
        p,ctype=item
        self.send_response(200)
        self.send_header("Content-Length",str(p.stat().st_size))
        self.send_header("Content-Type",ctype)
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        with p.open("rb") as f:
            while True:
                b=f.read(1024*1024)
                if not b: break
                self.wfile.write(b)
ThreadingHTTPServer(("0.0.0.0",8000),H).serve_forever()
PY

python /tmp/serve_result.py &
SERVER_PID=$!

python - <<'PY'
import json,datetime
p="/workspace/export/progress.json"
out={
  "schema_version":1,
  "run":"Retry18J",
  "phase":"appliance_launch_running",
  "updated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()
}
with open(p,"w",encoding="utf-8") as f:
    json.dump(out,f,sort_keys=True); f.write("\n")
PY

if [ ! -d "$REPO/.git" ]; then
  git clone -q --branch agent/03-p4-gene1-physical-trainer --single-branch \
    https://github.com/india123445t-pixel/MUS-AI.git "$REPO"
fi

set +e
bash "$REPO/research/weight_factory/agent03/p4_runpod_appliance_launch.sh" >"$CONSOLE" 2>&1
RC=$?
set -e

cp "$CONSOLE" "$PAYLOAD/retry18j-console.log" || true
if [ -d "$ROOT/aqlevon_p4" ]; then
  cp -a "$ROOT/aqlevon_p4" "$PAYLOAD/aqlevon_p4"
fi

python - "$RC" <<'PY'
import json, os, sys, datetime
rc=int(sys.argv[1])
out={
  "schema_version":1,
  "run":"Retry18J",
  "worker03_head":os.environ["AQLEVON_EXPECTED_W03_HEAD"],
  "exit_code":rc,
  "completed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
with open("/workspace/export/payload/result.json","w",encoding="utf-8") as f:
    json.dump(out,f,indent=2,sort_keys=True); f.write("\n")
progress={
  "schema_version":1,
  "run":"Retry18J",
  "phase":"appliance_launch_completed",
  "exit_code":rc,
  "updated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
with open("/workspace/export/progress.json","w",encoding="utf-8") as f:
    json.dump(progress,f,sort_keys=True); f.write("\n")
PY

tar -czf "$EXPORT/result.tgz" -C "$PAYLOAD" .
sha256sum "$EXPORT/result.tgz" | awk '{print $1}' > "$EXPORT/result.tgz.sha256"

# Keep the container alive only to serve the collected evidence.
wait "$SERVER_PID"
