#!/usr/bin/env bash
set -euo pipefail

: "${AQLEVON_EXPECTED_W03_HEAD:?required}"
: "${RESULT_TOKEN:?required}"

ROOT=/workspace
REPO="$ROOT/MUS-AI"
EXPORT="$ROOT/export"
PAYLOAD="$EXPORT/payload"
CONSOLE="$ROOT/retry18k-console.log"
mkdir -p "$PAYLOAD"

cat > /tmp/serve_result.py <<'PY'
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
TOKEN=os.environ["RESULT_TOKEN"]
ROOT=Path("/workspace/export")
class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): return
    def do_GET(self):
        path=self.path.split("?",1)[0]
        if path==f"/{TOKEN}/health":
            body=b"ok\n"
            self.send_response(200); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body); return
        mapping={
            f"/{TOKEN}/result.tgz":ROOT/"result.tgz",
            f"/{TOKEN}/result.tgz.sha256":ROOT/"result.tgz.sha256",
        }
        p=mapping.get(path)
        if p is None or not p.is_file():
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Length",str(p.stat().st_size))
        self.send_header("Content-Type","application/octet-stream")
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

if [ ! -d "$REPO/.git" ]; then
  git clone -q --branch agent/03-p4-gene1-physical-trainer --single-branch https://github.com/india123445t-pixel/MUS-AI.git "$REPO"
fi

set +e
bash "$REPO/research/weight_factory/agent03/p4_runpod_appliance_launch.sh" >"$CONSOLE" 2>&1
RC=$?
set -e

cp "$CONSOLE" "$PAYLOAD/retry18k-console.log" || true
if [ -d "$ROOT/aqlevon_p4" ]; then
  cp -a "$ROOT/aqlevon_p4" "$PAYLOAD/aqlevon_p4"
fi

python - "$RC" <<'PY'
import json, os, sys, datetime
out={
  "schema_version":1,
  "run":"Retry18K",
  "worker03_head":os.environ["AQLEVON_EXPECTED_W03_HEAD"],
  "exit_code":int(sys.argv[1]),
  "completed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
with open("/workspace/export/payload/result.json","w",encoding="utf-8") as f:
    json.dump(out,f,indent=2,sort_keys=True); f.write("\n")
PY

tar -czf "$EXPORT/result.tgz" -C "$PAYLOAD" .
sha256sum "$EXPORT/result.tgz" | awk '{print $1}' > "$EXPORT/result.tgz.sha256"

wait "$SERVER_PID"
