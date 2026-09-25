FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/models/hf \
    TRANSFORMERS_CACHE=/models/hf \
    HF_HUB_DISABLE_TELEMETRY=1

WORKDIR /app

RUN python -m pip install --no-cache-dir \
    runpod \
    transformers==5.17.0 \
    peft==0.21.0 \
    accelerate==1.15.0 \
    huggingface_hub \
    safetensors \
    sentencepiece \
    qwen-vl-utils==0.0.14

COPY handler.py /app/handler.py
COPY adapter /app/adapter

CMD ["python","-u","/app/handler.py"]
