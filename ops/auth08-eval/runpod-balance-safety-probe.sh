#!/usr/bin/env bash
set -euo pipefail
test -n "${RUNPOD_API_KEY:-}"
cat >/tmp/q.json <<'JSON'
{"query":"query { myself { clientBalance currentSpendPerHr underBalance pods { id name desiredStatus volumeInGb containerDiskInGb networkVolumeId costPerHr adjustedCostPerHr memoryInGb vcpuCount } networkVolumes { id name size dataCenterId } dailyCharges { amount diskCharges podCharges apiCharges serverlessCharges type updatedAt } } }"}
JSON
curl -fsS -X POST -H "content-type: application/json" \
  --url "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  --data-binary @/tmp/q.json >/tmp/inventory.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/inventory.json"))
assert not d.get("errors"), d
me=d["data"]["myself"]
out={
 "clientBalance":me.get("clientBalance"),
 "currentSpendPerHr":me.get("currentSpendPerHr"),
 "underBalance":me.get("underBalance"),
 "pods":me.get("pods") or [],
 "networkVolumes":me.get("networkVolumes") or [],
 "dailyCharges":(me.get("dailyCharges") or [])[-20:]
}
print("AQLEVON_RUNPOD_RESOURCE_INVENTORY",json.dumps(out,sort_keys=True))
PY


cat >/tmp/gpu-market.json <<'JSON'
{"query":"query { gpuTypes { id displayName memoryInGb secureCloud communityCloud lowestPrice(input: { gpuCount: 2 }) { stockStatus minimumBidPrice uninterruptablePrice } } }"}
JSON
curl -fsS -X POST -H "content-type: application/json" \
  --url "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  --data-binary @/tmp/gpu-market.json >/tmp/gpu-market-out.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/gpu-market-out.json"))
if d.get("errors"):
    print("AQLEVON_RUNPOD_GPU_MARKET_QUERY_ERROR",json.dumps(d["errors"],sort_keys=True))
else:
    rows=[]
    for g in d.get("data",{}).get("gpuTypes") or []:
        name=(g.get("displayName") or "")
        if any(x in name.upper() for x in ["A6000","A40","A100"]):
            rows.append(g)
    print("AQLEVON_RUNPOD_GPU_MARKET",json.dumps(rows,sort_keys=True))
PY
