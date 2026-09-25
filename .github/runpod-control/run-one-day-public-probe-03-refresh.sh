#!/usr/bin/env bash
set -euo pipefail

BASE_DRIVER=".github/runpod-control/run-one-day-public-probe-02.sh"
AUTH03=".github/runpod-control/one-day-public-probe-manager-authorization-03-20260925.json"
FREE03=".github/runpod-control/one-day-public-probe-free-result-03.json"
TMP_DRIVER="/tmp/run-one-day-public-probe-03.sh"

python3 - <<'PY'
from pathlib import Path
p=Path(".github/runpod-control/run-one-day-public-probe-02.sh").read_text()
repls={
"P4-ONE-DAY-PUBLIC-PASSN-20260925-02":"P4-ONE-DAY-PUBLIC-PASSN-20260925-03",
"430ae3149249d9522aa027a852bde786f5ef4a97d252781fea15080483e467c6":"062487f3de6bd60bafc269643bb40bb982eb39c05cfe9a99d28f3ee766098c03",
"one-day-public-probe-manager-authorization-02-20260925.json":"one-day-public-probe-manager-authorization-03-20260925.json",
"one-day-public-probe-free-result-02.json":"one-day-public-probe-free-result-03.json",
"execute-one-day-public-probe-02.json":"execute-one-day-public-probe-03.json",
"one-day-public-probe-consumed-02.json":"one-day-public-probe-consumed-03.json",
"one-day-public-probe-run-result-02.json":"one-day-public-probe-run-result-03.json",
"AQLEVON-ONE-DAY-PASSN-02-20260925":"AQLEVON-ONE-DAY-PASSN-03-20260925",
}
for a,b in repls.items():
    p=p.replace(a,b)
p=p.replace(
    'git pull --rebase origin ops/one-day-verified-trajectory-20260925 || die consumed_rebase_failed\n',
    ': # auth03: no post-create rebase\n'
)
p=p.replace(
    'git pull --rebase origin ops/one-day-verified-trajectory-20260925 || true\n',
    ': # auth03: no post-create rebase\n'
)
needle='echo "AQLEVON_ONE_DAY_POD_CREATED $pod"\n'
trap=r'''echo "AQLEVON_ONE_DAY_POD_CREATED $pod"
emergency_stop_on_exit() {
  status=$?
  if [ "$status" -ne 0 ] && [ -n "${pod:-}" ]; then
    echo "AQLEVON_AUTH03_EXIT_TRAP_STOP pod=$pod status=$status"
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/auth03-exit-trap-stop.json || true
  fi
  return "$status"
}
trap emergency_stop_on_exit EXIT
'''
assert needle in p
p=p.replace(needle,trap,1)
Path("/tmp/run-one-day-public-probe-03.sh").write_text(p)
print("AQLEVON_AUTH03_DRIVER_GENERATED")
PY
bash -n "$TMP_DRIVER"
grep -q 'one-day-public-probe-consumed-03.json' "$TMP_DRIVER"
grep -q 'AQLEVON_AUTH03_EXIT_TRAP_STOP' "$TMP_DRIVER"
if [ "${AQLEVON_FREE_CONTRACT_ONLY:-0}" = 1 ]; then
  echo AQLEVON_AUTH03_GENERATED_DRIVER_FREE_CONTRACT_PASS
  exit 0
fi

curl -sSL https://cli.runpod.net | sudo bash >/dev/null
runpodctl gpu list --output json >/tmp/auth03-gpus.json
python3 - <<'PY'
import datetime,json
from pathlib import Path
a=json.loads(Path(".github/runpod-control/one-day-public-probe-manager-authorization-03-20260925.json").read_text())
f=json.loads(Path(".github/runpod-control/one-day-public-probe-free-result-03.json").read_text())
t=json.loads(Path(".github/runpod-control/execute-one-day-public-probe-03.json").read_text()) if Path(".github/runpod-control/execute-one-day-public-probe-03.json").exists() else {}
excluded={tuple(x) for x in t.get("failed_capacity_pairs",[])}
allowed=set(a["permitted_gpu_ids"]); choices=[]
for g in json.load(open("/tmp/auth03-gpus.json")):
    gid=str(g.get("gpuId",""))
    if gid not in allowed or not g.get("secureCloud"): continue
    price=float(g.get("securePricePerHr") or 999)
    if price>float(a["max_hourly_rate_usd"]): continue
    for d in (g.get("dataCenterAvailability") or []):
        dc=d.get("dataCenterId")
        if str(d.get("stockStatus")).lower()!="none" and (gid,dc) not in excluded:
            choices.append((price,gid,dc))
assert choices,"no_permitted_gpu_stock_now"
price,gpu,dc=sorted(choices)[0]
dynamic=min(int(a["max_billed_seconds"]),int(float(a["max_total_cost_usd"])*3600/price))
assert dynamic>=600,(gpu,price,dynamic)
f.update({
    "selected_gpu_id":gpu,
    "selected_datacenter":dc,
    "selected_price_hr":price,
    "dynamic_max_billed_seconds":dynamic,
    "paid_boundary_refresh_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "paid_boundary_refresh_committed_before_pod":True,
})
Path(".github/runpod-control/one-day-public-probe-free-result-03.json").write_text(json.dumps(f,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH03_LIVE_SELECTION",gpu,dc,price,dynamic)
PY

git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$FREE03"
if ! git diff --cached --quiet; then
  git commit -m "ops: persist auth03 live GPU selection before spend [skip ci]"
  git push origin HEAD:ops/one-day-verified-trajectory-20260925
fi
test -z "$(git status --porcelain)" || { git status --porcelain; echo FAIL_CLOSED_AUTH03_DIRTY_TREE_BEFORE_POD; exit 1; }

exec bash "$TMP_DRIVER"
