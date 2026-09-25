#!/usr/bin/env bash
set -uo pipefail
rc=255
trap 'printf "%s\n" "$rc" >/workspace/one_day_probe.rc' EXIT
rm -rf /workspace/one_day_probe /workspace/models/qwen35-4b-daa9c16f3712
mkdir -p /workspace/one_day_probe/input /workspace/models/qwen35-4b-daa9c16f3712
tar -xzf /tmp/aqlevon-one-day-probe-payload.tgz -C /workspace/one_day_probe/input || { rc=81; exit "$rc"; }
python3 - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3.5-4B-Base",
    revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
    local_dir="/workspace/models/qwen35-4b-daa9c16f3712",
)
print("AQLEVON_ONE_DAY_MODEL_STAGED", flush=True)
PY
rc=$?
[ "$rc" -eq 0 ] || exit "$rc"
timeout --signal=TERM --kill-after=15s 720s python3 /workspace/one_day_probe/input/probe.py   --w02-module /workspace/one_day_probe/input/w02.py   --training-pack /workspace/one_day_probe/input/public-pack.json   --model-dir /workspace/models/qwen35-4b-daa9c16f3712   --output /workspace/one_day_probe/result.json --n 8   > /workspace/one_day_probe/probe.log 2>&1
rc=$?
exit "$rc"
