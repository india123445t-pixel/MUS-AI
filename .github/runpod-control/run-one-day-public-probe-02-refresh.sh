#!/usr/bin/env bash
set -euo pipefail
AUTH=".github/runpod-control/one-day-public-probe-manager-authorization-02-20260925.json"
FREE=".github/runpod-control/one-day-public-probe-free-result-02.json"
curl -sSL https://cli.runpod.net | sudo bash >/dev/null
runpodctl gpu list --output json >/tmp/wrapper-gpus.json
python3 - <<'PY'
import json
from pathlib import Path
a=json.loads(Path(".github/runpod-control/one-day-public-probe-manager-authorization-02-20260925.json").read_text())
f=json.loads(Path(".github/runpod-control/one-day-public-probe-free-result-02.json").read_text())
allowed=set(a["permitted_gpu_ids"]); choices=[]
for g in json.load(open("/tmp/wrapper-gpus.json")):
    gid=str(g.get("gpuId",""))
    if gid not in allowed or not g.get("secureCloud"): continue
    price=float(g.get("securePricePerHr") or 999)
    if price>float(a["max_hourly_rate_usd"]): continue
    for d in (g.get("dataCenterAvailability") or []):
        if str(d.get("stockStatus")).lower()!="none":
            choices.append((price,gid,d.get("dataCenterId")))
assert choices,"no_permitted_gpu_stock_now"
price,gpu,dc=sorted(choices)[0]
f["selected_gpu_id"]=gpu
f["selected_datacenter"]=dc
f["selected_price_hr"]=price
f["selection_refreshed_locally_at_paid_boundary"]=True
Path(".github/runpod-control/one-day-public-probe-free-result-02.json").write_text(json.dumps(f,indent=2,sort_keys=True)+"\n")
print("AQLEVON_ONE_DAY_LOCAL_SELECTION_REFRESH",gpu,dc,price)
PY
exec bash .github/runpod-control/run-one-day-public-probe-02.sh
