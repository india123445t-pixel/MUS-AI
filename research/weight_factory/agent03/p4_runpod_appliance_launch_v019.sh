#!/usr/bin/env bash
set -euo pipefail

START_TS="$(date +%s)"
ROOT=/workspace
REPO="$ROOT/MUS-AI"
SDPO_IMAGE=/opt/aqlevon/runtime/SDPO
SDPO="$ROOT/SDPO"
DATA="$ROOT/aqlevon_p4/data"
MODEL="$ROOT/models/qwen35-4b-daa9c16f3712"
EXPECTED_HEAD="${AQLEVON_EXPECTED_W03_HEAD:?AQLEVON_EXPECTED_W03_HEAD is required}"
EXPECTED_IMAGE_DIGEST="${AQLEVON_EXPECTED_IMAGE_DIGEST:?AQLEVON_EXPECTED_IMAGE_DIGEST is required}"
[[ "$EXPECTED_IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo "FAIL_CLOSED_BAD_EXPECTED_IMAGE_DIGEST"; exit 39; }
export AQLEVON_EXPECTED_IMAGE_DIGEST="$EXPECTED_IMAGE_DIGEST"

echo "AQLEVON_APPLIANCE_LAUNCH_START $(date -u +%FT%TZ)"
echo "AQLEVON_EXPECTED_IMAGE_DIGEST=$EXPECTED_IMAGE_DIGEST"

test -d "$SDPO_IMAGE/.git" || { echo "FAIL_CLOSED_APPLIANCE_SDPO_MISSING"; exit 40; }
python3 /opt/aqlevon/runtime/smoke_runtime_v019.py --build-check
# Retry19Q proved the pinned SDPO launcher invokes `python`, while the
# vLLM appliance may expose only `python3`. Repair this explicitly and
# fail closed before model staging/training; this is runtime plumbing only.
if ! command -v python >/dev/null 2>&1; then
  PY3="$(command -v python3)"
  test -n "$PY3" || { echo "FAIL_CLOSED_PYTHON3_MISSING"; exit 49; }
  ln -sf "$PY3" /usr/local/bin/python
fi
python - <<'PY'
import sys
assert sys.version_info[:2] == (3, 12), sys.version
print("AQLEVON_SDPO_PYTHON_LAUNCHER_PASS", sys.executable, sys.version.split()[0])
PY
python3 - <<'PY'
import torch
assert torch.cuda.is_available(), "AQLEVON_V019_CUDA_UNAVAILABLE"
p=torch.cuda.get_device_properties(0)
gib=p.total_memory/(1024**3)
name=p.name
assert gib >= 44.0, f"AQLEVON_V019_GPU_MEMORY_TOO_SMALL:{name}:{gib:.2f}GiB"
assert ("A40" in name) or ("A6000" in name), f"AQLEVON_V019_GPU_SKU_UNAUTHORIZED:{name}"
print("AQLEVON_V019_GPU_IDENTITY_PASS",name,f"{gib:.2f}GiB")
PY

if [ ! -d "$REPO/.git" ]; then
  git clone -q --no-checkout https://github.com/india123445t-pixel/MUS-AI.git "$REPO"
fi
# Freeze execution to the Manager-authorized commit. Never reset to a mutable
# branch head: concurrent Worker03 commits must not invalidate or alter a paid run.
if ! git -C "$REPO" cat-file -e "$EXPECTED_HEAD^{commit}" 2>/dev/null; then
  git -C "$REPO" fetch -q origin "$EXPECTED_HEAD"
fi
git -C "$REPO" checkout -q --detach "$EXPECTED_HEAD"
git -C "$REPO" reset -q --hard "$EXPECTED_HEAD"
ACTUAL_HEAD="$(git -C "$REPO" rev-parse HEAD)"
echo "MUS_AI_HEAD=$ACTUAL_HEAD"
test "$ACTUAL_HEAD" = "$EXPECTED_HEAD" || { echo "FAIL_CLOSED_WRONG_HEAD"; exit 41; }
echo "APPLIANCE_IMMUTABLE_HEAD_PASS=$ACTUAL_HEAD"

AGENT="$REPO/research/weight_factory/agent03"
RUN="$AGENT/p4_a1_seed1701_run_manifest_v1.json"
LOCK="$AGENT/p4_a1_seed1701_command_lock_v1.json"
PLAN="$AGENT/p4_frozen_training_plan_v1.json"

RESOLVED_RUNTIME_FILES="$(python3 - <<'PY'
import json, os, sys
from pathlib import Path
repo=Path("/workspace/MUS-AI")
agent=repo/"research/weight_factory/agent03"
sys.path.insert(0,str(agent))
import p4_gene1_trainer as c
run=json.loads((agent/"p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads((agent/"p4_a1_seed1701_command_lock_v1.json").read_text())
auth_name,binding_name=c.resolve_runtime_launch_files(
    agent_dir=agent,
    repo_dir=repo,
    actual_head=os.environ["AQLEVON_EXPECTED_W03_HEAD"],
    expected_image_digest=os.environ["AQLEVON_EXPECTED_IMAGE_DIGEST"],
    run_manifest_sha256=run["manifest_sha256"],
    command_lock_sha256=lock["lock_sha256"],
)
print(auth_name+"|"+binding_name)
PY
)"
AUTH_FILE="${RESOLVED_RUNTIME_FILES%%|*}"
BINDING_FILE="${RESOLVED_RUNTIME_FILES#*|}"
test -n "$AUTH_FILE" -a -n "$BINDING_FILE" -a "$AUTH_FILE" != "$BINDING_FILE" || { echo "FAIL_CLOSED_RUNTIME_CONTRACT_RESOLUTION"; exit 42; }
export AQLEVON_RESOLVED_AUTH_FILE="$AUTH_FILE"
export AQLEVON_RESOLVED_BINDING_FILE="$BINDING_FILE"
echo "APPLIANCE_RUNTIME_CONTRACT_AUTO_RESOLVED auth=$AUTH_FILE binding=$BINDING_FILE"

AUTH="$AGENT/$AUTH_FILE"
BINDING="$AGENT/$BINDING_FILE"
test -f "$AUTH" || { echo "FAIL_CLOSED_AUTH_FILE_MISSING=$AUTH_FILE"; exit 42; }
test -f "$BINDING" || { echo "FAIL_CLOSED_BINDING_FILE_MISSING=$BINDING_FILE"; exit 44; }
rm -rf "$SDPO"
ln -s "$SDPO_IMAGE" "$SDPO"

# Native vLLM 0.19.1 appliance: do not mutate vLLM/site-packages at runtime.
# Verify the pinned SDPO + TF5 compatibility patch baked into the image.
test "$(git -C "$SDPO_IMAGE" rev-parse HEAD)" = "7c457fc1b1f636ae794eb0362ba37d4743b06fbc" || { echo "FAIL_CLOSED_SDPO_COMMIT_MISMATCH"; exit 46; }
grep -q "AQLEVON_TF5_VISION_ALIAS" "$SDPO_IMAGE/verl/utils/model.py" || { echo "FAIL_CLOSED_TF5_MODEL_ALIAS_MISSING"; exit 47; }
grep -q "AQLEVON_TF5_VISION_ALIAS" "$SDPO_IMAGE/verl/workers/fsdp_workers.py" || { echo "FAIL_CLOSED_TF5_FSDP_ALIAS_MISSING"; exit 48; }
python3 - <<'PY'
import importlib, vllm
assert vllm.__version__.split("+")[0] == "0.19.1", vllm.__version__
q=importlib.import_module("vllm.model_executor.models.qwen3_5")
assert hasattr(q,"Qwen3_5ForCausalLM")
assert hasattr(q,"Qwen3_5ForConditionalGeneration")
print("APPLIANCE_NATIVE_QWEN35_VLLM019_PASS",vllm.__version__)
PY

rm -rf "$ROOT/aqlevon_p4"
mkdir -p "$DATA" "$MODEL" /tmp/p4inputs

python3 - <<'PY'
import json, os, sys
from pathlib import Path
agent=Path("/workspace/MUS-AI/research/weight_factory/agent03")
sys.path.insert(0,str(agent))
import p4_gene1_trainer as c
auth=json.loads((agent/os.environ["AQLEVON_RESOLVED_AUTH_FILE"]).read_text())
binding=json.loads((agent/os.environ["AQLEVON_RESOLVED_BINDING_FILE"]).read_text())
run=json.loads((agent/"p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads((agent/"p4_a1_seed1701_command_lock_v1.json").read_text())
assert c.verify_self_digest(auth,"authorization_sha256"),auth
assert c.verify_self_digest(binding,"binding_sha256"),binding
assert binding["binding_kind"]=="AQLEVON_RUNTIME_APPLIANCE_BINDING_V1",binding
assert binding["authorization_sha256"]==auth["authorization_sha256"],binding
assert binding["run_manifest_sha256"]==run["manifest_sha256"],binding
assert binding["command_lock_sha256"]==lock["lock_sha256"],binding
assert binding["runtime_appliance_digest"]==os.environ["AQLEVON_EXPECTED_IMAGE_DIGEST"],binding
assert binding["runtime_appliance_image"]=="ghcr.io/india123445t-pixel/mus-ai@"+binding["runtime_appliance_digest"],binding
print("APPLIANCE_BINDING_PASS",binding["binding_sha256"],binding["runtime_appliance_digest"])
print("APPLIANCE_RUNTIME_SOURCE_COMMIT",binding["worker03_runtime_source_commit"])
PY

RUNTIME_SOURCE="$(python3 - <<'PY'
import json, os
from pathlib import Path
agent=Path("/workspace/MUS-AI/research/weight_factory/agent03")
b=json.loads((agent/os.environ["AQLEVON_RESOLVED_BINDING_FILE"]).read_text())
print(b["worker03_runtime_source_commit"])
PY
)"
DELTA="$(git -C "$REPO" diff --name-only "$RUNTIME_SOURCE..$ACTUAL_HEAD")"
EXPECTED_DELTA="research/weight_factory/agent03/$BINDING_FILE"
test "$DELTA" = "$EXPECTED_DELTA" || { echo "FAIL_CLOSED_RUNTIME_SOURCE_DRIFT"; printf '%s\n' "$DELTA"; exit 45; }
echo "APPLIANCE_SOURCE_DELTA_PASS=$EXPECTED_DELTA"

git -C "$REPO" fetch -q --no-tags origin \
  abb94ef134e2e97036b6959dbc9db4278d3736b6 \
  f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae

git -C "$REPO" show f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae:research/evaluation/gene1_worker01_method_tournament_spec_v1.json > /tmp/p4inputs/w01.json
git -C "$REPO" show f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae:research/evaluation/gene1_worker02_public_pack_binding_v1.json > /tmp/p4inputs/w02_binding.json
git -C "$REPO" show f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae:research/evaluation/gene1_evaluation_law_v1.json > /tmp/p4inputs/w05_law.json
git -C "$REPO" show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_shard_manifest_v1.json > /tmp/p4inputs/shard_manifest.json
git -C "$REPO" show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_shard_v1.jsonl > /tmp/p4inputs/shard.jsonl
git -C "$REPO" show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_visible_pack_v1.json > /tmp/p4inputs/pack.json
git -C "$REPO" show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_split_commitment_v1.json > /tmp/p4inputs/split.json

cd "$AGENT"
python3 p4_gene1_trainer.py freeze-plan \
  --method-spec /tmp/p4inputs/w01.json \
  --training-shard-manifest /tmp/p4inputs/shard_manifest.json \
  --training-shard /tmp/p4inputs/shard.jsonl \
  --training-pack /tmp/p4inputs/pack.json \
  --split /tmp/p4inputs/split.json \
  --w02-binding /tmp/p4inputs/w02_binding.json \
  --w05-law /tmp/p4inputs/w05_law.json \
  --output /tmp/p4inputs/generated_plan.json

diff -u "$PLAN" /tmp/p4inputs/generated_plan.json

python3 p4_surrogate_tournament.py prepare-data \
  --training-shard /tmp/p4inputs/shard.jsonl \
  --training-pack /tmp/p4inputs/pack.json \
  --output-dir "$DATA"

python3 - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
 repo_id="Qwen/Qwen3.5-4B-Base",
 revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
 local_dir="/workspace/models/qwen35-4b-daa9c16f3712",
)
print("MODEL_STAGE_PASS")
PY

python3 - <<'PY'
import json, os
from pathlib import Path
import p4_gene1_trainer as c
import p4_surrogate_tournament as t
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path(os.environ["AQLEVON_RESOLVED_AUTH_FILE"]).read_text())
assert run["manifest_sha256"]=="b277b41d3d67be1180b4d0600ab6f533f6dbf7b69163980ef5ecc6f0677195b7"
assert lock["lock_sha256"]=="10f333cf453f5896402066d7c483ae170688909ca82a08a0adb1e90766213fcb"
assert c.verify_self_digest(auth,"authorization_sha256")
argv=t.build_a1_argv(Path("p4_frozen_training_plan_v1.json"),Path("/workspace"))
assert argv==lock["argv"]
assert c.canonical_sha256(argv)==run["command_sha256"]
required_seed={
    "data.seed=1701",
    "actor_rollout_ref.actor.data_loader_seed=1701",
    "actor_rollout_ref.actor.fsdp_config.seed=1701",
    "actor_rollout_ref.ref.fsdp_config.seed=1701",
    "++actor_rollout_ref.rollout.engine_kwargs.vllm.seed=1701",
}
assert required_seed.issubset(set(argv)), sorted(required_seed-set(argv))
required_memory={
    "actor_rollout_ref.actor.fsdp_config.model_dtype=bf16",
    "actor_rollout_ref.actor.fsdp_config.param_offload=True",
    "actor_rollout_ref.actor.fsdp_config.optimizer_offload=True",
}
assert required_memory.issubset(set(argv)), sorted(required_memory-set(argv))
assert not c.validate_command_seed_binding(argv,arm_id=lock["arm_id"],seed=lock["seed"])
print("APPLIANCE_SEED1701_BINDING_PASS")
errors=c.validate_manager_authorization(auth,lock=lock,run_manifest_sha256=run["manifest_sha256"])
assert not errors, errors
print("APPLIANCE_EXACT_AUTHORIZATION_PASS",auth["authorization_sha256"])
PY

python3 - <<'PY'
import os
from pathlib import Path
import hydra
from omegaconf import OmegaConf
import p4_surrogate_tournament as t

argv=t.build_a1_argv(Path("p4_frozen_training_plan_v1.json"),Path("/workspace"))
os.environ["EXPERIMENT"]=argv[4]
os.environ["TASK"]=argv[6]
with hydra.initialize_config_dir(config_dir="/workspace/SDPO/verl/trainer/config",version_base=None):
    cfg=hydra.compose(config_name=argv[5],overrides=argv[7:])
OmegaConf.resolve(cfg)
assert cfg.actor_rollout_ref.rollout.max_model_len == 4096, cfg.actor_rollout_ref.rollout.max_model_len
assert cfg.actor_rollout_ref.rollout.max_num_batched_tokens == 4096, cfg.actor_rollout_ref.rollout.max_num_batched_tokens
assert cfg.actor_rollout_ref.rollout.max_num_seqs == 16, cfg.actor_rollout_ref.rollout.max_num_seqs
profile_num_reqs=min(
    cfg.actor_rollout_ref.rollout.max_num_batched_tokens,
    cfg.actor_rollout_ref.rollout.max_num_seqs,
)
assert profile_num_reqs == 16, profile_num_reqs
assert cfg.data.train_batch_size * cfg.actor_rollout_ref.rollout.n == 16
derived_default_max_cudagraph_capture_size=min(cfg.actor_rollout_ref.rollout.max_num_seqs*2,512)
assert derived_default_max_cudagraph_capture_size <= 32, derived_default_max_cudagraph_capture_size
print(
    "AQLEVON_V019_EFFECTIVE_SCHEDULER_PASS",
    "max_model_len=4096",
    "max_num_batched_tokens=4096",
    "max_num_seqs=16",
    f"profile_num_reqs={profile_num_reqs}",
    f"derived_default_max_cudagraph_capture_size={derived_default_max_cudagraph_capture_size}",
)
PY

echo "AQLEVON_V019_LORA_SMOKE_START elapsed=$(( $(date +%s) - START_TS ))"
nvidia-smi --query-gpu=name,memory.total,memory.free,utilization.gpu --format=csv
timeout --signal=TERM --kill-after=20s 2400s \
  python3 "$AGENT/p4_v019_gpu_lora_smoke.py" \
    --model-path "$MODEL" \
    --evidence "$ROOT/aqlevon_p4/v019_lora_smoke.json"
echo "AQLEVON_V019_LORA_SMOKE_PASS"
nvidia-smi --query-gpu=name,memory.total,memory.free,utilization.gpu --format=csv

ELAPSED="$(( $(date +%s) - START_TS ))"
TOTAL_EXECUTION_BUDGET_SECONDS=3300
MIN_TRAIN_WINDOW_SECONDS=900
REMAINING="$(( TOTAL_EXECUTION_BUDGET_SECONDS - ELAPSED ))"
if [ "$REMAINING" -lt "$MIN_TRAIN_WINDOW_SECONDS" ]; then
  echo "FAIL_CLOSED insufficient training window after smoke elapsed=${ELAPSED}s remaining=${REMAINING}s"
  exit 43
fi

echo "A1_LOCKED_TRAINING_START elapsed=${ELAPSED}s remaining=${REMAINING}s"

# Diagnostic-only sampler: preserve enough evidence to distinguish host/cgroup OOM,
# GPU pressure, or an abrupt worker crash during first rollout wake/weight sync.
DIAG="$ROOT/aqlevon_p4/runtime_resource_diag.tsv"
(
  echo -e "utc\tcgroup_current\tcgroup_peak\tcgroup_events\tmem_available_kb\tgpu_used_mib\tgpu_free_mib\tworker_rss_kb"
  while true; do
    ts="$(date -u +%FT%TZ)"
    cur="$(cat /sys/fs/cgroup/memory.current 2>/dev/null || echo NA)"
    peak="$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo NA)"
    events="$(tr '\n' ',' < /sys/fs/cgroup/memory.events 2>/dev/null || echo NA)"
    avail="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null || echo NA)"
    gpu="$(nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d ' ' || echo NA,NA)"
    used="${gpu%%,*}"; free="${gpu#*,}"
    rss="$(ps -eo comm=,rss= 2>/dev/null | awk '$1 ~ /ray::WorkerDict|python/ {s+=$2} END {print s+0}')"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$ts" "$cur" "$peak" "$events" "$avail" "$used" "$free" "$rss"
    sleep 1
  done
) >> "$DIAG" 2>&1 &
DIAG_PID=$!
cleanup_diag() { kill "$DIAG_PID" 2>/dev/null || true; wait "$DIAG_PID" 2>/dev/null || true; }
trap cleanup_diag EXIT

set +e
timeout --signal=TERM --kill-after=20s "${REMAINING}s" \
python3 - <<'PY' 2>&1 | tee "$ROOT/aqlevon_p4/P4_A1_seed1701_appliance.log"
import json, os
from pathlib import Path
import p4_gene1_trainer as c
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path(os.environ["AQLEVON_RESOLVED_AUTH_FILE"]).read_text())
rc=c.run_locked(
    lock,
    paid=True,
    authorization=auth,
    run_manifest_sha256=run["manifest_sha256"],
    cwd=Path("/workspace/MUS-AI"),
)
raise SystemExit(rc)
PY
RC=${PIPESTATUS[0]}
set -e
cleanup_diag
trap - EXIT

echo "AQLEVON_A1_EXIT_CODE=$RC"
echo "AQLEVON_RUNTIME_RESOURCE_DIAG=$DIAG"
tail -n 30 "$DIAG" 2>/dev/null || true
find "$ROOT/aqlevon_p4/runs" -maxdepth 5 -type f -printf '%p %s bytes\\n' 2>/dev/null | tail -n 100 || true
echo "AQLEVON_APPLIANCE_TOTAL_SCRIPT_SECONDS=$(( $(date +%s) - START_TS ))"
exit "$RC"
