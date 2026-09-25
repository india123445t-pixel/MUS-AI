#!/usr/bin/env bash
set -euo pipefail

BASE_DRIVER=".github/runpod-control/run-one-day-public-probe-02.sh"
AUTH05=".github/runpod-control/one-day-public-probe-manager-authorization-05-20260925.json"
FREE04=".github/runpod-control/one-day-public-probe-free-result-05.json"
TMP_DRIVER="/tmp/run-one-day-public-probe-05.sh"

python3 - <<'PY'
from pathlib import Path
p=Path(".github/runpod-control/run-one-day-public-probe-02.sh").read_text()
repls={
"P4-ONE-DAY-PUBLIC-PASSN-20260925-02":"P4-ONE-DAY-PUBLIC-PASSN-20260925-05",
"430ae3149249d9522aa027a852bde786f5ef4a97d252781fea15080483e467c6":"187f4b4d17086e3352d873263787e717ac24e32096350a07e87c5816674bd859",
"one-day-public-probe-manager-authorization-02-20260925.json":"one-day-public-probe-manager-authorization-05-20260925.json",
"one-day-public-probe-free-result-02.json":"one-day-public-probe-free-result-05.json",
"execute-one-day-public-probe-02.json":"execute-one-day-public-probe-05.json",
"one-day-public-probe-consumed-02.json":"one-day-public-probe-consumed-05.json",
"one-day-public-probe-run-result-02.json":"one-day-public-probe-run-result-05.json",
"AQLEVON-ONE-DAY-PASSN-02-20260925":"AQLEVON-ONE-DAY-PASSN-05-20260925",
"AQLEVON_ONE_DAY_AUTH02_PRESPEND_PASS":"AQLEVON_ONE_DAY_AUTH05_PRESPEND_PASS",
"print(min(1200,int(1.20*3600/rate)))":"print(min(1800,int(1.00*3600/rate)))",
}
for a,b in repls.items():
    p=p.replace(a,b)
p=p.replace(
    'git pull --rebase origin ops/one-day-verified-trajectory-20260925 || die consumed_rebase_failed\n',
    ': # auth05: no post-create rebase\n'
)
p=p.replace(
    'git pull --rebase origin ops/one-day-verified-trajectory-20260925 || true\n',
    ': # auth05: no post-create rebase\n'
)
p=p.replace('REMOTE_SCRIPT=".github/runpod-control/remote-one-day-public-probe-02.sh"', 'REMOTE_SCRIPT=".github/runpod-control/remote-one-day-public-probe-v2.sh"', 1)
p=p.replace('assert float(a["prior_mission_spend_usd"])+float(a["max_total_cost_usd"]) < float(a["mission_max_total_usd"])', 'assert float(a["fresh_authorization_spend_before_auth05_usd"])+float(a["max_total_cost_usd"]) <= float(a["owner_fresh_mission_authorization_usd"])', 1)
p=p.replace('for i in $(seq 1 60); do', 'for i in $(seq 1 180); do', 1)
p=p.replace('[ "$elapsed" -lt 300 ] || break', '[ "$elapsed" -lt 900 ] || break', 1)
p=p.replace('rm -f /workspace/one_day_probe.rc; nohup setsid bash /tmp/run-one-day-probe.sh >/workspace/one_day_probe-supervisor.log 2>&1 < /dev/null &', 'mkdir -p /workspace; rm -f /workspace/one_day_probe.rc; nohup setsid bash /tmp/run-one-day-probe.sh >/workspace/one_day_probe-supervisor.log 2>&1 < /dev/null &', 1)
needle='echo "AQLEVON_ONE_DAY_POD_CREATED $pod"\n'
trap=r'''echo "AQLEVON_ONE_DAY_POD_CREATED $pod"
emergency_stop_on_exit() {
  status=$?
  if [ "$status" -ne 0 ] && [ -n "${pod:-}" ]; then
    echo "AQLEVON_AUTH05_EXIT_TRAP_STOP pod=$pod status=$status"
    curl -sS -X POST "https://rest.runpod.io/v1/pods/$pod/stop" -H "Authorization: Bearer $RUNPOD_API_KEY" -H 'Content-Type: application/json' -d '{}' >/tmp/auth05-exit-trap-stop.json || true
  fi
  return "$status"
}
trap emergency_stop_on_exit EXIT
'''
assert needle in p
p=p.replace(needle,trap,1)
assert 'one-day-public-probe-consumed-05.json' in p
assert 'P4-ONE-DAY-PUBLIC-PASSN-20260925-05' in p
assert 'seq 1 180' in p
assert '-lt 900' in p
assert 'min(1800,int(1.00*3600/rate))' in p
assert 'consumed_rebase_failed' not in p
assert 'remote-one-day-public-probe-v2.sh' in p
assert 'prior_mission_spend_usd' not in p
assert 'mkdir -p /workspace; rm -f /workspace/one_day_probe.rc' in p
Path("/tmp/run-one-day-public-probe-05.sh").write_text(p)
print("AQLEVON_AUTH05_DRIVER_GENERATED")
PY
bash -n "$TMP_DRIVER"
grep -q 'one-day-public-probe-consumed-05.json' "$TMP_DRIVER"
grep -q 'AQLEVON_AUTH05_EXIT_TRAP_STOP' "$TMP_DRIVER"
grep -q 'seq 1 180' "$TMP_DRIVER"
grep -q -- '-lt 900' "$TMP_DRIVER"
if [ "${AQLEVON_FREE_CONTRACT_ONLY:-0}" = 1 ]; then
  echo AQLEVON_AUTH05_GENERATED_DRIVER_FREE_CONTRACT_PASS
  exit 0
