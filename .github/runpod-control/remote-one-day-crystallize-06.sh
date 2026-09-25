#!/usr/bin/env bash
set -uo pipefail
ROOT=/workspace/aqlevon_one_day_crystallize
MODEL=/workspace/models/qwen35-4b-daa9c16f3712
mkdir -p "$ROOT/input" /workspace/models
rc=255
trap 'printf "%s\n" "$rc" >"$ROOT/run.rc"' EXIT
rm -rf "$ROOT/input" "$ROOT/output" "$MODEL"
mkdir -p "$ROOT/input" "$MODEL"
tar -xzf /tmp/aqlevon-crystallize-payload.tgz -C "$ROOT/input" || { rc=81; exit "$rc"; }
python3 - <<'PY' >"$ROOT/model-stage.log" 2>&1
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3.5-4B-Base",
    revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
    local_dir="/workspace/models/qwen35-4b-daa9c16f3712",
)
print("AQLEVON_AUTH06_MODEL_STAGED", flush=True)
PY
rc=$?
[ "$rc" -eq 0 ] || exit "$rc"
python3 "$ROOT/input/materializer.py"   --recovered-decision "$ROOT/input/auth05-recovered.json"   --training-pack "$ROOT/input/public-pack.json"   --output "$ROOT/materialized-probe.json" >"$ROOT/materializer.log" 2>&1
rc=$?
[ "$rc" -eq 0 ] || exit "$rc"
timeout --signal=TERM --kill-after=20s 1000s python3 "$ROOT/input/crystallize.py"   --probe-result "$ROOT/materialized-probe.json"   --w02-module "$ROOT/input/w02.py"   --training-pack "$ROOT/input/public-pack.json"   --model-dir "$MODEL"   --output-dir "$ROOT/output" >"$ROOT/train.log" 2>&1
rc=$?
if [ -d "$ROOT/output" ]; then
  tar -czf "$ROOT/evidence.tgz" -C "$ROOT" output materialized-probe.json materializer.log train.log model-stage.log || true
fi
exit "$rc"
