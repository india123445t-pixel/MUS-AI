#!/usr/bin/env bash
set -uo pipefail

ROOT=/workspace/auth16
HTTP_DIR="$ROOT/http"
MODEL_DIR=/workspace/models/qwen35-4b-daa9c16
SOURCE_HEAD=22b95b0fdfaf97c3ba3314a94c2413d45439cc6e
SOURCE_BLOB=cb86e6494fada78328310dfe5900e75205862ee0
W02_HEAD=abb94ef134e2e97036b6959dbc9db4278d3736b6
RECOVERY_HEAD=529e665ea140c2f8d6b96c02a42c100e9075c037
MODEL_REV=daa9c16f371249f9ad1c75a9ed6f956c08ea08f5
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
 "kind":"AQLEVON_AUTH16_HTTP_BOOTSTRAP_STATUS_V1",
 "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "stage":os.environ["STAGE"],
 "rc":int(os.environ["RC"]) if os.environ.get("RC","").isdigit() else None,
 "detail":os.environ.get("DETAIL",""),
 "worker05_used_for_tuning":False,
 "sealed_eval_consumed":False
}
for name in ("candidate_artifact_manifest.json","training_run_receipt.json"):
 q=root/"candidate"/name
 if q.exists():
  try:
   d=json.loads(q.read_text())
   if name.startswith("candidate"):
    out["candidate_status"]=d.get("candidate_status")
    out["public_shadow_gate_pass"]=d.get("public_shadow_gate_pass")
    out["manifest_sha256"]=d.get("manifest_sha256")
    out["adapter_model_sha256"]=d.get("adapter_model_sha256")
   else:
    out["optimizer_updates"]=d.get("optimizer_updates")
    out["discovery_dev_gate_pass"]=d.get("discovery_dev_gate_pass")
    out["dev_pre_successes"]=d.get("dev_pre_successes")
    out["dev_post_successes"]=d.get("dev_post_successes")
    out["dev_gain_tasks"]=d.get("dev_gain_tasks")
    out["dev_improvement"]=d.get("dev_improvement")
    out["shadow_pre_successes"]=d.get("shadow_pre_successes")
    out["shadow_post_successes"]=d.get("shadow_post_successes")
    out["shadow_gain_tasks"]=d.get("shadow_gain_tasks")
    out["shadow_improvement"]=d.get("shadow_improvement")
  except Exception as e: out["parse_error"]=repr(e)
tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n"); tmp.replace(p)
PY
}

package_evidence() {
  python3 - "$ROOT" <<'PY'
import tarfile,sys
from pathlib import Path
root=Path(sys.argv[1]); out=root/"http"/"evidence.tgz"
members=[x for x in ("candidate","train.log","hardware.txt","versions.txt","materializer.log","preflight.log","input") if (root/x).exists()]
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
assert free>=70000,free
assert torch.cuda.is_available()
assert torch.cuda.is_bf16_supported()
print("AQLEVON_AUTH16_HARDWARE_PASS",free,flush=True)
PY
  python3 - <<'PY' >"$ROOT/versions.txt"
import torch,transformers,peft,accelerate
print("torch",torch.__version__)
print("transformers",transformers.__version__)
print("peft",peft.__version__)
print("accelerate",accelerate.__version__)
PY

  write_status INPUT_STAGING 0 downloading_public_inputs
  curl -fsSL "$RAW/$SOURCE_HEAD/research/weight_factory/agent03/p4_one_day_synthetic_curriculum.py" -o "$ROOT/input/candidate.py"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_training_visible_pack_v1.json" -o "$ROOT/input/public-pack.json"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_data_verifier_pack_v1.py" -o "$ROOT/input/w02.py"
  curl -fsSL "$RAW/$RECOVERY_HEAD/research/weight_factory/agent03/p4_one_day_recovered_materializer.py" -o "$ROOT/input/materializer.py"
  curl -fsSL "$RAW/$RECOVERY_HEAD/research/weight_factory/agent03/auth05_recovered_material_decision.json" -o "$ROOT/input/recovered.json"
  python3 - "$ROOT/input/candidate.py" "$SOURCE_BLOB" <<'PY'
import hashlib,sys
p=open(sys.argv[1],"rb").read()
git_blob=hashlib.sha1(b"blob "+str(len(p)).encode()+b"\0"+p).hexdigest()
assert git_blob==sys.argv[2],(git_blob,sys.argv[2])
print("AQLEVON_AUTH16_SOURCE_BLOB_PASS",git_blob,flush=True)
PY
  python3 -m py_compile "$ROOT/input/candidate.py" "$ROOT/input/materializer.py" "$ROOT/input/w02.py"
  python3 "$ROOT/input/materializer.py" --recovered-decision "$ROOT/input/recovered.json" --training-pack "$ROOT/input/public-pack.json" --output "$ROOT/input/probe.json" >"$ROOT/materializer.log"
  grep -q 'train_targets=6 shadow_targets=0' "$ROOT/materializer.log"
  python3 "$ROOT/input/candidate.py" --probe-result "$ROOT/input/probe.json" --w02-module "$ROOT/input/w02.py" --training-pack "$ROOT/input/public-pack.json" --preflight-only >"$ROOT/preflight.log"
  grep -q 'AQLEVON_SYNTH_PUBLIC_PREFLIGHT_PASS synthetic=672 dev=28 shadow=28 families=14 updates=672 probe_decision=MATERIAL_LATENT_CAPABILITY' "$ROOT/preflight.log"

  write_status MODEL_DOWNLOAD 0 qwen35_4b
  python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Qwen/Qwen3.5-4B-Base",revision="$MODEL_REV",local_dir="$MODEL_DIR")
print("AQLEVON_AUTH16_MODEL_STAGED",flush=True)
PY

  write_status TRAINING 0 synthetic_672
  timeout --signal=TERM --kill-after=20s 1200s python3 "$ROOT/input/candidate.py" \
    --probe-result "$ROOT/input/probe.json" \
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
  tailmsg="$(tail -n 3 "$ROOT/train.log" 2>/dev/null | tr '\n' ' ' | cut -c1-600)"
  write_status FAILED "$rc" "$tailmsg"
fi
sync
# Keep the HTTP proxy alive long enough for the control plane to retrieve evidence.
sleep 900
kill "$HTTP_PID" 2>/dev/null || true
exit "$rc"
