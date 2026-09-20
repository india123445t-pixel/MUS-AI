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
AUTH_FILE="${AQLEVON_AUTH_FILE:?AQLEVON_AUTH_FILE is required}"
BINDING_FILE="${AQLEVON_BINDING_FILE:?AQLEVON_BINDING_FILE is required}"
EXPECTED_IMAGE_DIGEST="${AQLEVON_EXPECTED_IMAGE_DIGEST:?AQLEVON_EXPECTED_IMAGE_DIGEST is required}"

echo "AQLEVON_APPLIANCE_LAUNCH_START $(date -u +%FT%TZ)"
echo "AQLEVON_EXPECTED_IMAGE_DIGEST=$EXPECTED_IMAGE_DIGEST"

test -d "$SDPO_IMAGE/.git" || { echo "FAIL_CLOSED_APPLIANCE_SDPO_MISSING"; exit 40; }
python /opt/aqlevon/runtime/smoke_runtime.py --build-check --gpu-check

if [ ! -d "$REPO/.git" ]; then
  git clone -q --branch agent/03-p4-gene1-physical-trainer --single-branch https://github.com/india123445t-pixel/MUS-AI.git "$REPO"
fi
git -C "$REPO" fetch -q origin agent/03-p4-gene1-physical-trainer
git -C "$REPO" checkout -q agent/03-p4-gene1-physical-trainer
git -C "$REPO" reset -q --hard origin/agent/03-p4-gene1-physical-trainer
ACTUAL_HEAD="$(git -C "$REPO" rev-parse HEAD)"
echo "MUS_AI_HEAD=$ACTUAL_HEAD"
test "$ACTUAL_HEAD" = "$EXPECTED_HEAD" || { echo "FAIL_CLOSED_WRONG_HEAD"; exit 41; }

AGENT="$REPO/research/weight_factory/agent03"
RUN="$AGENT/p4_a1_seed1701_run_manifest_v1.json"
LOCK="$AGENT/p4_a1_seed1701_command_lock_v1.json"
PLAN="$AGENT/p4_frozen_training_plan_v1.json"
AUTH="$AGENT/$AUTH_FILE"
BINDING="$AGENT/$BINDING_FILE"
test -f "$AUTH" || { echo "FAIL_CLOSED_AUTH_FILE_MISSING=$AUTH_FILE"; exit 42; }
test -f "$BINDING" || { echo "FAIL_CLOSED_BINDING_FILE_MISSING=$BINDING_FILE"; exit 44; }

rm -rf "$SDPO"
ln -s "$SDPO_IMAGE" "$SDPO"
rm -rf "$ROOT/aqlevon_p4"
mkdir -p "$DATA" "$MODEL" /tmp/p4inputs

python - <<'PY'
import json, os, sys
from pathlib import Path
agent=Path("/workspace/MUS-AI/research/weight_factory/agent03")
sys.path.insert(0,str(agent))
import p4_gene1_trainer as c
auth=json.loads((agent/os.environ["AQLEVON_AUTH_FILE"]).read_text())
binding=json.loads((agent/os.environ["AQLEVON_BINDING_FILE"]).read_text())
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

RUNTIME_SOURCE="$(python - <<'PY'
import json, os
from pathlib import Path
agent=Path("/workspace/MUS-AI/research/weight_factory/agent03")
b=json.loads((agent/os.environ["AQLEVON_BINDING_FILE"]).read_text())
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

python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
 repo_id="Qwen/Qwen3.5-4B-Base",
 revision="daa9c16f371249f9ad1c75a9ed6f956c08ea08f5",
 local_dir="/workspace/models/qwen35-4b-daa9c16f3712",
)
print("MODEL_STAGE_PASS")
PY

python - <<'PY'
import json, os
from pathlib import Path
import p4_gene1_trainer as c
import p4_surrogate_tournament as t
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path(os.environ["AQLEVON_AUTH_FILE"]).read_text())
assert run["manifest_sha256"]=="24e3d21155c3f1011ca92f90e6c622fe03f92bfd65656d31d87fa627886fad47"
assert lock["lock_sha256"]=="b07441e07d0f26191fc5bd20ebf61e61c88003c542205687a2679243d90623c2"
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
assert not c.validate_command_seed_binding(argv,arm_id=lock["arm_id"],seed=lock["seed"])
print("APPLIANCE_SEED1701_BINDING_PASS")
errors=c.validate_manager_authorization(auth,lock=lock,run_manifest_sha256=run["manifest_sha256"])
assert not errors, errors
print("APPLIANCE_EXACT_AUTHORIZATION_PASS",auth["authorization_sha256"])
PY

ELAPSED="$(( $(date +%s) - START_TS ))"
if [ "$ELAPSED" -ge 720 ]; then
  echo "FAIL_CLOSED staging consumed ${ELAPSED}s; refusing training"
  exit 43
fi

echo "A1_LOCKED_TRAINING_START elapsed=${ELAPSED}s"

set +e
timeout --signal=TERM --kill-after=20s 900s \
python - <<'PY' 2>&1 | tee "$ROOT/aqlevon_p4/P4_A1_seed1701_appliance.log"
import json, os
from pathlib import Path
import p4_gene1_trainer as c
run=json.loads(Path("p4_a1_seed1701_run_manifest_v1.json").read_text())
lock=json.loads(Path("p4_a1_seed1701_command_lock_v1.json").read_text())
auth=json.loads(Path(os.environ["AQLEVON_AUTH_FILE"]).read_text())
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
echo "AQLEVON_APPLIANCE_TOTAL_SCRIPT_SECONDS=$(( $(date +%s) - START_TS ))"
exit "$RC"
