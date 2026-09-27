#!/usr/bin/env bash
set -euo pipefail

ROOT=/workspace/aqlevon-auth08-eval
MODEL_DIR=/workspace/models/qwen38-27b-1d4bf0
STATUS="$ROOT/status.json"
TRANSFER_CODE="${AQLEVON_TRANSFER_CODE:-}"
EXPECTED_BUNDLE_SHA="${AQLEVON_BUNDLE_SHA256:-}"
SOURCE_SHA="${AQLEVON_SOURCE_SHA:-}"

mkdir -p "$ROOT"
cd "$ROOT"

write_status() {
  local stage="$1"; shift
  python3 - "$STATUS" "$stage" "$@" <<'PY'
import json,sys,time,os,tempfile
path=sys.argv[1]; stage=sys.argv[2]; detail=" ".join(sys.argv[3:])
obj={"kind":"AQLEVON_AUTH08_UNIFIED_PUBLIC_EVAL_STATUS_V1","stage":stage,"detail":detail,"updated_at":time.time()}
fd,tmp=tempfile.mkstemp(prefix="status.",dir=os.path.dirname(path))
with os.fdopen(fd,"w") as f:
    json.dump(obj,f,sort_keys=True); f.write("\n"); f.flush(); os.fsync(f.fileno())
os.replace(tmp,path)
PY
}

fail() {
  rc=$?
  write_status FAILED "rc=$rc"
  exit "$rc"
}
trap fail ERR

write_status BOOT "source=$SOURCE_SHA"
python3 -m http.server 8000 --directory "$ROOT" >/tmp/aqeval-http.log 2>&1 &

test -n "$TRANSFER_CODE"
test -n "$EXPECTED_BUNDLE_SHA"
test -n "$SOURCE_SHA"

RUNPODCTL_URL="https://github.com/runpod/runpodctl/releases/latest/download/runpodctl-linux-amd64"
for attempt in 1 2 3 4 5; do
  if curl -fL --retry 2 --retry-all-errors --connect-timeout 10 --max-time 90 "$RUNPODCTL_URL" -o /tmp/runpodctl; then
    break
  fi
  rm -f /tmp/runpodctl
  sleep $((attempt * 2))
done
test -s /tmp/runpodctl
install -m 0755 /tmp/runpodctl /usr/local/bin/runpodctl

write_status RECEIVE_BUNDLE
runpodctl receive "$TRANSFER_CODE"
BUNDLE="$(find "$ROOT" -maxdepth 1 -type f -name 'aqlevon-auth08-eval-bundle*.tgz' | head -n1)"
test -n "$BUNDLE"
ACTUAL_BUNDLE_SHA="$(sha256sum "$BUNDLE" | awk '{print $1}')"
test "$ACTUAL_BUNDLE_SHA" = "$EXPECTED_BUNDLE_SHA"
mkdir -p "$ROOT/bundle"
tar -xzf "$BUNDLE" -C "$ROOT/bundle"

test -f "$ROOT/bundle/adapter/adapter_model.safetensors"
test -f "$ROOT/bundle/candidate_manifest.json"
test -f "$ROOT/bundle/auth08-generalization-manifest.json"
test -f "$ROOT/bundle/auth08-generalization-results-skeleton.json"
test -f "$ROOT/bundle/auth08-paired-public-execution-plan.json"
test -f "$ROOT/bundle/auth08-paired-public-binding.json"
test -f "$ROOT/bundle/auth08_unified_public_eval_runner_v1.py"
test -f "$ROOT/bundle/aqlevon_27b_public_generalization_challenge_v1.py"

ADAPTER_SHA="$(sha256sum "$ROOT/bundle/adapter/adapter_model.safetensors" | awk '{print $1}')"
test "$ADAPTER_SHA" = "5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74"

write_status HARDWARE
nvidia-smi >"$ROOT/hardware.txt"
python3 - <<'PY' >"$ROOT/runtime-versions-pre.txt"
import platform
import torch,transformers,peft,huggingface_hub,safetensors
print("python="+platform.python_version())
print("torch="+torch.__version__)
print("torch_cuda="+str(torch.version.cuda))
print("transformers="+transformers.__version__)
print("peft="+peft.__version__)
print("huggingface_hub="+huggingface_hub.__version__)
print("safetensors="+safetensors.__version__)
assert torch.cuda.is_available()
assert torch.cuda.is_bf16_supported()
PY

write_status STAGING_MODEL
mkdir -p "$MODEL_DIR"
MODEL_DIR="$MODEL_DIR" python3 - <<'PY'
import os
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="Qwen/Qwen3.8-27B",
    revision="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
    local_dir=os.environ["MODEL_DIR"],
)
print("AQLEVON_AUTH08_BASE_STAGED",flush=True)
PY

write_status INFERENCE_START
rm -rf "$ROOT/results"
PYTHONUNBUFFERED=1 python3 "$ROOT/bundle/auth08_unified_public_eval_runner_v1.py"   --model-dir "$MODEL_DIR"   --adapter-dir "$ROOT/bundle/adapter"   --candidate-manifest "$ROOT/bundle/candidate_manifest.json"   --challenge-module "$ROOT/bundle/aqlevon_27b_public_generalization_challenge_v1.py"   --generalization-manifest "$ROOT/bundle/auth08-generalization-manifest.json"   --generalization-skeleton "$ROOT/bundle/auth08-generalization-results-skeleton.json"   --paired-plan "$ROOT/bundle/auth08-paired-public-execution-plan.json"   --paired-binding "$ROOT/bundle/auth08-paired-public-binding.json"   --output-dir "$ROOT/results"   --status-path "$STATUS"   2>&1 | tee "$ROOT/eval.log"

test -f "$ROOT/results/generalization-results.json"
test -f "$ROOT/results/paired-public-results.jsonl"
test -f "$ROOT/results/runtime-receipt.json"

write_status PACKAGING
tar -czf "$ROOT/evidence.tgz"   -C "$ROOT"   status.json hardware.txt runtime-versions-pre.txt eval.log results bundle/candidate_manifest.json   bundle/auth08-generalization-manifest.json bundle/auth08-paired-public-binding.json
sha256sum "$ROOT/evidence.tgz" >"$ROOT/evidence.sha256"
write_status DONE "$(cat "$ROOT/evidence.sha256")"
trap - ERR
echo AQLEVON_AUTH08_UNIFIED_EVAL_BOOTSTRAP_DONE
