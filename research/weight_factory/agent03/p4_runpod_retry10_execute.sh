#!/usr/bin/env bash
set -uo pipefail

START_TS=$(date +%s)
SCRIPT_BUDGET=1050
ROOT=/workspace
REPO="$ROOT/MUS-AI"
SDPO="$ROOT/SDPO"
DATA="$ROOT/aqlevon_p4/data"
MODEL="$ROOT/models/qwen35-4b-daa9c16f3712"
LOG="$ROOT/aqlevon_p4/P4_A1_R10.log"

fail(){ echo "AQLEVON_R10_FAIL: $*" | tee -a "$LOG"; exit 2; }
mkdir -p "$ROOT/aqlevon_p4" "$ROOT/models" || exit 2
: > "$LOG"

echo "AQLEVON_R10_BEGIN $(date -u +%FT%TZ)" | tee -a "$LOG"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | tee -a "$LOG" || fail "nvidia-smi"
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
[[ "$GPU_NAME" == *"RTX 4090"* ]] || fail "wrong_gpu:$GPU_NAME"

rm -rf "$REPO" "$SDPO" "$ROOT/aqlevon_p4/data" "$MODEL"
git clone -q --branch agent/03-p4-gene1-physical-trainer --single-branch https://github.com/india123445t-pixel/MUS-AI.git "$REPO" || fail "clone_repo"
git clone -q https://github.com/lasgroup/SDPO.git "$SDPO" || fail "clone_sdpo"
git -C "$SDPO" checkout -q 7c457fc1b1f636ae794eb0362ba37d4743b06fbc || fail "sdpo_checkout"

cd "$REPO" || fail "cd_repo"
[[ "$(git hash-object research/weight_factory/agent03/p4_gene1_trainer.py)" == "14b5573f682c0b50860a570f1328b3b0eca21032" ]] || fail "trainer_blob"
[[ "$(git hash-object research/weight_factory/agent03/p4_surrogate_tournament.py)" == "20accc2df44c5a5db002e14a0f3842e459631987" ]] || fail "tournament_blob"
[[ "$(git hash-object research/weight_factory/agent03/p4_aqlevon_reward.py)" == "c9db3e315299cce59c5d4cece7de86302c10c614" ]] || fail "reward_blob"
[[ "$(git hash-object research/weight_factory/agent03/p4_patch_sdpo_transformers5_compat.py)" == "81d4c2e2df463293c16a3a3d5ff84f0ecb991fd2" ]] || fail "patch_blob"
echo "SOURCE_BLOBS_PASS $(git rev-parse HEAD)" | tee -a "$LOG"

python -m pip install -q --no-cache-dir --disable-pip-version-check   transformers==5.17.0 peft==0.21.0 accelerate==1.15.0   pyarrow==22.0.0 qwen-vl-utils==0.0.14 hydra-core==1.3.2   "ray[default]==2.53.0" vllm==0.10.2   torchdata==0.11.0 tensordict==0.10.0 datasets==4.4.2   codetiming==1.4.0 safetensors psutil huggingface-hub pillow || fail "pip_install"

git fetch -q --no-tags origin abb94ef134e2e97036b6959dbc9db4278d3736b6 f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae || fail "fetch_inputs"
mkdir -p /tmp/p4inputs "$DATA" || fail "mkdir_inputs"

git show f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae:research/evaluation/gene1_worker01_method_tournament_spec_v1.json > /tmp/p4inputs/w01.json || fail "w01"
git show f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae:research/evaluation/gene1_worker02_public_pack_binding_v1.json > /tmp/p4inputs/w02_binding.json || fail "w02_binding"
git show f01e0ba91bbfa43e0d659fba5c0d0c4f64a06cae:research/evaluation/gene1_evaluation_law_v1.json > /tmp/p4inputs/w05_law.json || fail "w05_law"
git show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_shard_manifest_v1.json > /tmp/p4inputs/shard_manifest.json || fail "shard_manifest"
git show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_shard_v1.jsonl > /tmp/p4inputs/shard.jsonl || fail "shard"
git show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_training_visible_pack_v1.json > /tmp/p4inputs/pack.json || fail "pack"
git show abb94ef134e2e97036b6959dbc9db4278d3736b6:research/weight_factory/agent02/gene1_split_commitment_v1.json > /tmp/p4inputs/split.json || fail "split"

