#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SDPO = Path("/opt/aqlevon/runtime/SDPO")
EXPECTED_PATCH = {
    SDPO / "verl/utils/model.py": "135f61865fcbe057d29da90bf07968b04dd778e2e96a31d3ad640a8650155f8d",
    SDPO / "verl/workers/fsdp_workers.py": "e0ec49a1b891daed8f180a35f5d1d7e5147a3a8289c3787fc7688892e0e55fed",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_check() -> dict:
    import torch
    import ray
    import transformers
    import peft
    import accelerate
    import flash_attn
    import verl
    import verl.workers.fsdp_workers
    import vllm
    from vllm.engine.arg_utils import AsyncEngineArgs

    assert sys.version_info[:2] == (3, 12), sys.version
    assert torch.__version__.split("+")[0] == "2.8.0", torch.__version__
    assert torch.version.cuda and torch.version.cuda.startswith("12.8"), torch.version.cuda
    assert ray.__version__ == "2.53.0", ray.__version__
    assert transformers.__version__ == "5.17.0", transformers.__version__
    assert peft.__version__ == "0.21.0", peft.__version__
    assert accelerate.__version__ == "1.15.0", accelerate.__version__
    assert flash_attn.__version__ == "2.8.3", flash_attn.__version__
    assert vllm.__version__ == "0.10.2", vllm.__version__
    assert "model_impl" in AsyncEngineArgs.__dataclass_fields__, AsyncEngineArgs.__dataclass_fields__.keys()
    assert str(Path(verl.__file__).resolve()).startswith(str(SDPO)), verl.__file__

    qwen_backend = SDPO / "verl/workers/rollout/vllm_rollout/vllm_async_server.py"
    qwen_text = qwen_backend.read_text(encoding="utf-8")
    assert 'getattr(self.model_config.hf_config, "model_type", None) == "qwen3_5"' in qwen_text
    assert 'engine_kwargs["model_impl"] = "transformers"' in qwen_text
    assert "AQLEVON_QWEN35_VLLM_TRANSFORMERS_BACKEND_PASS" in qwen_text

    for path, expected in EXPECTED_PATCH.items():
        got = sha256(path)
        assert got == expected, (str(path), got, expected)

    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)

    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "ray": ray.__version__,
        "transformers": transformers.__version__,
        "peft": peft.__version__,
        "accelerate": accelerate.__version__,
        "flash_attn": flash_attn.__version__,
        "vllm": vllm.__version__,
        "qwen35_model_impl": "transformers",
        "verl": str(Path(verl.__file__).resolve()),
        "gpu_required": False,
    }


def gpu_check() -> dict:
    import torch
    from flash_attn import flash_attn_func

    assert torch.cuda.is_available(), "CUDA_NOT_AVAILABLE"
    assert torch.cuda.device_count() == 1, torch.cuda.device_count()
    name = torch.cuda.get_device_name(0)
    assert "RTX 4090" in name, name

    q = torch.randn((1, 16, 16, 256), device="cuda", dtype=torch.bfloat16, requires_grad=True)
    k = torch.randn((1, 16, 4, 256), device="cuda", dtype=torch.bfloat16, requires_grad=True)
    v = torch.randn((1, 16, 4, 256), device="cuda", dtype=torch.bfloat16, requires_grad=True)
    out = flash_attn_func(q, k, v, dropout_p=0.0, causal=True)
    out.float().sum().backward()
    torch.cuda.synchronize()
    assert q.grad is not None and k.grad is not None and v.grad is not None

    return {
        "gpu_required": True,
        "gpu": name,
        "device_count": torch.cuda.device_count(),
        "flash_attn_shape": list(out.shape),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--build-check", action="store_true")
    p.add_argument("--gpu-check", action="store_true")
    args = p.parse_args()

    assert args.build_check or args.gpu_check, "choose --build-check and/or --gpu-check"

    result = {}
    if args.build_check:
        result["build"] = build_check()
        print("AQLEVON_APPLIANCE_BUILD_CHECK_PASS")
    if args.gpu_check:
        result["gpu"] = gpu_check()
        print("AQLEVON_APPLIANCE_GPU_CHECK_PASS")

    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
