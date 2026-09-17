#!/usr/bin/env bash
set -euo pipefail

MODEL_REPO="ggml-org/Qwen3.8-27B-GGUF"
MODEL_FILE="Qwen3.8-27B-Q4_K_M.gguf"
MODEL_URL="https://huggingface.co/${MODEL_REPO}/resolve/main/${MODEL_FILE}?download=true"
MODEL_ALIAS="AQLEVON-27B"
ROOT="/workspaces/.aqlevon"
MODEL_DIR="${ROOT}/models"
BUILD_DIR="${ROOT}/llama.cpp"
LOG_DIR="${ROOT}/logs"
PID_FILE="${ROOT}/llama-server.pid"
LOG_FILE="${LOG_DIR}/llama-server.log"

mkdir -p "$MODEL_DIR" "$LOG_DIR"

echo '=== AQLEVON Codespace capacity ==='
free -h
df -h /workspaces || df -h /

MEM_GB=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
FREE_GB=$(df -BG --output=avail /workspaces 2>/dev/null | tail -1 | tr -dc '0-9' || true)
if [ -z "$FREE_GB" ]; then FREE_GB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9'); fi

if [ "$MEM_GB" -lt 28 ]; then
  echo "AQLEVON_CAPACITY_FAIL: need at least ~28GB RAM for the Q4 proof; detected ${MEM_GB}GB" >&2
  exit 21
fi
if [ "$FREE_GB" -lt 24 ]; then
  echo "AQLEVON_DISK_FAIL: need at least 24GB free; detected ${FREE_GB}GB" >&2
  exit 22
fi

if [ ! -x "$BUILD_DIR/build/bin/llama-server" ]; then
  rm -rf "$BUILD_DIR"
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$BUILD_DIR"
  cmake -S "$BUILD_DIR" -B "$BUILD_DIR/build" \
    -DGGML_CUDA=OFF \
    -DLLAMA_CURL=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DLLAMA_BUILD_TESTS=OFF
  cmake --build "$BUILD_DIR/build" -j "$(nproc)" --target llama-server
fi

MODEL_PATH="$MODEL_DIR/$MODEL_FILE"
if [ ! -f "$MODEL_PATH" ] || [ "$(stat -c%s "$MODEL_PATH" 2>/dev/null || echo 0)" -lt 18000000000 ]; then
  rm -f "$MODEL_PATH"
  curl -fL --retry 8 --retry-all-errors --connect-timeout 30 \
    "$MODEL_URL" -o "$MODEL_PATH"
fi

if [ "$(stat -c%s "$MODEL_PATH")" -lt 18000000000 ]; then
  echo 'AQLEVON_MODEL_FAIL: downloaded artifact is unexpectedly small' >&2
  exit 23
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  kill "$(cat "$PID_FILE")" || true
  sleep 2
fi

nohup "$BUILD_DIR/build/bin/llama-server" \
  -m "$MODEL_PATH" \
  --alias "$MODEL_ALIAS" \
  --host 0.0.0.0 \
  --port 8080 \
  --ctx-size 1024 \
  --threads "$(nproc)" \
  --parallel 1 \
  --n-gpu-layers 0 \
  > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

for i in $(seq 1 180); do
  if curl -fsS http://127.0.0.1:8080/health >/tmp/aqlevon-health.json 2>/dev/null; then
    echo 'AQLEVON_ENDPOINT_HEALTH_PASS'
    cat /tmp/aqlevon-health.json
    echo
    echo 'Local endpoint: http://127.0.0.1:8080/v1/chat/completions'
    echo 'Codespaces port 8080 should remain PRIVATE unless the owner deliberately changes its visibility.'
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo 'AQLEVON_SERVER_EXITED_DURING_LOAD' >&2
    tail -200 "$LOG_FILE" >&2 || true
    exit 24
  fi
  sleep 5
done

echo 'AQLEVON_ENDPOINT_HEALTH_TIMEOUT' >&2
tail -200 "$LOG_FILE" >&2 || true
exit 25
