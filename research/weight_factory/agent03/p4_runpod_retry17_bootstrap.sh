#!/usr/bin/env bash
set -euo pipefail

START_TS="$(date +%s)"
ROOT=/workspace
REPO="$ROOT/MUS-AI"
SDPO="$ROOT/SDPO"
DATA="$ROOT/aqlevon_p4/data"
MODEL="$ROOT/models/qwen35-4b-daa9c16f3712"
AGENT="$REPO/research/weight_factory/agent03"
AUTH="$AGENT/p4_a1_runpod_manager_authorization_retry17_v1.json"
RUN="$AGENT/p4_a1_seed1701_run_manifest_v1.json"
LOCK="$AGENT/p4_a1_seed1701_command_lock_v1.json"
PLAN="$AGENT/p4_frozen_training_plan_v1.json"

echo "AQLEVON_RETRY17_BOOTSTRAP_START $(date -u +%FT%TZ)"
if [ ! -d "$REPO/.git" ]; then
  git clone -q --branch agent/03-p4-gene1-physical-trainer --single-branch https://github.com/india123445t-pixel/MUS-AI.git "$REPO"
fi
git -C "$REPO" fetch -q origin agent/03-p4-gene1-physical-trainer
git -C "$REPO" checkout -q agent/03-p4-gene1-physical-trainer
git -C "$REPO" reset -q --hard origin/agent/03-p4-gene1-physical-trainer
echo "MUS_AI_HEAD=$(git -C "$REPO" rev-parse HEAD)"

GPU_COUNT="$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l | tr -d ' ')"
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1 | xargs)"
test "$GPU_COUNT" = "1"
case "$GPU_NAME" in
  *RTX\ 4090*) ;;
  *) echo "FAIL_CLOSED unexpected GPU: $GPU_NAME"; exit 20 ;;
esac
echo "GPU_PASS $GPU_NAME"

python - <<'PY'
import json
from pathlib import Path
a=json.loads(Path("/workspace/MUS-AI/research/weight_factory/agent03/p4_a1_runpod_manager_authorization_retry17_v1.json").read_text())
assert a["authorization_id"]=="P4-A1-RUNPOD-4090-20260920-17-FLASHATTN-VERL-REPAIR"
assert a["authorization_sha256"]=="aea8d26d5cadd94e9c7364f8c23129d99aa8c2d2de5e4ceb65d2ebb5ec2cf869"
assert a["max_billed_seconds"]==1800
assert a["max_total_cost_usd"]=="0.40"
assert a["max_hourly_rate_usd"]=="0.80"
assert a["single_use"] is True
print("RETRY17_FILE_IDENTITY_PASS")
PY

rm -rf "$SDPO" "$ROOT/aqlevon_p4" "$MODEL"
mkdir -p "$DATA" "$MODEL" /tmp/p4inputs

git clone -q https://github.com/lasgroup/SDPO.git "$SDPO"
git -C "$SDPO" checkout -q 7c457fc1b1f636ae794eb0362ba37d4743b06fbc

# Retry17 repair 1: make the pinned SDPO/verl package importable for the driver and Ray workers.
python -m pip install -q --disable-pip-version-check --no-deps -e "$SDPO"
python - <<'PY'
import verl
assert verl.__file__.startswith("/workspace/SDPO/verl/"), verl.__file__
print("VERL_EDITABLE_IMPORT_PASS", verl.__file__)
PY

python -m pip install -q --disable-pip-version-check \
  transformers==5.17.0 peft==0.21.0 accelerate==1.15.0 \
  pyarrow==22.0.0 qwen-vl-utils==0.0.14 hydra-core==1.3.2 \
  "ray[default]==2.53.0" vllm==0.10.2 \
  torchdata==0.11.0 tensordict==0.10.0 datasets==4.4.2 \
  codetiming==1.4.0 safetensors psutil huggingface-hub pillow

# Retry17 repair 2: exact official FlashAttention2 wheel for the frozen torch/Python runtime.
python - <<'PY'
import sys, torch
assert sys.version_info[:2] == (3, 12), sys.version
assert torch.__version__.split("+")[0] == "2.8.0", torch.__version__
assert torch.version.cuda and torch.version.cuda.startswith("12.8"), torch.version.cuda
abi = bool(torch._C._GLIBCXX_USE_CXX11_ABI)
print("FLASH_ATTN_RUNTIME_IDENTITY_PASS", torch.__version__, torch.version.cuda, "CXX11ABI="+str(abi))
PY

FA_ABI="$(python - <<'PY'
import torch
print("TRUE" if torch._C._GLIBCXX_USE_CXX11_ABI else "FALSE")
PY
)"
case "$FA_ABI" in
  TRUE)
    FA_SHA="f25da18657a87fc83dc1bfb8b7751b82246e9db355510226b674fd437c34b5fb"
    ;;
  FALSE)
    FA_SHA="2605b2653e7b9d6615bbb154896ae4d3f0b95d3120af7a6374ee97092e61df02"
    ;;
  *) echo "FAIL_CLOSED unknown torch CXX11 ABI: $FA_ABI"; exit 24 ;;
