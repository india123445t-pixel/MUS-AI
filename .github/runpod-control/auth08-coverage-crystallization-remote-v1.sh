#!/usr/bin/env bash
set -uo pipefail
mkdir -p /workspace
rc=255
trap 'printf "%s\n" "$rc" >/workspace/auth08.rc' EXIT
rm -rf /workspace/MUS-AI /workspace/auth08 /workspace/models/qwen35-4b-daa9c16
mkdir -p /workspace/MUS-AI /workspace/auth08 /workspace/models/qwen35-4b-daa9c16
tar --no-same-owner -xzf /tmp/coverage-source.tgz -C /workspace/MUS-AI || { rc=81; exit "$rc"; }
test "$(cat /workspace/MUS-AI/.aqlevon_source_head)" = "529e665ea140c2f8d6b96c02a42c100e9075c037" || { rc=82; exit "$rc"; }
cp /tmp/public-pack.json /workspace/auth08/public-pack.json || { rc=83; exit "$rc"; }
cp /tmp/w02.py /workspace/auth08/w02.py || { rc=84; exit "$rc"; }
cp /tmp/recovered-materialized-probe.json /workspace/auth08/probe.json || { rc=85; exit "$rc"; }
python3 - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3.5-4B-Base",
    revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
    local_dir="/workspace/models/qwen35-4b-daa9c16",
)
print("AQLEVON_AUTH08_MODEL_STAGED", flush=True)
PY
rc=$?
[ "$rc" -eq 0 ] || exit "$rc"
timeout --signal=TERM --kill-after=20s 1200s python3 /workspace/MUS-AI/research/weight_factory/agent03/p4_one_day_crystallize_coverage.py \
  --probe-result /workspace/auth08/probe.json \
  --w02-module /workspace/auth08/w02.py \
  --training-pack /workspace/auth08/public-pack.json \
  --model-dir /workspace/models/qwen35-4b-daa9c16 \
  --output-dir /workspace/auth08/candidate \
  > /workspace/auth08/train.log 2>&1
rc=$?
exit "$rc"
