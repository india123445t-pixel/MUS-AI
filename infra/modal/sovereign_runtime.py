"""MUS AI sovereign runtime on Modal.

Safety properties:
- Exact model + immutable revision are pinned.
- GPU serving is text-only for the first proof-of-runtime, reducing VRAM pressure.
- The server scales from zero and is limited to one replica.
- The first smoke test uses 2x L4 GPUs with tensor parallelism to avoid the L40S payment-method gate.
- External inference providers are not used here.
- The HTTP endpoint requires a bearer API key supplied via the Modal secret
  `mus-model-runtime` (`MUS_MODEL_KEY`).
- Model weights must be prepared first by `infra/modal/prepare_model.py`.
- The smoke-test entrypoint is bounded and the ephemeral app exits after testing.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

import modal

MODEL_ID = "Qwen/Qwen3.8-27B-FP8"
MODEL_REVISION = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"
MODEL_VOLUME_NAME = "mus-model-store"
VLLM_CACHE_VOLUME_NAME = "mus-vllm-cache"
RUNTIME_SECRET_NAME = "mus-model-runtime"

MODEL_MOUNT = pathlib.Path("/models")
MODEL_DIR = MODEL_MOUNT / "Qwen3.8-27B-FP8" / MODEL_REVISION
VLLM_CACHE_MOUNT = pathlib.Path("/vllm-cache")
PORT = 8000
SMOKE_TIMEOUT_SECONDS = 16 * 60
SMOKE_MAX_MODEL_LEN = 2048

app = modal.App("mus-sovereign-runtime")

# Fail closed if the prepared model volume is missing. This prevents accidentally
# starting paid GPUs against an empty model store.
model_volume = modal.Volume.from_name(MODEL_VOLUME_NAME)
vllm_cache_volume = modal.Volume.from_name(VLLM_CACHE_VOLUME_NAME, create_if_missing=True)

vllm_image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.0-devel-ubuntu22.04",
        add_python="3.12",
    )
    .entrypoint([])
    .uv_pip_install(
        "vllm==0.29.0",
        "huggingface_hub[hf_xet]>=0.35.0",
    )
    .env(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_XET_HIGH_PERFORMANCE": "1",
            "VLLM_CACHE_ROOT": str(VLLM_CACHE_MOUNT),
            "OMP_NUM_THREADS": "1",
        }
    )
)

runtime_secret = modal.Secret.from_name(
    RUNTIME_SECRET_NAME,
    required_keys=["MUS_MODEL_KEY"],
)


def _wait_for_vllm(process: subprocess.Popen, api_key: str, timeout_seconds: int = 13 * 60) -> None:
    """Wait until vLLM is actually ready before Modal routes traffic to it."""
    deadline = time.monotonic() + timeout_seconds
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/health",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"vLLM exited during startup with code {process.returncode}")
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if 200 <= response.status < 300:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(2)

    raise TimeoutError("vLLM did not become healthy before the startup deadline")


@app.server(
    image=vllm_image,
    gpu="L4:2",
    min_containers=0,
    max_containers=1,
    target_concurrency=1,
    scaledown_window=30,
    startup_timeout=15 * 60,
    port=PORT,
    unauthenticated=True,  # vLLM itself enforces MUS_MODEL_KEY bearer auth.
    volumes={
        str(MODEL_MOUNT): model_volume.with_mount_options(read_only=True),
        str(VLLM_CACHE_MOUNT): vllm_cache_volume,
    },
    secrets=[runtime_secret],
)
class SovereignServer:
    """Authenticated OpenAI-compatible vLLM server for MUS self_hosted_only."""

    @modal.enter()
    def start(self) -> None:
        api_key = os.environ["MUS_MODEL_KEY"]
        manifest_path = MODEL_DIR / "MUS_RUNTIME_MANIFEST.json"
        if not manifest_path.exists():
            raise RuntimeError(
                "Pinned model is not prepared. Run `modal run infra/modal/prepare_model.py` first."
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("repo") != MODEL_ID or manifest.get("revision") != MODEL_REVISION:
            raise RuntimeError("Model manifest does not match the frozen MUS artifact.")

        cmd = [
            "vllm",
            "serve",
            str(MODEL_DIR),
            "--served-model-name",
            MODEL_ID,
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
            "--api-key",
            api_key,
            "--max-model-len",
            str(SMOKE_MAX_MODEL_LEN),
            "--max-num-seqs",
            "1",
            "--gpu-memory-utilization",
            "0.90",
            "--tensor-parallel-size",
            "2",
            "--language-model-only",
            "--enforce-eager",
            "--uvicorn-log-level",
            "warning",
            "--disable-log-requests",
        ]

        print(
            json.dumps(
                {
                    "event": "starting_vllm",
                    "model": MODEL_ID,
                    "revision": MODEL_REVISION,
                    "max_model_len": SMOKE_MAX_MODEL_LEN,
                    "gpu": "L4:2",
                    "tensor_parallel_size": 2,
                    "text_only": True,
                }
            )
        )
        self.process = subprocess.Popen(cmd)
        _wait_for_vllm(self.process, api_key)
        print(json.dumps({"event": "vllm_ready", "model": MODEL_ID}))

    @modal.exit()
    def stop(self) -> None:
        process = getattr(self, "process", None)
        if process is None:
            return
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@app.function(
    secrets=[runtime_secret],
    timeout=SMOKE_TIMEOUT_SECONDS,
    cpu=0.125,
    memory=256,
)
def smoke_test() -> dict:
    """Trigger one bounded GPU server and verify three short chat completions.

    This function never prints or returns MUS_MODEL_KEY. The first request also
    triggers the scale-from-zero server. HTTP 503 is retried while the GPU
    container is starting. When this `modal run` invocation finishes, the
    ephemeral App exits; the server is not left deployed persistently.
    """
    api_key = os.environ["MUS_MODEL_KEY"]
    base_url = SovereignServer.get_url().rstrip("/")
    endpoint = f"{base_url}/v1/chat/completions"
    deadline = time.monotonic() + 15 * 60

    prompts = [
        "أجب بالعربية الفصحى بجملة واحدة: ما فائدة اختبار النظام قبل نشره؟",
        "جاوب بالدارجة المغربية بجملة قصيرة: علاش خاصنا نجربو النظام قبل ما نستعملوه؟",
        "احسب 17 × 23 وأعط النتيجة فقط.",
    ]

    outputs: list[dict] = []
    for index, prompt in enumerate(prompts, start=1):
        payload = json.dumps(
            {
                "model": MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 80,
            }
        ).encode("utf-8")

        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError("Sovereign smoke test exceeded its 15-minute request deadline")

            request = urllib.request.Request(
                endpoint,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    body = json.loads(response.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"]
                outputs.append({"prompt_index": index, "response": content})
                print(json.dumps({"event": "smoke_prompt_ok", "prompt_index": index}, ensure_ascii=False))
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 503:
                    time.sleep(3)
                    continue
                raise RuntimeError(f"Smoke request failed with HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(3)

    result = {
        "status": "PASS",
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "prompts_ok": len(outputs),
        "outputs": outputs,
    }
    print(json.dumps(result, ensure_ascii=False))
    return result
