#!/usr/bin/env bash
set -euo pipefail
# ZERO-COST PROTOTYPE ONLY. This helper never creates, starts, stops, or deletes Pods.
# Auth10 is NOT authorized by this file.

: "${RUNPODCTL_BIN:=runpodctl}"

proxy_target_for_pod() {
  local pod_id="${1:?pod id required}"
  local out target
  out="$("$RUNPODCTL_BIN" ssh info "$pod_id" 2>&1)"
  printf '%s\n' "$out" >/tmp/aqlevon-auth10-ssh-info.txt
  target="$(python3 - <<'PY'
import re
s=open('/tmp/aqlevon-auth10-ssh-info.txt',errors='replace').read()
m=re.search(r'\bssh\s+([^\s]+@ssh\.runpod\.io)\b',s)
if not m:
    raise SystemExit(2)
print(m.group(1))
PY
)"
  test -n "$target"
  printf '%s\n' "$target"
}

wait_proxy_target() {
  local pod_id="${1:?pod id required}"
  local timeout_s="${2:-360}"
  local start now target
  start="$(date +%s)"
  while :; do
    if target="$(proxy_target_for_pod "$pod_id" 2>/dev/null)"; then
      printf '%s\n' "$target"
      return 0
    fi
    now="$(date +%s)"
    [ $((now-start)) -lt "$timeout_s" ] || return 124
    sleep 5
  done
}

proxy_exec() {
  local key="${1:?private key required}"
  local target="${2:?proxy target required}"
  shift 2
  ssh -i "$key" -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=12 "$target" "$@"
}

proxy_put_verified() {
  local key="${1:?private key required}"
  local target="${2:?proxy target required}"
  local local_path="${3:?local path required}"
  local remote_path="${4:?remote path required}"
  local local_sha remote_sha
  local_sha="$(sha256sum "$local_path" | awk '{print $1}')"
  # Basic Runpod SSH does not support SCP/SFTP. Stream bytes over the SSH session.
  proxy_exec "$key" "$target" "cat > '$remote_path'" <"$local_path"
  remote_sha="$(proxy_exec "$key" "$target" "sha256sum '$remote_path' | awk '{print \\$1}'")"
  test "$local_sha" = "$remote_sha"
  printf 'AQLEVON_PROXY_TRANSFER_PASS %s %s\n' "$remote_path" "$local_sha"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "AQLEVON_AUTH10_PROXY_TRANSPORT_STATIC_ONLY"
fi
