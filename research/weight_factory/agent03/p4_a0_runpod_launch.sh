#!/usr/bin/env bash
set -euo pipefail

ROOT=/workspace
REPO="$ROOT/MUS-AI"
PUBLIC="$ROOT/aqlevon_a0/public"
MODEL="$ROOT/models/qwen35-4b-daa9c16f3712"
OUT="$ROOT/aqlevon_a0/candidate/P4_A0_seed1701_Worker05"
HEAD="${AQLEVON_EXPECTED_A0_HEAD:?immutable A0 source SHA required}"
IMAGE="${AQLEVON_EXPECTED_IMAGE_DIGEST:?runtime image digest required}"
[[ "$HEAD" =~ ^[0-9a-f]{40}$ && "$IMAGE" =~ ^sha256:[0-9a-f]{64}$ ]]
START="$(date +%s)"
echo "AQLEVON_A0_LAUNCH_START=$(date -u +%FT%TZ) SOURCE_HEAD=$HEAD IMAGE_DIGEST=$IMAGE"

python3 - <<'PY'
import torch
p=torch.cuda.get_device_properties(0)
allowed={'NVIDIA A40':44_000_000_000,'NVIDIA A100 80GB PCIe':75_000_000_000,'NVIDIA A100-SXM4-80GB':75_000_000_000}
assert p.name in allowed,p.name
assert p.total_memory>=allowed[p.name],p.total_memory
assert torch.cuda.is_bf16_supported()
print('AQLEVON_A0_GPU_BF16_PASS',p.name,p.total_memory,flush=True)
PY

test "$(git -C "$REPO" rev-parse HEAD)" = "$HEAD"
mkdir -p "$PUBLIC" "$MODEL" "$(dirname "$OUT")"
if [[ -s "$PUBLIC/shard.jsonl" && -s "$PUBLIC/manifest.json" ]]; then
  echo AQLEVON_A0_PINNED_PUBLIC_INPUTS_STAGED
else
  git -C "$REPO" fetch -q --no-tags origin abb94ef134e2e97036b6959dbc9db4278d3736b6
  git -C "$REPO" show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_shard_v1.jsonl > "$PUBLIC/shard.jsonl"
  git -C "$REPO" show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_shard_manifest_v1.json > "$PUBLIC/manifest.json"
fi

TRAINER="$REPO/research/weight_factory/agent03/p4_a0_sft_candidate.py"
PLAN="$REPO/research/weight_factory/agent03/p4_frozen_training_plan_v1.json"
python3 "$TRAINER" --shard-path "$PUBLIC/shard.jsonl" --manifest-path "$PUBLIC/manifest.json" --plan-path "$PLAN" --preflight-only
python3 - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(repo_id='Qwen/Qwen3.5-4B-Base',
                  revision='daa9c16f371249f9ad1c75a9ed6f956c08ea08f5',
                  local_dir='/workspace/models/qwen35-4b-daa9c16f3712')
print('AQLEVON_A0_PINNED_MODEL_STAGED',flush=True)
PY

RESOURCE="$ROOT/aqlevon_a0/resource.tsv"
(
  printf 'utc\tcgroup_current\tcgroup_peak\tcgroup_events\tavailable_kb\tgpu_used_mib\tgpu_free_mib\n'
  while true; do
    ev="$(tr '\n' ',' </sys/fs/cgroup/memory.events 2>/dev/null || echo UNKNOWN)"
    current="$(cat /sys/fs/cgroup/memory.current 2>/dev/null || echo UNKNOWN)"
    peak="$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo UNKNOWN)"
    available="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
    gpu="$(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits | head -n1 | tr -d ' ')"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -u +%FT%TZ)" "$current" "$peak" "$ev" "$available" "${gpu%%,*}" "${gpu#*,}"
    sleep 2
  done
) > "$RESOURCE" 2>&1 &
SAMPLER=$!
finish() { kill "$SAMPLER" 2>/dev/null || true; wait "$SAMPLER" 2>/dev/null || true; }
trap finish EXIT

echo "AQLEVON_A0_TRAINING_START elapsed=$(( $(date +%s) - START ))" 
timeout --signal=TERM --kill-after=20s 3600s python3 "$TRAINER" \
  --shard-path "$PUBLIC/shard.jsonl" --manifest-path "$PUBLIC/manifest.json" \
  --plan-path "$PLAN" --model-dir "$MODEL" --repo-dir "$REPO" --output-dir "$OUT"
echo "AQLEVON_A0_TRAINING_AND_PACKAGE_PASS total_seconds=$(( $(date +%s) - START ))"
