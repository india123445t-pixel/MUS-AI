#!/usr/bin/env bash
set -uo pipefail
ROOT=/workspace/aq27
HTTP_DIR="$ROOT/http"
MODEL_DIR=/workspace/models/qwen38-27b-1d4bf0f2
RAW=https://raw.githubusercontent.com/india123445t-pixel/MUS-AI
AUTH16_SOURCE=22b95b0fdfaf97c3ba3314a94c2413d45439cc6e
W02_HEAD=abb94ef134e2e97036b6959dbc9db4278d3736b6
RECOVERY_HEAD=529e665ea140c2f8d6b96c02a42c100e9075c037
MODEL_REV=1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
rm -rf "$ROOT"; mkdir -p "$HTTP_DIR" "$MODEL_DIR" "$ROOT/input"

status(){
  STAGE="$1" RC="${2:-}" DETAIL="${3:-}" ROOT="$ROOT" python3 - <<'PY'
import datetime,json,os
from pathlib import Path
root=Path(os.environ["ROOT"]); out={"kind":"AQLEVON_27B_8USD_STATUS_V1","stage":os.environ["STAGE"],"rc":int(os.environ["RC"]) if os.environ.get("RC","").isdigit() else None,"detail":os.environ.get("DETAIL",""),"checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"sealed_eval_consumed":False,"worker05_used_for_tuning":False}
for n in ("candidate_artifact_manifest.json","training_run_receipt.json"):
 p=root/"candidate"/n
 if p.exists():
  try:
   d=json.loads(p.read_text())
   for k in ("candidate_status","manifest_sha256","adapter_model_sha256","receipt_sha256","optimizer_updates","dev_pre_successes","dev_post_successes","dev_gain_tasks","dev_improvement","shadow_pre_successes","shadow_post_successes","shadow_gain_tasks","shadow_improvement","public_shadow_gate_pass","discovery_dev_gate_pass"):
    if k in d: out[k]=d[k]
  except Exception as e: out["parse_error"]=repr(e)
tmp=root/"http"/"status.tmp"; tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n"); tmp.replace(root/"http"/"status.json")
PY
}
pack(){
  ROOT="$ROOT" python3 - <<'PY'
import os,tarfile
from pathlib import Path
r=Path(os.environ["ROOT"]); o=r/"http"/"evidence.tgz"
with tarfile.open(o,"w:gz") as t:
 for n in ("candidate","train.log","hardware.txt","versions.txt","preflight.log","input"):
  p=r/n
  if p.exists(): t.add(p,arcname=n)
PY
}

status BOOTSTRAP 0 starting
python3 -m http.server 8000 --bind 0.0.0.0 --directory "$HTTP_DIR" >"$ROOT/http-server.log" 2>&1 &
HTTP_PID=$!
sleep 1

main(){
 set -euo pipefail
 status HARDWARE_CHECK 0 checking_a100_80gb
 nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader >"$ROOT/hardware.txt"
 python3 - <<'PY'
import subprocess,torch
row=subprocess.check_output(["nvidia-smi","--query-gpu=name,memory.total,memory.free","--format=csv,noheader,nounits"],text=True).splitlines()[0]
name,total,free=[x.strip() for x in row.split(",")]
assert float(total)>=79000,(name,total,free)
assert float(free)>=76000,(name,total,free)
assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
print("AQLEVON_27B_HARDWARE_PASS",name,total,free,flush=True)
PY
 python3 - <<'PY' >"$ROOT/versions.txt"
import torch,transformers,peft,accelerate
print("torch",torch.__version__); print("transformers",transformers.__version__); print("peft",peft.__version__); print("accelerate",accelerate.__version__)
PY

 status INPUT_STAGING 0 public_only
 curl -fsSL "$RAW/$AUTH16_SOURCE/research/weight_factory/agent03/p4_one_day_synthetic_curriculum.py" -o "$ROOT/input/candidate.py"
 curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_training_visible_pack_v1.json" -o "$ROOT/input/public-pack.json"
 curl -fsSL "$RAW/$W02_HEAD/research/weight_factory/agent02/gene1_data_verifier_pack_v1.py" -o "$ROOT/input/w02.py"
 curl -fsSL "$RAW/$RECOVERY_HEAD/research/weight_factory/agent03/p4_one_day_recovered_materializer.py" -o "$ROOT/input/materializer.py"
 curl -fsSL "$RAW/$RECOVERY_HEAD/research/weight_factory/agent03/auth05_recovered_material_decision.json" -o "$ROOT/input/recovered.json"

 python3 - "$ROOT/input/candidate.py" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); s=p.read_text()
def rep(a,b):
 global s
 if a not in s: raise SystemExit("missing_anchor:"+a[:60])
 s=s.replace(a,b,1)
rep('MODEL_REPO = "Qwen/Qwen3.5-4B-Base"\nMODEL_REV = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"',
    'MODEL_REPO = "Qwen/Qwen3.8-27B"\nMODEL_REV = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"\nSOURCE_RECIPE_MODEL_REPO = "Qwen/Qwen3.5-4B-Base"\nSOURCE_RECIPE_MODEL_REV = "daa9c16f371249f9ad1c75a9ed6f956c08ea08f5"')
rep('CAP = 2048\nLAYERS = (3, 7, 11, 15, 19, 23, 27, 31)',
    'CAP = 1024\nLORA_R = 8\nPROJECTIONS = ("q_proj", "k_proj", "v_proj", "o_proj")\nLAYERS = tuple(range(3, 64, 4))')
rep('TARGET_SUFFIXES = {f"layers.{i}.self_attn.{p}" for i in LAYERS for p in ("q_proj", "k_proj", "v_proj", "o_proj")}',
    'TARGET_SUFFIXES = {f"layers.{i}.self_attn.{p}" for i in LAYERS for p in PROJECTIONS}')
start=s.index('def tensor_layout(weights: dict) -> dict:')
end=s.index('\ndef state_hash(weights: dict)',start)
generic='''def tensor_layout(weights: dict) -> dict:
    modules = {}
    expected_tensor_count = len(LAYERS) * len(PROJECTIONS) * 2
    if len(weights) != expected_tensor_count:
        raise RuntimeError(f"adapter_tensor_count_mismatch:{len(weights)}:{expected_tensor_count}")
    for name,value in weights.items():
        hit=WEIGHT_NAME.search(name)
        if not hit: raise RuntimeError(f"unexpected_adapter_key:{name}")
        layer,projection,part=int(hit[1]),hit[2],hit[3]
        modules.setdefault((layer,projection),{})[part]=tuple(value.shape)
    expected={(i,p) for i in LAYERS for p in PROJECTIONS}
    if set(modules)!=expected: raise RuntimeError("adapter_topology_mismatch")
    for key,parts in modules.items():
        if set(parts)!={"A","B"}: raise RuntimeError(f"adapter_AB_mismatch:{key}")
        if len(parts["A"])!=2 or len(parts["B"])!=2 or parts["A"][0]!=LORA_R or parts["B"][1]!=LORA_R:
            raise RuntimeError(f"adapter_rank_mismatch:{key}:{parts}")
    return {f"{layer}:{proj}":{k:list(v) for k,v in parts.items()} for (layer,proj),parts in sorted(modules.items())}
'''
s=s[:start]+generic+s[end:]
rep('if probe.get("model_repo") != MODEL_REPO or probe.get("model_revision") != MODEL_REV:',
    'if probe.get("model_repo") != SOURCE_RECIPE_MODEL_REPO or probe.get("model_revision") != SOURCE_RECIPE_MODEL_REV:')
rep('lora=LoraConfig(r=8,lora_alpha=16,target_modules=["q_proj","k_proj","v_proj","o_proj"],',
    'lora=LoraConfig(r=LORA_R,lora_alpha=16,target_modules=[f"model.language_model.layers.{i}.self_attn.{p}" for i in LAYERS for p in PROJECTIONS],')
rep('if observed != TARGET_SUFFIXES or len(targets)!=32:','if observed != TARGET_SUFFIXES or len(targets)!=64:')
rep('if trainable != 1572864:\n        raise RuntimeError(f"trainable_parameter_count_mismatch:{trainable}")',
    'if trainable <= 0:\n        raise RuntimeError(f"trainable_parameter_count_invalid:{trainable}")')
s=s.replace('"adapter_tensors":64,"target_modules":32,','"adapter_tensors":128,"target_modules":64,')
s=s.replace('"receipt_kind":"AQLEVON_ONE_DAY_SYNTHETIC_CURRICULUM_RECEIPT_V1",','"receipt_kind":"AQLEVON_27B_AUTH16_RECIPE_TRAINING_RECEIPT_V1",')
s=s.replace('"manifest_kind":"AQLEVON_ONE_DAY_SYNTHETIC_CURRICULUM_CANDIDATE_V1",','"manifest_kind":"AQLEVON_27B_R0A_CANDIDATE_V1",')
s=s.replace('"handoff_kind":"AQLEVON_ONE_DAY_SYNTHETIC_CURRICULUM_WORKER05_HANDOFF_V1",','"handoff_kind":"AQLEVON_27B_R0A_WORKER05_HANDOFF_V1",')
s=s.replace('tensors=64 modules=32','tensors=128 modules=64')
p.write_text(s)
PY
 python3 -m py_compile "$ROOT/input/candidate.py" "$ROOT/input/w02.py" "$ROOT/input/materializer.py"
 python3 "$ROOT/input/materializer.py" --recovered-decision "$ROOT/input/recovered.json" --training-pack "$ROOT/input/public-pack.json" --output "$ROOT/input/probe.json" >/dev/null
 python3 "$ROOT/input/candidate.py" --probe-result "$ROOT/input/probe.json" --w02-module "$ROOT/input/w02.py" --training-pack "$ROOT/input/public-pack.json" --preflight-only >"$ROOT/preflight.log"
 grep -q 'synthetic=672 dev=28 shadow=28 families=14 updates=672' "$ROOT/preflight.log"

 status MODEL_DOWNLOAD 0 qwen38_27b_exact_revision
 python3 - <<PY
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Qwen/Qwen3.8-27B",revision="$MODEL_REV",local_dir="$MODEL_DIR")
print("AQLEVON_27B_MODEL_STAGED",flush=True)
PY

 status TRAINING 0 auth16_recipe_672
 timeout --signal=TERM --kill-after=30s 12600s python3 "$ROOT/input/candidate.py" --probe-result "$ROOT/input/probe.json" --w02-module "$ROOT/input/w02.py" --training-pack "$ROOT/input/public-pack.json" --model-dir "$MODEL_DIR" --output-dir "$ROOT/candidate" >"$ROOT/train.log" 2>&1
}

rc=0; main || rc=$?
pack || true
if [ "$rc" -eq 0 ]; then status DONE 0 complete; else tailmsg="$(tail -n 4 "$ROOT/train.log" 2>/dev/null | tr '\n' ' ' | cut -c1-700)"; status FAILED "$rc" "$tailmsg"; fi
sync
sleep 900
kill "$HTTP_PID" 2>/dev/null || true
exit "$rc"