cd "$REPO/research/weight_factory/agent03" || fail "cd_agent03"
python p4_gene1_trainer.py freeze-plan   --method-spec /tmp/p4inputs/w01.json   --training-shard-manifest /tmp/p4inputs/shard_manifest.json   --training-shard /tmp/p4inputs/shard.jsonl   --training-pack /tmp/p4inputs/pack.json   --split /tmp/p4inputs/split.json   --w02-binding /tmp/p4inputs/w02_binding.json   --w05-law /tmp/p4inputs/w05_law.json   --output /tmp/p4inputs/generated_plan.json | tee -a "$LOG" || fail "freeze_plan"
diff -u p4_frozen_training_plan_v1.json /tmp/p4inputs/generated_plan.json >> "$LOG" || fail "plan_diff"

python p4_surrogate_tournament.py prepare-data   --training-shard /tmp/p4inputs/shard.jsonl   --training-pack /tmp/p4inputs/pack.json   --output-dir "$DATA" | tee -a "$LOG" || fail "prepare_data"

cd "$REPO" || fail "cd_repo_patch"
python research/weight_factory/agent03/p4_patch_sdpo_transformers5_compat.py | tee -a "$LOG" || fail "sdpo_patch"
python - <<'PY' | tee -a "$LOG" || exit 2
import hashlib
from pathlib import Path
expected={
"/workspace/SDPO/verl/utils/model.py":"135f61865fcbe057d29da90bf07968b04dd778e2e96a31d3ad640a8650155f8d",
"/workspace/SDPO/verl/workers/fsdp_workers.py":"e0ec49a1b891daed8f180a35f5d1d7e5147a3a8289c3787fc7688892e0e55fed"}
for p,w in expected.items():
    g=hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert g==w,(p,g,w)
print("PATCH_SHA_PASS")
PY

python - <<'PY' | tee -a "$LOG" || fail "model_download"
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Qwen/Qwen3.5-4B-Base",
 revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
 local_dir="/workspace/models/qwen35-4b-daa9c16f3712")
print("MODEL_STAGE_PASS")
PY

cd "$REPO/research/weight_factory/agent03" || fail "cd_preflight"
python p4_surrogate_tournament.py check-runtime --sdpo-root "$SDPO" | tee -a "$LOG" || fail "runtime_check"

python - <<'PY' | tee -a "$LOG" || fail "authorization_check"
import json
from pathlib import Path
import p4_gene1_trainer as c
import p4_surrogate_tournament as t
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path("p4_a1_runpod_manager_authorization_retry10_v1.json").read_text())
assert run["manifest_sha256"]=="7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45"
assert lock["lock_sha256"]=="f1d05b53d0e00b07f7f4d60c90a6bf489f4cd2bd118b2b6a6b38c66026cee44e"
assert auth["authorization_sha256"]=="f4dabdc756872cc81e723bc700349d44104126a0e169b23407099d2d03cb47a8"
argv=t.build_a1_argv(Path("p4_frozen_training_plan_v1.json"),Path("/workspace"))
assert argv==lock["argv"]
assert c.canonical_sha256(argv)==run["command_sha256"]
errors=c.validate_manager_authorization(auth,lock=lock,run_manifest_sha256=run["manifest_sha256"])
assert not errors,errors
print("RETRY10_EXACT_AUTHORIZATION_PASS")
PY

ELAPSED=$(( $(date +%s) - START_TS ))
REMAIN=$(( SCRIPT_BUDGET - ELAPSED ))
if (( REMAIN < 180 )); then fail "insufficient_time_remaining:${REMAIN}s"; fi
if (( REMAIN > 900 )); then REMAIN=900; fi

echo "A1_TRAINING_START remaining_timeout=${REMAIN}s $(date -u +%FT%TZ)" | tee -a "$LOG"
set +o pipefail
timeout --signal=TERM --kill-after=20s "${REMAIN}s" python - <<'PY' 2>&1 | tee -a "$LOG"
import json
from pathlib import Path
import p4_gene1_trainer as c
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path("p4_a1_runpod_manager_authorization_retry10_v1.json").read_text())
raise SystemExit(c.run_locked(lock,paid=True,authorization=auth,run_manifest_sha256=run["manifest_sha256"],cwd=Path("/workspace/MUS-AI")))
PY
RC=${PIPESTATUS[0]}
set -o pipefail

echo "AQLEVON_A1_EXIT_CODE=$RC" | tee -a "$LOG"
find /workspace/aqlevon_p4/runs -maxdepth 5 -type f 2>/dev/null | sort | tail -80 | tee -a "$LOG"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader | tee -a "$LOG" || true
echo "AQLEVON_R10_END $(date -u +%FT%TZ) elapsed=$(( $(date +%s)-START_TS ))s" | tee -a "$LOG"
exit "$RC"