fi

curl -sSL https://cli.runpod.net | sudo bash >/dev/null
runpodctl gpu list --output json >/tmp/auth05-gpus.json
python3 - <<'PY'
import datetime,json
from pathlib import Path
a=json.loads(Path(".github/runpod-control/one-day-public-probe-manager-authorization-05-20260925.json").read_text())
f=json.loads(Path(".github/runpod-control/one-day-public-probe-free-result-05.json").read_text())
allowed=set(a["permitted_gpu_ids"]); choices=[]
for g in json.load(open("/tmp/auth05-gpus.json")):
    gid=str(g.get("gpuId",""))
    if gid not in allowed or not g.get("secureCloud"): continue
    price=float(g.get("securePricePerHr") or 999)
    if price>float(a["max_hourly_rate_usd"]): continue
    for d in (g.get("dataCenterAvailability") or []):
        if str(d.get("stockStatus")).lower()!="none":
            dynamic=min(int(a["max_billed_seconds"]),int(float(a["max_total_cost_usd"])*3600/price))
            choices.append((price,gid,d.get("dataCenterId"),dynamic))
assert choices,"no_permitted_gpu_stock_now"
price,gpu,dc,dynamic=sorted(choices)[0]
assert dynamic>=1200,(gpu,price,dynamic)
f.update({
    "selected_gpu_id":gpu,
    "selected_datacenter":dc,
    "selected_price_hr":price,
    "dynamic_max_billed_seconds":dynamic,
    "paid_boundary_refresh_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "paid_boundary_refresh_committed_before_pod":True,
})
Path(".github/runpod-control/one-day-public-probe-free-result-05.json").write_text(json.dumps(f,indent=2,sort_keys=True)+"\n")
print("AQLEVON_AUTH05_LIVE_SELECTION",gpu,dc,price,dynamic)
PY

git config user.name aqlevon-runpod-bot
git config user.email actions@users.noreply.github.com
git add "$FREE04"
if ! git diff --cached --quiet; then
  git commit -m "ops: persist auth05 live GPU selection before spend [skip ci]"
  git push origin HEAD:ops/one-day-verified-trajectory-20260925
fi
test -z "$(git status --porcelain)" || { git status --porcelain; echo FAIL_CLOSED_AUTH05_DIRTY_TREE_BEFORE_POD; exit 1; }

exec bash "$TMP_DRIVER"
