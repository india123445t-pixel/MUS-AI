#!/usr/bin/env bash
set -uo pipefail

ROOT=/workspace/aqlevon27b
HTTP_DIR=$ROOT/http
MODEL_DIR=/workspace/models/qwen38-27b
INPUT_DIR=$ROOT/input
CANDIDATE_DIR=$ROOT/candidate
RAW=https://raw.githubusercontent.com/india123445t-pixel/MUS-AI
TRAINER_COMMIT=6718cc94bfcaeac1c52f2755d04f1872e339eea2
TRAINER_SHA=652800806cac005981b059a24888e5ba65e2be6b117f98de24da42822e59aad9
W02_HEAD=abb94ef134e2e97036b6959dbc9db4278d3736b6
MODEL_REV=1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0

rm -rf "$ROOT"
mkdir -p "$HTTP_DIR" "$MODEL_DIR" "$INPUT_DIR"

write_status() {
  stage="$1"
  rc="${2:-}"
  detail="${3:-}"
  STAGE="$stage" RC="$rc" DETAIL="$detail" ROOT="$ROOT" python3 - <<'PY'
import datetime,json,os
from pathlib import Path
root=Path(os.environ["ROOT"])
p=root/"http"/"status.json"
tmp=p.with_suffix(".tmp")
out={
  "kind":"AQLEVON_27B_R0_HTTP_STATUS_V2",
  "checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "stage":os.environ["STAGE"],
  "rc":int(os.environ["RC"]) if os.environ.get("RC","").isdigit() else None,
  "detail":os.environ.get("DETAIL",""),
  "sealed_eval_consumed":False,
  "worker05_used_for_tuning":False
}
for name in ("candidate_artifact_manifest.json","training_run_receipt.json"):
    q=root/"candidate"/name
    if q.exists():
        try:
            d=json.loads(q.read_text())
            if name.startswith("candidate"):
                out["candidate_status"]=d.get("candidate_status")
                out["model_name"]=d.get("model_name")
                out["public_retention_gate_pass"]=d.get("public_retention_gate_pass")
                out["public_gain_observed"]=d.get("public_gain_observed")
                out["adapter_model_sha256"]=d.get("adapter_model_sha256")
                out["manifest_sha256"]=d.get("manifest_sha256")
            else:
                out["optimizer_updates"]=d.get("optimizer_updates")
                out["dev_pre_successes"]=d.get("dev_pre_successes")
                out["dev_post_successes"]=d.get("dev_post_successes")
                out["shadow_pre_successes"]=d.get("shadow_pre_successes")
                out["shadow_post_successes"]=d.get("shadow_post_successes")
        except Exception as e:
            out["parse_error"]=repr(e)
tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
tmp.replace(p)
PY
}

package_evidence() {
  python3 - "$ROOT" <<'PY'
import tarfile,sys
from pathlib import Path
root=Path(sys.argv[1])
out=root/"http"/"evidence.tgz"
members=[n for n in ("candidate","train.log","hardware.txt","versions.txt","download.log","input") if (root/n).exists()]
with tarfile.open(out,"w:gz") as t:
    for n in members:
        t.add(root/n,arcname=n)
print("AQLEVON_27B_EVIDENCE_READY",out.stat().st_size,flush=True)
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
row=subprocess.check_output(
    ["nvidia-smi","--query-gpu=name,memory.total,memory.free","--format=csv,noheader,nounits"],
    text=True
).strip().splitlines()
assert len(row)==1,row
parts=[x.strip() for x in row[0].split(",")]
name,total,free=parts[0],float(parts[1]),float(parts[2])
assert "A100" in name,(name,total,free)
assert total>=77824,(name,total,free)
assert torch.cuda.is_available()
assert torch.cuda.is_bf16_supported()
print("AQLEVON_27B_HARDWARE_PASS",name,total,free,flush=True)
PY
  python3 - <<'PY' >"$ROOT/versions.txt"
import torch,transformers,peft,accelerate
print("torch",torch.__version__)
print("transformers",transformers.__version__)
print("peft",peft.__version__)
print("accelerate",accelerate.__version__)
PY

  write_status INPUT_STAGING 0 exact_sources
  curl -fsSL "$RAW/$TRAINER_COMMIT/research/weight_factory/agent03/aqlevon_27b_r0_gene1.py.gz" -o "$INPUT_DIR/trainer.py.gz"
  gzip -t "$INPUT_DIR/trainer.py.gz"
  gzip -dc "$INPUT_DIR/trainer.py.gz" >"$INPUT_DIR/trainer.py"
  test "$(sha256sum "$INPUT_DIR/trainer.py" | awk '{print $1}')" = "$TRAINER_SHA"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_training_visible_pack_v1.json" -o "$INPUT_DIR/public-pack.json"
  curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_data_verifier_pack_v1.py" -o "$INPUT_DIR/w02.py"
  python3 -m py_compile "$INPUT_DIR/trainer.py" "$INPUT_DIR/w02.py"
  python3 - "$INPUT_DIR/public-pack.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
assert p["pack_sha256"]=="35c7ebe6d5e82f42d7553fa28391f6d82c8800d6eced582d06881c8eb17d9d6b"
assert len(p["tasks"])>=56
print("AQLEVON_27B_INPUT_PASS",len(p["tasks"]),flush=True)
PY

  write_status MODEL_DOWNLOAD 0 qwen38_27b_exact_revision
  python3 - <<PY >"$ROOT/download.log" 2>&1
from huggingface_hub import snapshot_download
p=snapshot_download(
    repo_id="Qwen/Qwen3.8-27B",
    revision="$MODEL_REV",
    local_dir="$MODEL_DIR"
)
print("AQLEVON_27B_MODEL_STAGED",p,flush=True)
PY

  write_status TRAINING 0 coverage_first_budgeted
  timeout --signal=TERM --kill-after=30s 11800s \
    python3 "$INPUT_DIR/trainer.py" \
      --w02-module "$INPUT_DIR/w02.py" \
      --training-pack "$INPUT_DIR/public-pack.json" \
      --model-dir "$MODEL_DIR" \
      --output-dir "$CANDIDATE_DIR" \
      --train-budget-seconds 8200 \
      >"$ROOT/train.log" 2>&1
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
  tailmsg="$(tail -n 5 "$ROOT/train.log" 2>/dev/null | tr '\n' ' ' | cut -c1-800)"
  if [ -z "$tailmsg" ]; then
    tailmsg="$(tail -n 5 "$ROOT/download.log" 2>/dev/null | tr '\n' ' ' | cut -c1-800)"
  fi
  write_status FAILED "$rc" "$tailmsg"
fi
sync
sleep 900
kill "$HTTP_PID" 2>/dev/null || true
exit "$rc"
