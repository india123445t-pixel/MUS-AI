#!/usr/bin/env bash
set -euo pipefail
test -n "${RUNPOD_API_KEY:-}"
cat >/tmp/q.json <<'JSON'
{"query":"query { pod(input: { podId: \"hjwspv5aqtnqxd\" }) { id desiredStatus gpuCount memoryInGb vcpuCount machineId volumeInGb volumeMountPath networkVolumeId machine { id memoryTotal memoryReserved vcpuTotal vcpuReserved gpuAvailable dataCenterId } } }"}
JSON
curl -fsS -X POST -H "content-type: application/json" \
  --url "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  --data-binary @/tmp/q.json >/tmp/pod-host.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/pod-host.json"))
assert not d.get("errors"), d
p=d["data"]["pod"]
m=p.get("machine") or {}
out={
 "pod_id":p.get("id"),
 "desiredStatus":p.get("desiredStatus"),
 "pod_memoryInGb":p.get("memoryInGb"),
 "pod_vcpuCount":p.get("vcpuCount"),
 "machineId":p.get("machineId"),
 "volumeInGb":p.get("volumeInGb"),
 "volumeMountPath":p.get("volumeMountPath"),
 "networkVolumeId":p.get("networkVolumeId"),
 "machine_memoryTotal":m.get("memoryTotal"),
 "machine_memoryReserved":m.get("memoryReserved"),
 "machine_vcpuTotal":m.get("vcpuTotal"),
 "machine_vcpuReserved":m.get("vcpuReserved"),
 "machine_gpuAvailable":m.get("gpuAvailable"),
 "dataCenterId":m.get("dataCenterId")
}
mt, mr = out["machine_memoryTotal"], out["machine_memoryReserved"]
if isinstance(mt,(int,float)) and isinstance(mr,(int,float)):
    out["machine_memory_free_estimate"]=mt-mr
print("AQLEVON_AUTH02_HOST_READINESS",json.dumps(out,sort_keys=True))
PY