esac
FA_NAME="flash_attn-2.8.3+cu12torch2.8cxx11abi${FA_ABI}-cp312-cp312-linux_x86_64.whl"
FA_URL="https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3%2Bcu12torch2.8cxx11abi${FA_ABI}-cp312-cp312-linux_x86_64.whl"
FA_PATH="/tmp/$FA_NAME"
curl -fL --retry 3 --retry-delay 2 -o "$FA_PATH" "$FA_URL"
echo "$FA_SHA  $FA_PATH" | sha256sum -c -
python -m pip install -q --disable-pip-version-check --no-deps "$FA_PATH"
python - <<'PY'
import flash_attn
from flash_attn import flash_attn_func
assert flash_attn.__version__ == "2.8.3", flash_attn.__version__
print("FLASH_ATTN_IMPORT_PASS", flash_attn.__version__)
PY

# Cheap fail-fast GPU compatibility probe matching Qwen3.5 full-attention head_dim=256, BF16, causal, no dropout.
python - <<'PY'
import torch
from flash_attn import flash_attn_func
assert torch.cuda.is_available()
assert "RTX 4090" in torch.cuda.get_device_name(0), torch.cuda.get_device_name(0)
q=torch.randn((1,16,16,256),device="cuda",dtype=torch.bfloat16,requires_grad=True)
k=torch.randn((1,16,4,256),device="cuda",dtype=torch.bfloat16,requires_grad=True)
v=torch.randn((1,16,4,256),device="cuda",dtype=torch.bfloat16,requires_grad=True)
out=flash_attn_func(q,k,v,dropout_p=0.0,causal=True)
out.float().sum().backward()
torch.cuda.synchronize()
assert q.grad is not None and k.grad is not None and v.grad is not None
print("FLASH_ATTN_4090_BF16_HD256_FWD_BWD_PASS", tuple(out.shape))
PY
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

python p4_gene1_trainer.py freeze-plan \
  --method-spec /tmp/p4inputs/w01.json \
  --training-shard-manifest /tmp/p4inputs/shard_manifest.json \
  --training-shard /tmp/p4inputs/shard.jsonl \
  --training-pack /tmp/p4inputs/pack.json \
  --split /tmp/p4inputs/split.json \
  --w02-binding /tmp/p4inputs/w02_binding.json \
  --w05-law /tmp/p4inputs/w05_law.json \
  --output /tmp/p4inputs/generated_plan.json

diff -u "$PLAN" /tmp/p4inputs/generated_plan.json

python p4_surrogate_tournament.py prepare-data \
  --training-shard /tmp/p4inputs/shard.jsonl \
  --training-pack /tmp/p4inputs/pack.json \
  --output-dir "$DATA"

cd "$REPO"
python research/weight_factory/agent03/p4_patch_sdpo_transformers5_compat.py

python - <<'PY'
import hashlib
from pathlib import Path
expected={
 "/workspace/SDPO/verl/utils/model.py":"135f61865fcbe057d29da90bf07968b04dd778e2e96a31d3ad640a8650155f8d",
 "/workspace/SDPO/verl/workers/fsdp_workers.py":"e0ec49a1b891daed8f180a35f5d1d7e5147a3a8289c3787fc7688892e0e55fed",
}
for p,w in expected.items():
    g=hashlib.sha256(Path(p).read_bytes()).hexdigest()
    assert g==w,(p,g,w)
print("SDPO_PATCH_SHA_PASS")
PY

python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
 repo_id="Qwen/Qwen3.5-4B-Base",
 revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
 local_dir="/workspace/models/qwen35-4b-daa9c16f3712",
)
print("MODEL_STAGE_PASS")
PY

cd "$AGENT"
python p4_surrogate_tournament.py check-runtime --sdpo-root "$SDPO"

python - <<'PY'
import json
from pathlib import Path
import p4_gene1_trainer as c
import p4_surrogate_tournament as t
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path("p4_a1_runpod_manager_authorization_retry17_v1.json").read_text())
assert run["manifest_sha256"]=="7152cdea6ffd082f632a819e153122b401bd7394ed0273a327537ca961c7fe45"
assert lock["lock_sha256"]=="f1d05b53d0e00b07f7f4d60c90a6bf489f4cd2bd118b2b6a6b38c66026cee44e"
assert c.verify_self_digest(auth,"authorization_sha256")
argv=t.build_a1_argv(Path("p4_frozen_training_plan_v1.json"),Path("/workspace"))
assert argv==lock["argv"]
assert c.canonical_sha256(argv)==run["command_sha256"]
errors=c.validate_manager_authorization(auth,lock=lock,run_manifest_sha256=run["manifest_sha256"])
assert not errors, errors
print("RETRY17_EXACT_AUTHORIZATION_PASS")
PY

ELAPSED="$(( $(date +%s) - START_TS ))"
if [ "$ELAPSED" -ge 720 ]; then
  echo "FAIL_CLOSED staging consumed ${ELAPSED}s; refusing training to protect 1800s authorization"
  exit 31
fi

echo "A1_LOCKED_TRAINING_START elapsed=${ELAPSED}s"

set +e
timeout --signal=TERM --kill-after=20s 900s \
python - <<'PY' 2>&1 | tee "$ROOT/aqlevon_p4/P4_A1_seed1701_retry17.log"
import json
from pathlib import Path
import p4_gene1_trainer as c
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path("p4_a1_runpod_manager_authorization_retry17_v1.json").read_text())
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

echo "AQLEVON_A1_EXIT_CODE=$RC"
find "$ROOT/aqlevon_p4/runs" -maxdepth 5 -type f -printf '%p %s bytes\\n' 2>/dev/null | tail -n 100 || true
echo "AQLEVON_RETRY17_TOTAL_SCRIPT_SECONDS=$(( $(date +%s) - START_TS ))"
exit "$RC"
