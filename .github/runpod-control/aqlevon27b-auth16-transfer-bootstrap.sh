#!/usr/bin/env bash
set -uo pipefail

ROOT=/workspace/aqlevon27b
HTTP_DIR="$ROOT/http"
MODEL_DIR=/workspace/models/qwen38-27b-1d4bf0f
SOURCE_COMMIT=372d049efb8f60ef8bd5b5c86d540abab9a8f77d
SOURCE_BLOB=33c51c1e43aa834f41753b7067aaf4b8e19e7835
W02_HEAD=abb94ef134e2e97036b6959dbc9db4278d3736b6
RECOVERY_HEAD=529e665ea140c2f8d6b96c02a42c100e9075c037
MODEL_REPO=Qwen/Qwen3.8-27B
MODEL_REV=1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
RAW=https://raw.githubusercontent.com/india123445t-pixel/MUS-AI

rm -rf "$ROOT"
mkdir -p "$HTTP_DIR" "$MODEL_DIR" "$ROOT/input"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
export HF_XET_HIGH_PERFORMANCE=1

write_status() {
  local stage="$1"; local rc="${2:-}"; local detail="${3:-}"
  STAGE="$stage" RC="$rc" DETAIL="$detail" ROOT="$ROOT" python3 - <<'PY'
import datetime,json,os
from pathlib import Path
root=Path(os.environ["ROOT"]); p=root/"http"/"status.json"; tmp=p.with_suffix(".tmp")
out={
 "kind":"AQLEVON_27B_AUTH16_TRANSFER_STATUS_V1",
 "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "stage":os.environ["STAGE"],
 "rc":int(os.environ["RC"]) if os.environ.get("RC","").isdigit() else None,
 "detail":os.environ.get("DETAIL",""),
 "lane":"AQLEVON_27B_AUTH16_TRANSFER_V1",
 "sealed_eval_consumed":False,
 "worker05_used_for_tuning":False,
 "capability_gain_claim":False
}
for name in ("candidate_artifact_manifest.json","training_run_receipt.json"):
 q=root/"candidate"/name
 if q.exists():
  try:
   d=json.loads(q.read_text())
   if name.startswith("candidate"):
    for k in ("candidate_status","public_shadow_gate_pass","manifest_sha256","adapter_model_sha256","adapter_state_sha256"):
     out[k]=d.get(k)
   else:
    for k in ("optimizer_updates","trainable_parameters","discovery_dev_gate_pass","dev_pre_successes","dev_post_successes","dev_gain_tasks","dev_improvement","shadow_pre_successes","shadow_post_successes","shadow_gain_tasks","shadow_improvement"):
     out[k]=d.get(k)
  except Exception as e: out["parse_error"]=repr(e)
tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n"); tmp.replace(p)
PY
}

package_evidence() {
  python3 - "$ROOT" <<'PY'
import tarfile,sys
from pathlib import Path
root=Path(sys.argv[1]); out=root/"http"/"evidence.tgz"
members=[x for x in ("candidate","train.log","hardware.txt","versions.txt","materializer.log","preflight.log","input","disk.txt") if (root/x).exists()]
with tarfile.open(out,"w:gz") as t:
    for name in members: t.add(root/name,arcname=name)
PY
}

write_status BOOTSTRAP 0 starting
python3 -m http.server 8000 --bind 0.0.0.0 --directory "$HTTP_DIR" >"$ROOT/http-server.log" 2>&1 &
HTTP_PID=$!
sleep 1

main() {
  set -euo pipefail
  write_status HARDWARE_CHECK 0 checking_a100_80gb
  nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader >"$ROOT/hardware.txt"
  df -h /workspace >"$ROOT/disk.txt" || true
  python3 - <<'PY'
import subprocess,torch
free=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True).splitlines()[0])
total=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.total","--format=csv,noheader,nounits"],text=True).splitlines()[0])
assert total>=79000,(total,free)
assert free>=76000,(total,free)
assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
print("AQLEVON_27B_HARDWARE_PASS",total,free,flush=True)
PY
  python3 - <<'PY' >"$ROOT/versions.txt"
