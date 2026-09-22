#!/usr/bin/env python3
"""AQLEVON P4 runtime compatibility repair for Qwen3.5 on vLLM 0.10.2."""
from __future__ import annotations
import hashlib, subprocess
from pathlib import Path

SDPO = Path("/workspace/SDPO")
EXPECTED_COMMIT = "7c457fc1b1f636ae794eb0362ba37d4743b06fbc"
TARGET = SDPO / "verl/workers/rollout/vllm_rollout/vllm_async_server.py"
MARKER = "AQLEVON_QWEN35_VLLM_TRANSFORMERS_BACKEND_PASS"

OLD = '''        engine_kwargs = self.config.get("engine_kwargs", {}).get("vllm", {}) or {}
        engine_kwargs = {key: val for key, val in engine_kwargs.items() if val is not None}
        if self.config.get("limit_images", None):  # support for multi-image data
'''

NEW = '''        engine_kwargs = self.config.get("engine_kwargs", {}).get("vllm", {}) or {}
        engine_kwargs = {key: val for key, val in engine_kwargs.items() if val is not None}
        # AQLEVON_QWEN35_VLLM_TRANSFORMERS_BACKEND:
        # vLLM 0.10.2 does not natively register Qwen3_5ForConditionalGeneration.
        # Bind only exact qwen3_5 to vLLM's documented Transformers backend.
        if getattr(self.model_config.hf_config, "model_type", None) == "qwen3_5":
            requested_model_impl = engine_kwargs.get("model_impl")
            if requested_model_impl not in (None, "transformers"):
                raise RuntimeError(
                    "AQLEVON_QWEN35_MODEL_IMPL_CONFLICT:"
                    + str(requested_model_impl)
                )
            engine_kwargs["model_impl"] = "transformers"
            required_hf_overrides = {"architectures": ["TransformersForMultimodalLM"]}
            requested_hf_overrides = engine_kwargs.get("hf_overrides")
            if requested_hf_overrides not in (None, required_hf_overrides):
                raise RuntimeError(
                    "AQLEVON_QWEN35_HF_OVERRIDES_CONFLICT:"
                    + str(requested_hf_overrides)
                )
            engine_kwargs["hf_overrides"] = required_hf_overrides
            logger.info("AQLEVON_QWEN35_VLLM_TRANSFORMERS_BACKEND_PASS")
        if self.config.get("limit_images", None):  # support for multi-image data
'''

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    head = subprocess.check_output(["git", "-C", str(SDPO), "rev-parse", "HEAD"], text=True).strip()
    if head != EXPECTED_COMMIT:
        raise SystemExit(f"sdpo_commit_mismatch:{head}")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        raise SystemExit("qwen35_backend_patch_already_applied")
    if text.count(OLD) != 1:
        raise SystemExit(f"qwen35_backend_anchor_count:{text.count(OLD)}")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    subprocess.run(["python", "-m", "py_compile", str(TARGET)], check=True)
    patched = TARGET.read_text(encoding="utf-8")
    for required in (
        'getattr(self.model_config.hf_config, "model_type", None) == "qwen3_5"',
        'engine_kwargs["model_impl"] = "transformers"',
        '"TransformersForMultimodalLM"',
        'engine_kwargs["hf_overrides"] = required_hf_overrides',
        MARKER,
        "AQLEVON_QWEN35_MODEL_IMPL_CONFLICT",
        "AQLEVON_QWEN35_HF_OVERRIDES_CONFLICT",
    ):
        if required not in patched:
            raise SystemExit("qwen35_backend_patch_missing:" + required)
    diff = subprocess.check_output(
        ["git", "-C", str(SDPO), "diff", "--", str(TARGET.relative_to(SDPO))], text=True
    )
    if not diff.strip():
        raise SystemExit("qwen35_backend_patch_no_diff")
    print(MARKER)
    print("VLLM_ASYNC_SERVER_SHA256:", sha256(TARGET))
    print("=== PATCH DIFF ===")
    print(diff)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
