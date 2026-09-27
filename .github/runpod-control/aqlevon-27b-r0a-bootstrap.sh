#!/usr/bin/env bash
set -uo pipefail

ROOT=/workspace/aqlevon27b
HTTP_DIR="$ROOT/http"
MODEL_DIR=/workspace/models/qwen38-27b-1d4bf0f2
SOURCE_HEAD="${AQLEVON_SOURCE_HEAD:?AQLEVON_SOURCE_HEAD required}"
TRAINER_BLOB="${AQLEVON_TRAINER_BLOB:?AQLEVON_TRAINER_BLOB required}"
W02_HEAD=abb94ef134e2e97036b6959dbc9db4278d3736b6
MODEL_REV=1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
RAW=https://raw.githubusercontent.com/india123445t-pixel/MUS-AI

rm -rf "$ROOT"
mkdir -p "$HTTP_DIR" "$MODEL_DIR" "$ROOT/input"

write_status() {
  local stage="$1"; local rc="${2:-}"; local detail="${3:-}"
  STAGE="$stage" RC="$rc" DETAIL="$detail" ROOT="$ROOT" python3 - <<'PY'
import datetime,json,os
from pathlib import Path
root=Path(os.environ["ROOT"]); p=root/"http"/"status.json"; tmp=p.with_suffix(".tmp")
out={
 "kind":"AQLEVON_27B_R0A_HTTP_BOOTSTRAP_STATUS_V1",
 "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "stage":os.environ["STAGE"],
 "rc":int(os.environ["RC"]) if os.environ.get("RC","").isdigit() else None,
 "detail":os.environ.get("DETAIL",""),
 "sealed_eval_consumed":False,
 "worker05_used_for_tuning":False,
}
q=root/"candidate"/"training_run_receipt.json"
if q.exists():
  try:
    d=json.loads(q.read_text())
    for k in ("candidate_status","public_gate_pass","discovery_dev_gate_pass","public_shadow_gate_pass",
              "selected_optimizer_updates","selected_phase","dev_pre_successes","dev_post_successes",
              "shadow_pre_successes","shadow_post_successes","adapter_model_sha256","receipt_sha256"):
      if k in d: out[k]=d[k]
  except Exception as e: out["parse_error"]=repr(e)
tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n"); tmp.replace(p)
PY
}

package_evidence() {
  python3 - "$ROOT" <<'PY'
import tarfile,sys
from pathlib import Path
root=Path(sys.argv[1]); out=root/"http"/"evidence.tgz"
members=[x for x in ("candidate","train.log","hardware.txt","versions.txt","download.log","preflight.log","input") if (root/x).exists()]
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
  write_status HARDWARE_CHECK 0 checking
  nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader >"$ROOT/hardware.txt"
  python3 - <<'PY'
import shutil,subprocess,torch
free=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True).splitlines()[0])
disk=shutil.disk_usage("/workspace")
assert free>=70000,("free_vram_mib",free)
assert disk.free>=65*1024**3,("free_disk_bytes",disk.free)
assert torch.cuda.is_available()
assert torch.cuda.is_bf16_supported()
print("AQLEVON_27B_HARDWARE_PASS",free,disk.free,flush=True)
PY
  python3 - <<'PY' >"$ROOT/versions.txt"
import torch,transformers,peft,accelerate
print("torch",torch.__version__)
print("transformers",transformers.__version__)
print("peft",peft.__version__)
print("accelerate",accelerate.__version__)
PY

  write_status INPUT_STAGING 0 downloading_public_inputs
  curl -fsSL "$RAW/$SOURCE_HEAD/research/weight_factory/agent03/p4_27b_progressive_curriculum.py" -o "$ROOT/input/trainer.py"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_training_visible_pack_v1.json" -o "$ROOT/input/public-pack.json"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_data_verifier_pack_v1.py" -o "$ROOT/input/w02.py"
  python3 - "$ROOT/input/trainer.py" "$TRAINER_BLOB" <<'PY'
import hashlib,sys
p=open(sys.argv[1],"rb").read()
git_blob=hashlib.sha1(b"blob "+str(len(p)).encode()+b"\0"+p).hexdigest()
assert git_blob==sys.argv[2],(git_blob,sys.argv[2])
print("AQLEVON_27B_SOURCE_BLOB_PASS",git_blob,flush=True)
PY
  python3 -m py_compile "$ROOT/input/trainer.py" "$ROOT/input/w02.py"
  python3 "$ROOT/input/trainer.py" --w02-module "$ROOT/input/w02.py" --training-pack "$ROOT/input/public-pack.json" --preflight-only >"$ROOT/preflight.log"
  grep -q 'AQLEVON_27B_PUBLIC_PREFLIGHT_PASS phases=\[168, 168, 168, 168\] max_updates=672 dev=28 shadow=28 families=14 sealed_eval=forbidden' "$ROOT/preflight.log"

  write_status MODEL_DOWNLOAD 0 qwen38_27b
  timeout --signal=TERM --kill-after=20s 2400s python3 - <<PY >"$ROOT/download.log" 2>&1
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Qwen/Qwen3.8-27B",revision="$MODEL_REV",local_dir="$MODEL_DIR",max_workers=8)
print("AQLEVON_27B_MODEL_STAGED",flush=True)
PY

  write_status TRAINING 0 progressive_public_curriculum
  timeout --signal=TERM --kill-after=30s 10800s python3 "$ROOT/input/trainer.py" \
    --w02-module "$ROOT/input/w02.py" \
    --training-pack "$ROOT/input/public-pack.json" \
    --model-dir "$MODEL_DIR" \
    --output-dir "$ROOT/candidate" >"$ROOT/train.log" 2>&1
}

rc=0
main || rc=$?
if [ "$rc" -eq 0 ]; then
  package_evidence || rc=91
else
  package_evidence || true
fi
if [ "$rc" -eq 0 ]; then
  write_status DONE 0 complete
else
  tailmsg="$(tail -n 4 "$ROOT/train.log" "$ROOT/download.log" "$ROOT/preflight.log" 2>/dev/null | tr '\n' ' ' | cut -c1-800)"
  write_status FAILED "$rc" "$tailmsg"
fi
sync
sleep 600
kill "$HTTP_PID" 2>/dev/null || true
exit "$rc"
