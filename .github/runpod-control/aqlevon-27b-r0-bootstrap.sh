#!/usr/bin/env bash
set -uo pipefail
ROOT=/workspace/aqlevon27b
HTTP_DIR="$ROOT/http"
MODEL_DIR=/workspace/models/qwen38-27b-1d4bf0f
RAW=https://raw.githubusercontent.com/india123445t-pixel/MUS-AI
W02_HEAD=abb94ef134e2e97036b6959dbc9db4278d3736b6
MODEL_REV=1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
SOURCE_SHA="${AQLEVON_SOURCE_SHA:?missing AQLEVON_SOURCE_SHA}"
rm -rf "$ROOT"; mkdir -p "$HTTP_DIR" "$ROOT/input" "$MODEL_DIR"
write_status() {
  local stage="$1"; local rc="${2:-}"; local detail="${3:-}"
  STAGE="$stage" RC="$rc" DETAIL="$detail" ROOT="$ROOT" python3 - <<'PY'
import datetime,json,os
from pathlib import Path
root=Path(os.environ["ROOT"]); p=root/"http"/"status.json"; tmp=p.with_suffix(".tmp")
out={"kind":"AQLEVON_27B_R0_STATUS_V1","checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"stage":os.environ["STAGE"],"rc":int(os.environ["RC"]) if os.environ.get("RC","").isdigit() else None,"detail":os.environ.get("DETAIL",""),"sealed_eval_consumed":False,"worker05_used_for_tuning":False}
m=root/"candidate"/"candidate_manifest.json"
if m.exists():
    try: out.update(json.loads(m.read_text()))
    except Exception as e: out["parse_error"]=repr(e)
tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n"); tmp.replace(p)
PY
}
package_evidence() {
  python3 - "$ROOT" <<'PY'
import tarfile,sys
from pathlib import Path
root=Path(sys.argv[1]); out=root/"http"/"evidence.tgz"
members=[x for x in ("candidate","train.log","hardware.txt","versions.txt","input") if (root/x).exists()]
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
import subprocess,torch
free=float(subprocess.check_output(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True).splitlines()[0])
assert free>=76000,free
assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
print("AQLEVON_27B_HARDWARE_PASS",free,flush=True)
PY
  python3 - <<'PY' >"$ROOT/versions.txt"
import torch,transformers,peft,accelerate
print("torch",torch.__version__); print("transformers",transformers.__version__); print("peft",peft.__version__); print("accelerate",accelerate.__version__)
PY
  write_status INPUT_STAGING 0 public_only
  curl -fsSL "$RAW/$SOURCE_SHA/research/weight_factory/agent03/aqlevon_27b_r0_auth16_transfer.py" -o "$ROOT/input/trainer.py"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_data_verifier_pack_v1.py" -o "$ROOT/input/w02.py"
  python3 -m py_compile "$ROOT/input/trainer.py" "$ROOT/input/w02.py"
  write_status MODEL_DOWNLOAD 0 qwen38_27b
  python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Qwen/Qwen3.8-27B",revision="$MODEL_REV",local_dir="$MODEL_DIR")
print("AQLEVON_27B_MODEL_STAGED",flush=True)
PY
  write_status TRAINING 0 auth16_recipe_transfer
  timeout --signal=TERM --kill-after=30s 13500s python3 "$ROOT/input/trainer.py" --w02-module "$ROOT/input/w02.py" --model-dir "$MODEL_DIR" --output-dir "$ROOT/candidate" >"$ROOT/train.log" 2>&1
}
rc=0
main || rc=$?
package_evidence || true
if [ "$rc" -eq 0 ]; then write_status DONE 0 complete
else
  tailmsg="$(tail -n 5 "$ROOT/train.log" 2>/dev/null | tr '\n' ' ' | cut -c1-900)"
  write_status FAILED "$rc" "$tailmsg"
fi
sync
sleep 900
kill "$HTTP_PID" 2>/dev/null || true
exit "$rc"
