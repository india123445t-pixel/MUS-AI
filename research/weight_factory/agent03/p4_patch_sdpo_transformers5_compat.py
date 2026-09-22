#!/usr/bin/env python3
"""Apply the minimal Transformers-5 compatibility patch to pinned SDPO.

The pinned SDPO commit still imports AutoModelForVision2Seq, removed from
Transformers 5.17.0. This patch changes only those imports/usages needed by the
P4 training path, aliasing the removed class name to AutoModelForImageTextToText.
It also forces vLLM's documented Transformers model implementation for the pinned
Qwen3.5 rollout path because vLLM 0.10.2 predates native Qwen3.5 registration.
It does not modify model weights, data, training hyperparameters, or the Git HEAD.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sysconfig
from pathlib import Path

SDPO = Path("/workspace/SDPO")
EXPECTED_COMMIT = "7c457fc1b1f636ae794eb0362ba37d4743b06fbc"

MODEL = SDPO / "verl/utils/model.py"
FSDP = SDPO / "verl/workers/fsdp_workers.py"
VLLM_ASYNC = SDPO / "verl/workers/rollout/vllm_rollout/vllm_async_server.py"
VLLM_LORA_MODELS = Path(os.environ.get("AQLEVON_VLLM_LORA_MODELS_PATH", str(Path(sysconfig.get_paths()["purelib"]) / "vllm/lora/models.py")))
VLLM_TRANSFORMERS_MODELS = Path(os.environ.get("AQLEVON_VLLM_TRANSFORMERS_MODELS_PATH", str(Path(sysconfig.get_paths()["purelib"]) / "vllm/model_executor/models/transformers.py")))
REQUIRED_ROLLOUT_LORA_SUFFIXES = (".self_attn.q_proj", ".self_attn.v_proj")
EXPECTED_REQUIRED_ROLLOUT_LORA_MODULES = 16


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected exactly one match, observed {n}")
    return text.replace(old, new, 1)


def patch_vllm_lora_manager(text: str) -> str:
    """Backport a fail-closed guard for unsupported Transformers-backend modules.

    vLLM 0.10.2 only skips non-LoRA-replaceable modules when supports_mm is
    true. The forced Qwen3.5 Transformers backend can expose mixed module
    types while supports_mm is false, causing an assertion before rollout.
    We may skip only unsupported non-target modules. Frozen self_attn q/v
    targets must all be LoRA-capable. Qwen3.5-4B has 8 full-attention layers\n    in its frozen 3:1 hybrid stack, so q_proj + v_proj yields exactly 16\n    rollout LoRA modules.
    """
    old = """            if self.supports_mm and not isinstance(new_module,
                                                   BaseLayerWithLoRA):
                continue
            self.register_module(module_name, new_module)
            self._register_packed_modules(module_name)
            # All lora layers share the same punica_wrapper based on reference.
            new_module.set_mapping(self.punica_wrapper)