import torch,transformers,peft,accelerate
print("torch",torch.__version__)
print("transformers",transformers.__version__)
print("peft",peft.__version__)
print("accelerate",accelerate.__version__)
PY

  write_status INPUT_STAGING 0 public_inputs_only
  curl -fsSL "$RAW/$SOURCE_COMMIT/research/weight_factory/agent03/p4_one_day_synthetic_curriculum.py" -o "$ROOT/input/candidate.py"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_training_visible_pack_v1.json" -o "$ROOT/input/public-pack.json"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_data_verifier_pack_v1.py" -o "$ROOT/input/w02.py"
  curl -fsSL "$RAW/$RECOVERY_HEAD/research/weight_factory/agent03/p4_one_day_recovered_materializer.py" -o "$ROOT/input/materializer.py"
  curl -fsSL "$RAW/$RECOVERY_HEAD/research/weight_factory/agent03/auth05_recovered_material_decision.json" -o "$ROOT/input/recovered.json"
  python3 - "$ROOT/input/candidate.py" "$SOURCE_BLOB" <<'PY'
import hashlib,sys
p=open(sys.argv[1],"rb").read()
git_blob=hashlib.sha1(b"blob "+str(len(p)).encode()+b"\0"+p).hexdigest()
assert git_blob==sys.argv[2],(git_blob,sys.argv[2])
print("AQLEVON_27B_SOURCE_BLOB_PASS",git_blob,flush=True)
PY
  python3 -m py_compile "$ROOT/input/candidate.py" "$ROOT/input/materializer.py" "$ROOT/input/w02.py"
  python3 "$ROOT/input/materializer.py" --recovered-decision "$ROOT/input/recovered.json" --training-pack "$ROOT/input/public-pack.json" --output "$ROOT/input/probe.json" >"$ROOT/materializer.log"
  grep -q 'train_targets=6 shadow_targets=0' "$ROOT/materializer.log"
  python3 - "$ROOT/input/probe.json" <<'PY'
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding="utf-8"))
d["model_repo"]="Qwen/Qwen3.8-27B"
d["model_revision"]="1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
with open(p,"w",encoding="utf-8") as f: json.dump(d,f,indent=2,sort_keys=True); f.write("\n")
print("AQLEVON_27B_PROBE_REBOUND_PUBLIC_ONLY",flush=True)
PY
  python3 "$ROOT/input/candidate.py" --probe-result "$ROOT/input/probe.json" --w02-module "$ROOT/input/w02.py" --training-pack "$ROOT/input/public-pack.json" --preflight-only >"$ROOT/preflight.log"
  grep -q 'synthetic=672 dev=28 shadow=28 families=14 updates=672' "$ROOT/preflight.log"

  write_status MODEL_DOWNLOAD 0 qwen38_27b_exact_revision
  python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download(repo_id="$MODEL_REPO",revision="$MODEL_REV",local_dir="$MODEL_DIR")
print("AQLEVON_27B_MODEL_STAGED",flush=True)
PY

  write_status TRAINING 0 auth16_recipe_transfer_672
  timeout --signal=TERM --kill-after=30s 10800s python3 "$ROOT/input/candidate.py" \
    --probe-result "$ROOT/input/probe.json" \
    --w02-module "$ROOT/input/w02.py" \
    --training-pack "$ROOT/input/public-pack.json" \
    --model-dir "$MODEL_DIR" \
    --output-dir "$ROOT/candidate" >"$ROOT/train.log" 2>&1
}

rc=0
main || rc=$?
package_evidence || { [ "$rc" -ne 0 ] || rc=91; }
if [ "$rc" -eq 0 ]; then
  write_status DONE 0 complete
else
  tailmsg="$(tail -n 6 "$ROOT/train.log" 2>/dev/null | tr '\n' ' ' | cut -c1-900)"
  write_status FAILED "$rc" "$tailmsg"
fi
sync
sleep 900
kill "$HTTP_PID" 2>/dev/null || true
exit "$rc"
