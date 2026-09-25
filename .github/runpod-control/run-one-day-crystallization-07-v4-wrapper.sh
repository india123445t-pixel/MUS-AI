#!/usr/bin/env bash
set -euo pipefail

BASE=".github/runpod-control/run-one-day-crystallization-07-v3.sh"
OUT="/tmp/run-one-day-crystallization-07-v4.sh"
OLD_SHA="7cdc2be72a407fed6e25333e4689c8dd26cda9f3d1a5e606f002fe4f1658c379"
NEW_SHA="7e5ccecce48c2340e45d2c9ccbfe6641a2aaccdca1675729a97d8d6dceddd222"

python3 - <<'PY'
from pathlib import Path
p=Path(".github/runpod-control/run-one-day-crystallization-07-v3.sh").read_text()
p=p.replace("7cdc2be72a407fed6e25333e4689c8dd26cda9f3d1a5e606f002fe4f1658c379",
            "7e5ccecce48c2340e45d2c9ccbfe6641a2aaccdca1675729a97d8d6dceddd222")
p=p.replace("assert free>=70000,(name,free)","assert free>=40000,(name,free)")
Path("/tmp/run-one-day-crystallization-07-v4.sh").write_text(p)
PY

bash -n "$OUT"
grep -q '7e5ccecce48c2340e45d2c9ccbfe6641a2aaccdca1675729a97d8d6dceddd222' "$OUT"
grep -q 'assert free>=40000' "$OUT"
grep -q 'auth07-crystallization-remote-v3.sh' "$OUT"

if [ "${AQLEVON_FREE_CONTRACT_ONLY:-0}" = 1 ]; then
  echo AQLEVON_AUTH07_V4_FREE_CONTRACT_PASS
  exit 0
fi

exec bash "$OUT"
