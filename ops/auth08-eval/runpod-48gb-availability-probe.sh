#!/usr/bin/env bash
set -euo pipefail
test -n "${RUNPOD_API_KEY:-}"
python3 - <<'PY'
import os,json,urllib.request
url="https://api.runpod.io/graphql"
q=r'''query {
  gpuTypes {
    id
    displayName
    memoryInGb
    lowestPrice(input:{gpuCount:1}) {
      gpuName
      gpuTypeId
      uninterruptablePrice
      minimumBidPrice
      stockStatus
      minMemory
      minVcpu
      minDisk
      totalCount
      rentedCount
      maxUnreservedGpuCount
      availableGpuCounts
    }
  }
  myself { clientBalance currentSpendPerHr underBalance }
}'''
req=urllib.request.Request(url,data=json.dumps({"query":q}).encode(),headers={
  "Authorization":"Bearer "+os.environ["RUNPOD_API_KEY"],
  "Content-Type":"application/json"
})
with urllib.request.urlopen(req,timeout=30) as r:
    d=json.load(r)
if d.get("errors"):
    raise SystemExit("graphql_errors:"+json.dumps(d["errors"])[:2000])
targets=[]
for g in d["data"]["gpuTypes"]:
    name=(g.get("displayName") or "")
    gid=(g.get("id") or "")
    mem=g.get("memoryInGb") or 0
    if mem>=48 and any(x in (name+" "+gid).upper() for x in ["A40","A6000","L40","RTX 6000 ADA"]):
        targets.append(g)
out={"kind":"AQLEVON_RUNPOD_48GB_AVAILABILITY_V1","account":d["data"]["myself"],"targets":targets}
print("AQLEVON_RUNPOD_48GB_AVAILABILITY "+json.dumps(out,separators=(",",":"),sort_keys=True))
PY
