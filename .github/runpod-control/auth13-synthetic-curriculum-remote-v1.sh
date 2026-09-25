#!/usr/bin/env bash
set -uo pipefail

SOURCE_HEAD="${1:?source head required}"
mkdir -p /workspace
rc=255
trap 'printf "%s\n" "$rc" >/workspace/auth13.rc' EXIT

rm -rf /workspace/MUS-AI /workspace/auth13 /workspace/models/qwen35-4b-daa9c16
mkdir -p /workspace/MUS-AI /workspace/auth13 /workspace/models/qwen35-4b-daa9c16

tar --no-same-owner -xzf /tmp/rsft-source.tgz -C /workspace/MUS-AI || { rc=81; exit "$rc"; }
test "$(cat /workspace/MUS-AI/.aqlevon_source_head)" = "$SOURCE_HEAD" || { rc=82; exit "$rc"; }
cp /tmp/public-pack.json /workspace/auth13/public-pack.json || { rc=83; exit "$rc"; }
cp /tmp/w02.py /workspace/auth13/w02.py || { rc=84; exit "$rc"; }
cp /tmp/recovered-materialized-probe.json /workspace/auth13/probe.json || { rc=85; exit "$rc"; }

python3 - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3.5-4B-Base",
    revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
    local_dir="/workspace/models/qwen35-4b-daa9c16",
)
print("AQLEVON_AUTH13_MODEL_STAGED", flush=True)
PY
rc=$?
[ "$rc" -eq 0 ] || exit "$rc"

timeout --signal=TERM --kill-after=20s 1200s   python3 /workspace/MUS-AI/research/weight_factory/agent03/p4_one_day_synthetic_curriculum.py     --probe-result /workspace/auth13/probe.json     --w02-module /workspace/auth13/w02.py     --training-pack /workspace/auth13/public-pack.json     --model-dir /workspace/models/qwen35-4b-daa9c16     --output-dir /workspace/auth13/candidate     > /workspace/auth13/train.log 2>&1
rc=$?
exit "$rc"
