FROM vllm/vllm-openai:v0.19.1

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
      git curl ca-certificates openssh-server ninja-build python3-cairo \
    && mkdir -p /run/sshd /root/.ssh \
    && chmod 700 /root/.ssh \
    && ln -sf "$(command -v python3)" /usr/local/bin/python \
    && python --version \
    && rm -rf /var/lib/apt/lists/*

COPY research/weight_factory/agent03/runtime_appliance_v019/requirements-p4-a1-v019.txt /tmp/requirements-p4-a1-v019.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-p4-a1-v019.txt

# SDPO's default HF attention implementation is flash_attention_2.
# Preserve the frozen recipe. GitHub-hosted runners repeatedly died compiling
# flash-attn from source, so use an exact-stack prebuilt wheel and verify bytes.
ARG FLASH_ATTN_WHEEL_URL=https://github.com/lesj0610/flash-attention/releases/download/v2.8.3-cu12-torch2.10-cp312/flash_attn-2.8.3%2Bcu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl
ARG FLASH_ATTN_WHEEL_SHA256=d4a497a7bd837bf47f7a8f6a7aa6887695f2ea819fa597f307552552018ee9d7
RUN if ! python3 -c 'import flash_attn' >/dev/null 2>&1; then \
      curl -fL "$FLASH_ATTN_WHEEL_URL" -o /tmp/flash_attn-2.8.3+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
      echo "$FLASH_ATTN_WHEEL_SHA256  /tmp/flash_attn-2.8.3+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl" | sha256sum -c - && \
      python3 -m pip install --no-cache-dir /tmp/flash_attn-2.8.3+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl && \
      rm -f /tmp/flash_attn-2.8.3+cu12torch2.10cxx11abiTRUE-cp312-cp312-linux_x86_64.whl; \
    fi

RUN git clone -q https://github.com/lasgroup/SDPO.git "$AQLEVON_SDPO" \
 && git -C "$AQLEVON_SDPO" checkout -q "$SDPO_COMMIT" \
 && python3 - <<'PY'
from pathlib import Path
p=Path("/opt/aqlevon/runtime/SDPO/setup.py")
s=p.read_text()
old='"numpy<2.0.0"'
new='"numpy>=2.0,<2.3"'
assert s.count(old)==1, s.count(old)
p.write_text(s.replace(old,new,1))
print("AQLEVON_SDPO_NUMPY2_METADATA_PATCH_PASS")
PY
RUN python3 -m pip install --no-cache-dir --no-deps -e "$AQLEVON_SDPO"

COPY research/weight_factory/agent03/p4_patch_sdpo_transformers5_native_vllm019.py /opt/aqlevon/runtime/p4_patch_sdpo_transformers5_native_vllm019.py
RUN python3 /opt/aqlevon/runtime/p4_patch_sdpo_transformers5_native_vllm019.py

COPY research/weight_factory/agent03/runtime_appliance_v019/smoke_runtime_v019.py /opt/aqlevon/runtime/smoke_runtime_v019.py
RUN python3 /opt/aqlevon/runtime/smoke_runtime_v019.py --build-check

COPY research/weight_factory/agent03/runtime_appliance_v019/start.sh /start.sh
RUN chmod +x /start.sh

LABEL org.opencontainers.image.title="AQLEVON P4 A1 Native Qwen3.5 Runtime Appliance" \
      aqlevon.sdpo.commit="7c457fc1b1f636ae794eb0362ba37d4743b06fbc" \
      aqlevon.vllm="0.19.1" \
      aqlevon.qwen35.backend="native"

ENTRYPOINT []
CMD ["/start.sh"]
