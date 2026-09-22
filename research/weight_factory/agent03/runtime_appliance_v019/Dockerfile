FROM vllm/vllm-openai:v0.19.0

ARG SDPO_COMMIT=7c457fc1b1f636ae794eb0362ba37d4743b06fbc
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    AQLEVON_RUNTIME_ROOT=/opt/aqlevon/runtime \
    AQLEVON_SDPO=/opt/aqlevon/runtime/SDPO \
    VLLM_USE_V1=1

USER root
WORKDIR /opt/aqlevon/runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl ca-certificates openssh-server ninja-build \
    && mkdir -p /run/sshd /root/.ssh \
    && chmod 700 /root/.ssh \
    && rm -rf /var/lib/apt/lists/*

COPY research/weight_factory/agent03/runtime_appliance_v019/requirements-p4-a1-v019.txt /tmp/requirements-p4-a1-v019.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-p4-a1-v019.txt

# SDPO's default HF attention implementation is flash_attention_2.
# Preserve the frozen recipe rather than silently switching to SDPA.
RUN python3 - <<'PY'
import importlib.util, subprocess, sys
if importlib.util.find_spec("flash_attn") is None:
    subprocess.check_call([
        sys.executable,"-m","pip","install","--no-cache-dir","--no-build-isolation",
        "flash-attn==2.8.3"
    ])
PY

RUN git clone -q https://github.com/lasgroup/SDPO.git "$AQLEVON_SDPO" \
 && git -C "$AQLEVON_SDPO" checkout -q "$SDPO_COMMIT" \
 && python3 -m pip install --no-cache-dir --no-deps -e "$AQLEVON_SDPO"

COPY research/weight_factory/agent03/p4_patch_sdpo_transformers5_native_vllm019.py /opt/aqlevon/runtime/p4_patch_sdpo_transformers5_native_vllm019.py
RUN python3 /opt/aqlevon/runtime/p4_patch_sdpo_transformers5_native_vllm019.py

COPY research/weight_factory/agent03/runtime_appliance_v019/smoke_runtime_v019.py /opt/aqlevon/runtime/smoke_runtime_v019.py
RUN python3 /opt/aqlevon/runtime/smoke_runtime_v019.py --build-check

COPY research/weight_factory/agent03/runtime_appliance_v019/start.sh /start.sh
RUN chmod +x /start.sh

LABEL org.opencontainers.image.title="AQLEVON P4 A1 Native Qwen3.5 Runtime Appliance" \
      aqlevon.sdpo.commit="7c457fc1b1f636ae794eb0362ba37d4743b06fbc" \
      aqlevon.vllm="0.19.0" \
      aqlevon.qwen35.backend="native"

ENTRYPOINT []
CMD ["/start.sh"]
