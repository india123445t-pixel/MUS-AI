#!/usr/bin/env bash
set -euo pipefail
SRC=.github/runpod-control/run-one-day-public-probe-02.sh
TMP=/tmp/run-one-day-public-probe-03.sh
python3 - "$SRC" "$TMP" <<'PY'
from pathlib import Path
import sys
src,dst=sys.argv[1:3]
s=Path(src).read_text()
repls={
"P4-ONE-DAY-PUBLIC-PASSN-20260925-02":"P4-ONE-DAY-PUBLIC-PASSN-20260925-03",
"430ae3149249d9522aa027a852bde786f5ef4a97d252781fea15080483e467c6":"062487f3de6bd60bafc269643bb40bb982eb39c05cfe9a99d28f3ee766098c03",
"one-day-public-probe-manager-authorization-02-20260925.json":"one-day-public-probe-manager-authorization-03-20260925.json",
"one-day-public-probe-free-result-02.json":"one-day-public-probe-free-result-03.json",
"execute-one-day-public-probe-02.json":"execute-one-day-public-probe-03.json",
"one-day-public-probe-consumed-02.json":"one-day-public-probe-consumed-03.json",
"one-day-public-probe-run-result-02.json":"one-day-public-probe-run-result-03.json",
"remote-one-day-public-probe-02.sh":"remote-one-day-public-probe-03.sh",
"AQLEVON-ONE-DAY-PASSN-02-20260925":"AQLEVON-ONE-DAY-PASSN-03-20260925",
}
for a,b in repls.items(): s=s.replace(a,b)
old='''git add "$CONSUMED"
git commit -m "ops: consume one-day public probe authorization [skip ci]" || die consumed_commit_failed
git pull --rebase origin ops/one-day-verified-trajectory-20260925 || die consumed_rebase_failed
git push origin HEAD:ops/one-day-verified-trajectory-20260925 || die consumed_push_failed'''
new='''git add "$CONSUMED"
git commit -m "ops: consume one-day public probe authorization 03 [skip ci]" || die consumed_commit_failed
git push origin HEAD:ops/one-day-verified-trajectory-20260925 || die consumed_push_failed'''
assert old in s
s=s.replace(old,new)
marker='# ---- paid boundary ----'
assert marker in s
s=s.replace(marker,'''# Fail before spend if the shared ops branch moved since checkout.
git fetch -q origin ops/one-day-verified-trajectory-20260925 || die ops_fetch_failed
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/ops/one-day-verified-trajectory-20260925)" || die ops_branch_moved_precreate

# ---- paid boundary ----''',1)
podmark='echo "AQLEVON_ONE_DAY_POD_CREATED $pod"'
assert podmark in s
s=s.replace(podmark,podmark+'''

# Immediate emergency stop trap. It stops only; evidence deletion remains governed by the normal durable-egress path.
emergency_stop_auth03(){
  p="$(cat /tmp/pod_id 2>/dev/null || true)"
  [ -n "$p" ] || return 0
  runpodctl pod stop "$p" >/tmp/auth03-emergency-stop.txt 2>&1 || true
}
trap emergency_stop_auth03 EXIT''',1)
Path(dst).write_text(s)
PY
cp .github/runpod-control/remote-one-day-public-probe-02.sh /tmp/remote-one-day-public-probe-03.sh
bash -n "$TMP"
bash -n /tmp/remote-one-day-public-probe-03.sh
python3 - "$TMP" <<'PY'
from pathlib import Path
import sys
s=Path(sys.argv[1]).read_text()
assert 'P4-ONE-DAY-PUBLIC-PASSN-20260925-03' in s
assert '062487f3de6bd60bafc269643bb40bb982eb39c05cfe9a99d28f3ee766098c03' in s
assert 'emergency_stop_auth03' in s
paid=s.split('# ---- paid boundary ----',1)[1]
consumed=paid.split('final_rc=255',1)[0]
assert 'git pull --rebase' not in consumed
assert 'one-day-public-probe-free-result-03.json' in s
assert 'one-day-public-probe-consumed-03.json' in s
print('AQLEVON_AUTH03_WRAPPER_STATIC_PASS')
PY
cp /tmp/remote-one-day-public-probe-03.sh .github/runpod-control/remote-one-day-public-probe-03.sh
exec bash "$TMP"