"""
    new = """            # AQLEVON_QWEN35_VLLM_LORA_GUARD: Transformers backend may expose
            # unsupported duplicate module names while supports_mm is false.
            # Never skip the frozen self_attn q/v LoRA targets.
            if not isinstance(new_module, BaseLayerWithLoRA):
                if module_name.endswith((\".self_attn.q_proj\", \".self_attn.v_proj\")):
                    raise RuntimeError(
                        \"AQLEVON_REQUIRED_ROLLOUT_LORA_MODULE_UNSUPPORTED:\"
                        + module_name + \":\" + type(module).__name__
                    )
                continue
            self.register_module(module_name, new_module)
            self._register_packed_modules(module_name)
            # All lora layers share the same punica_wrapper based on reference.
            new_module.set_mapping(self.punica_wrapper)

        aqlevon_required = [
            name for name in self.modules
            if name.endswith((\".self_attn.q_proj\", \".self_attn.v_proj\"))
        ]
        if len(aqlevon_required) != 16:
            raise RuntimeError(
                \"AQLEVON_REQUIRED_ROLLOUT_LORA_MODULE_COUNT:\"
                + str(len(aqlevon_required)) + \":expected_16\"
            )
"""
    if "AQLEVON_QWEN35_VLLM_LORA_GUARD" in text:
        return text
    return replace_once(text, old, new, "vllm_lora_guard")



def patch_vllm_transformers_mm_mapping(text: str) -> str:
    """Backport multimodal module mapping for Qwen3.5 Transformers backend.

    vLLM only filters vision-tower modules from LoRA when the multimodal model
    exposes get_mm_mapping(). The generic TransformersForMultimodalLM wrapper in
    v0.10.2 lacks that mapping, so its dummy multimodal profile run can wrap
    Qwen3.5 visual qkv/proj layers with LoRA and hit token mapping shape asserts.
    This mirrors the upstream vLLM fix pattern: explicitly separate the language
    model from the vision tower, while failing closed for any other model type.
    """
    if "AQLEVON_QWEN35_MM_LORA_MAPPING" in text:
        return text

    text = replace_once(
        text,
        "from .interfaces import (SupportsLoRA, SupportsMultiModal, SupportsPP,\n"
        "                         SupportsQuant)\n"
        "from .utils import (AutoWeightsLoader, PPMissingLayer, WeightsMapper,\n",
        "from .interfaces import (SupportsLoRA, SupportsMultiModal, SupportsPP,\n"
        "                         SupportsQuant)\n"
        "from .module_mapping import MultiModelKeys\n"
        "from .utils import (AutoWeightsLoader, PPMissingLayer, WeightsMapper,\n",
        "vllm_transformers_mm_mapping_import",
    )

    old = """    def __init__(self, *, vllm_config: VllmConfig, prefix: str = ""):
        super().__init__(vllm_config=vllm_config, prefix=prefix)

        self.dtype = vllm_config.model_config.dtype
"""
    new = """    # AQLEVON_QWEN35_MM_LORA_MAPPING: vLLM 0.10.2 generic Transformers
    # multimodal wrapper must expose language-vs-vision prefixes so LoRA never
    # wraps Qwen3.5 visual modules during startup profiling.
    def get_mm_mapping(self) -> MultiModelKeys:
        if getattr(self.config, "model_type", None) != "qwen3_5":
            raise RuntimeError(
                "AQLEVON_TRANSFORMERS_MM_MAPPING_UNSUPPORTED_MODEL:"
                + str(getattr(self.config, "model_type", None))
            )
        if not hasattr(self.model, "language_model") or not hasattr(self.model, "visual"):
            raise RuntimeError("AQLEVON_QWEN35_MM_MAPPING_STRUCTURE_MISMATCH")
        return MultiModelKeys.from_string_field(
            language_model="model.language_model",
            tower_model="model.visual",
        )

    def __init__(self, *, vllm_config: VllmConfig, prefix: str = ""):
        super().__init__(vllm_config=vllm_config, prefix=prefix)

        self.dtype = vllm_config.model_config.dtype
"""
    return replace_once(text, old, new, "vllm_transformers_mm_mapping_method")



def patch_vllm_transformers_mm_output(text: str) -> str:
    """Normalize Transformers 5 Qwen3.5 vision outputs for vLLM 0.10.2.

    Transformers 5 returns a BaseModelOutputWithPooling from Qwen3.5
    get_image_features(), while vLLM 0.10.2 expects the embeddings themselves.
    Qwen3.5 stores the already split image embedding tensors in pooler_output.
    """
    if "AQLEVON_QWEN35_MM_OUTPUT_UNWRAP" in text:
        return text

    old = """            vision_embeddings = self.model.get_image_features(
                pixel_values,
                **{
                    k: v.flatten(0, 1)
                    for k, v in kwargs.items()
                },
            )

            if isinstance(vision_embeddings, torch.Tensor):
"""
    new = """            vision_embeddings = self.model.get_image_features(
                pixel_values,
                **{
                    k: v.flatten(0, 1)
                    for k, v in kwargs.items()
                },
            )

            # AQLEVON_QWEN35_MM_OUTPUT_UNWRAP: Transformers 5 Qwen3.5 returns
            # BaseModelOutputWithPooling; vLLM expects tensor/list/tuple embeds.
            if getattr(self.config, "model_type", None) == "qwen3_5":
                if hasattr(vision_embeddings, "pooler_output"):
                    vision_embeddings = vision_embeddings.pooler_output
                valid_qwen35_mm = (
                    isinstance(vision_embeddings, torch.Tensor)
                    or (
                        isinstance(vision_embeddings, (list, tuple))
                        and all(isinstance(x, torch.Tensor) for x in vision_embeddings)
                    )
                )
                if not valid_qwen35_mm:
                    raise RuntimeError(
                        "AQLEVON_QWEN35_MM_OUTPUT_UNSUPPORTED:"
                        + type(vision_embeddings).__name__
                    )

            if isinstance(vision_embeddings, torch.Tensor):
"""
    return replace_once(text, old, new, "vllm_transformers_mm_output")


def patch_vllm_qwen35_text_rollout(text: str) -> str:
    """Route Qwen3.5 rollout through its text model with an explicit batch axis.

    vLLM 0.10.2's generic Transformers multimodal wrapper predates Qwen3.5.
    During v1 profile/dummy runs it can feed flattened [tokens, hidden] states
    into Qwen3.5's Gated DeltaNet, whose linear-attention implementation
    requires [batch, seq, hidden]. The P4 A1 arm is text-only, so route only
    Qwen3.5 through the already-loaded language_model and preserve the exact
    vLLM attention_instances/position_ids contract. Fail closed if the expected
    Qwen3.5 structure is not present.
    """
    if "AQLEVON_QWEN35_TEXT_ROLLOUT_3D" in text:
        return text

    old = """        hidden_states = self.model(
            input_ids=input_ids,
            inputs_embeds=inputs_embeds,
            use_cache=False,
            position_ids=position_ids,
            attention_instances=self.attention_instances,
            return_dict=False)[0][0, ...]  # we remove batch dimension for now
"""
    new = """        # AQLEVON_QWEN35_TEXT_ROLLOUT_3D: vLLM 0.10.2 predates Qwen3.5's
        # hybrid Gated DeltaNet. Keep the explicit batch axis and bypass the
        # multimodal shell for this frozen text-only rollout arm.
        target_model = self.model
        if getattr(self.config, "model_type", None) == "qwen3_5":
            language_model = getattr(self.model, "language_model", None)
            if language_model is None:
                raise RuntimeError("AQLEVON_QWEN35_LANGUAGE_MODEL_MISSING")
            if input_ids is not None and input_ids.ndim != 2:
                raise RuntimeError(
                    "AQLEVON_QWEN35_INPUT_IDS_RANK:" + str(input_ids.ndim)
                )
            if inputs_embeds is not None and inputs_embeds.ndim != 3:
                raise RuntimeError(
                    "AQLEVON_QWEN35_INPUT_EMBEDS_RANK:" + str(inputs_embeds.ndim)
                )
            target_model = language_model

        hidden_states = target_model(
            input_ids=input_ids,
            inputs_embeds=inputs_embeds,
            use_cache=False,
            position_ids=position_ids,
            attention_instances=self.attention_instances,
            return_dict=False)[0][0, ...]  # we remove batch dimension for now
"""
    return replace_once(text, old, new, "vllm_qwen35_text_rollout_3d")

def main() -> int:
    head = subprocess.check_output(
        ["git", "-C", str(SDPO), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != EXPECTED_COMMIT:
        raise SystemExit(f"sdpo_commit_mismatch:{head}")

    model = MODEL.read_text(encoding="utf-8")
    fsdp = FSDP.read_text(encoding="utf-8")
    vllm_async = VLLM_ASYNC.read_text(encoding="utf-8")
    vllm_lora_models = VLLM_LORA_MODELS.read_text(encoding="utf-8")
    vllm_transformers_models = VLLM_TRANSFORMERS_MODELS.read_text(encoding="utf-8")

    if "# AQLEVON_TF5_VISION_ALIAS" not in model:
        model = replace_once(
            model,
            "    AutoModelForVision2Seq,\n",
            "",
            "model_top_level_import",
        )
        model = replace_once(
            model,
            "from transformers.modeling_outputs import CausalLMOutputWithPast\n",
            "from transformers.modeling_outputs import CausalLMOutputWithPast\n"
            "\n# AQLEVON_TF5_VISION_ALIAS: Transformers 5 removed AutoModelForVision2Seq.\n"
            "AutoModelForVision2Seq = AutoModelForImageTextToText\n",
            "model_alias_anchor",
        )
        model = replace_once(
            model,
            "    from transformers import AutoModelForCausalLM, AutoModelForTokenClassification, AutoModelForVision2Seq\n",
            "    from transformers import AutoModelForCausalLM, AutoModelForTokenClassification\n",
            "model_valuehead_import",
        )

    if "# AQLEVON_TF5_VISION_ALIAS" not in fsdp:
        fsdp = replace_once(
            fsdp,
            "            AutoModelForImageTextToText,\n"
            "            AutoModelForVision2Seq,\n"
            "        )\n",
            "            AutoModelForImageTextToText,\n"
            "        )\n"
            "        # AQLEVON_TF5_VISION_ALIAS: preserve pinned SDPO semantics on Transformers 5.\n"
            "        AutoModelForVision2Seq = AutoModelForImageTextToText\n",
            "fsdp_model_import",
        )

    if "# AQLEVON_QWEN35_VLLM_TF_BACKEND" not in vllm_async:
        vllm_async = replace_once(
            vllm_async,
            "        engine_args = AsyncEngineArgs.from_cli_args(args)\n"
            "        usage_context = UsageContext.OPENAI_API_SERVER\n",
            "        engine_args = AsyncEngineArgs.from_cli_args(args)\n"
            "        # AQLEVON_QWEN35_VLLM_TF_BACKEND: vLLM 0.10.2 predates native Qwen3.5.\n"
            "        engine_args.model_impl = \"transformers\"\n"
            "        usage_context = UsageContext.OPENAI_API_SERVER\n",
            "vllm_server_transformers_backend",
        )
        vllm_async = replace_once(
            vllm_async,
            "        engine_args = vllm.AsyncEngineArgs.from_cli_args(args)\n"
            "        usage_context = UsageContext.OPENAI_API_SERVER\n",
            "        engine_args = vllm.AsyncEngineArgs.from_cli_args(args)\n"
            "        # AQLEVON_QWEN35_VLLM_TF_BACKEND: keep headless path identical.\n"
            "        engine_args.model_impl = \"transformers\"\n"
            "        usage_context = UsageContext.OPENAI_API_SERVER\n",
            "vllm_headless_transformers_backend",
        )

    vllm_lora_models = patch_vllm_lora_manager(vllm_lora_models)
    vllm_transformers_models = patch_vllm_transformers_mm_mapping(vllm_transformers_models)
    vllm_transformers_models = patch_vllm_transformers_mm_output(vllm_transformers_models)
    vllm_transformers_models = patch_vllm_qwen35_text_rollout(vllm_transformers_models)

    MODEL.write_text(model, encoding="utf-8")
    FSDP.write_text(fsdp, encoding="utf-8")
    VLLM_ASYNC.write_text(vllm_async, encoding="utf-8")
    VLLM_LORA_MODELS.write_text(vllm_lora_models, encoding="utf-8")
    VLLM_TRANSFORMERS_MODELS.write_text(vllm_transformers_models, encoding="utf-8")

    subprocess.run(
        ["python", "-m", "py_compile", str(MODEL), str(FSDP), str(VLLM_ASYNC), str(VLLM_LORA_MODELS), str(VLLM_TRANSFORMERS_MODELS)],
        check=True,
    )

    diff = subprocess.check_output(
        [
            "git", "-C", str(SDPO), "diff", "--",
            "verl/utils/model.py",
            "verl/workers/fsdp_workers.py",
            "verl/workers/rollout/vllm_rollout/vllm_async_server.py",
        ],
        text=True,
    )
    if not diff.strip():
        raise SystemExit("compat_patch_produced_no_diff")
    if "AQLEVON_QWEN35_VLLM_LORA_GUARD" not in vllm_lora_models:
        raise SystemExit("vllm_lora_guard_missing_after_patch")
    if "AQLEVON_QWEN35_MM_LORA_MAPPING" not in vllm_transformers_models:
        raise SystemExit("vllm_transformers_mm_mapping_missing_after_patch")
    if "AQLEVON_QWEN35_MM_OUTPUT_UNWRAP" not in vllm_transformers_models:
        raise SystemExit("vllm_transformers_mm_output_missing_after_patch")
    if "AQLEVON_QWEN35_TEXT_ROLLOUT_3D" not in vllm_transformers_models:
        raise SystemExit("vllm_qwen35_text_rollout_3d_missing_after_patch")

    print("AQLEVON_SDPO_TF5_COMPAT_PATCH_PASS")
    print("MODEL_SHA256:", sha256(MODEL))
    print("FSDP_SHA256:", sha256(FSDP))
    print("VLLM_ASYNC_SHA256:", sha256(VLLM_ASYNC))
    print("VLLM_LORA_MODELS_SHA256:", sha256(VLLM_LORA_MODELS))
    print("VLLM_TRANSFORMERS_MODELS_SHA256:", sha256(VLLM_TRANSFORMERS_MODELS))
    print("=== PATCH DIFF ===")
    print(diff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
