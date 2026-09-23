#!/usr/bin/env python3
from pathlib import Path
import hashlib
import importlib.util
import py_compile
import subprocess

SDPO=Path("/opt/aqlevon/runtime/SDPO")
EXPECTED_COMMIT="7c457fc1b1f636ae794eb0362ba37d4743b06fbc"
MODEL=SDPO/"verl/utils/model.py"
FSDP=SDPO/"verl/workers/fsdp_workers.py"
VLLM_ASYNC=SDPO/"verl/workers/rollout/vllm_rollout/vllm_async_server.py"
VLLM_ROLLOUT=SDPO/"verl/workers/rollout/vllm_rollout/vllm_rollout.py"
VLLM_SPEC=importlib.util.find_spec("vllm")
if VLLM_SPEC is None or not VLLM_SPEC.submodule_search_locations:
    raise SystemExit("vllm_package_not_found")
VLLM_ROOT=Path(next(iter(VLLM_SPEC.submodule_search_locations)))
VLLM_LORA_BASE=VLLM_ROOT/"lora/layers/base.py"
VLLM_LORA_LOGITS=VLLM_ROOT/"lora/layers/logits_processor.py"
VLLM_LORA_MANAGER=VLLM_ROOT/"lora/model_manager.py"
VLLM_LORA_RUNNER=VLLM_ROOT/"v1/worker/lora_model_runner_mixin.py"

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n=text.count(old)
    if n != 1:
        raise SystemExit(f"{label}:expected_once:found_{n}")
    return text.replace(old,new,1)

def main() -> int:
    head=subprocess.check_output(["git","-C",str(SDPO),"rev-parse","HEAD"],text=True).strip()
    if head != EXPECTED_COMMIT:
        raise SystemExit(f"sdpo_commit_mismatch:{head}")

    model=MODEL.read_text()
    fsdp=FSDP.read_text()
    vllm_async=VLLM_ASYNC.read_text()
    vllm_rollout=VLLM_ROLLOUT.read_text()
    vllm_lora_base=VLLM_LORA_BASE.read_text()
    vllm_lora_logits=VLLM_LORA_LOGITS.read_text()
    vllm_lora_manager=VLLM_LORA_MANAGER.read_text()
    vllm_lora_runner=VLLM_LORA_RUNNER.read_text()

    if "# AQLEVON_TF5_VISION_ALIAS" not in model:
        model=replace_once(model,"    AutoModelForVision2Seq,\n","","model_top_level_import")
        model=replace_once(
            model,
            "from transformers.modeling_outputs import CausalLMOutputWithPast\n",
            "from transformers.modeling_outputs import CausalLMOutputWithPast\n"
            "\n# AQLEVON_TF5_VISION_ALIAS: Transformers 5 removed AutoModelForVision2Seq.\n"
            "AutoModelForVision2Seq = AutoModelForImageTextToText\n",
            "model_alias_anchor",
        )
        model=replace_once(
            model,
            "    from transformers import AutoModelForCausalLM, AutoModelForTokenClassification, AutoModelForVision2Seq\n",
            "    from transformers import AutoModelForCausalLM, AutoModelForTokenClassification\n",
            "model_valuehead_import",
        )

    if "# AQLEVON_TF5_VISION_ALIAS" not in fsdp:
        fsdp=replace_once(
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

    if "AQLEVON_VLLM019_WORKER_DISPATCH" not in vllm_rollout:
        vllm_rollout=replace_once(
            vllm_rollout,
            "        else:\n"
            "            return self.inference_engine.execute_method(method, *args, **kwargs)\n",
            "        else:\n"
            "            # AQLEVON_VLLM019_WORKER_DISPATCH: vLLM 0.19 removed\n"
            "            # WorkerWrapperBase.execute_method. Mirror vLLM 0.19's own\n"
            "            # UniProcExecutor collective_rpc dispatch via serial_utils.run_method.\n"
            "            if not hasattr(type(self.inference_engine), \"execute_method\"):\n"
            "                from vllm.v1.serial_utils import run_method\n"
            "                return run_method(self.inference_engine, method, args, kwargs)\n"
            "            return self.inference_engine.execute_method(method, *args, **kwargs)\n",
            "vllm019_worker_dispatch",
        )

    if "AQLEVON_VLLM019_PRESERVE_MAX_MODEL_LEN" not in vllm_async:
        vllm_async=replace_once(
            vllm_async,
            "        self.config.max_model_len = get_max_position_embeddings(self.model_config.hf_config)\n",
            "        # AQLEVON_VLLM019_PRESERVE_MAX_MODEL_LEN: pinned SDPO used to\n"
            "        # overwrite an explicit rollout max_model_len with the HF model maximum.\n"
            "        # Preserve the frozen 4096 contract; only infer when config is None.\n"
            "        max_position_embeddings = get_max_position_embeddings(self.model_config.hf_config)\n"
            "        if self.config.max_model_len is None:\n"
            "            self.config.max_model_len = max_position_embeddings\n"
            "        elif self.config.max_model_len > max_position_embeddings:\n"
            "            raise ValueError(\n"
            "                f\"max_model_len ({self.config.max_model_len}) should be less than or equal to \"\n"
            "                f\"max_position_embeddings ({max_position_embeddings})\"\n"
            "            )\n",
            "vllm019_preserve_max_model_len",
        )

    if "AQLEVON_QWEN35_NATIVE_V019_TEXT_LORA_BINDING" not in vllm_async:
        vllm_async=replace_once(
            vllm_async,
            "        if self.config.prometheus.enable:\n",
            "        # AQLEVON_QWEN35_NATIVE_V019_TEXT_LORA_BINDING: native Qwen3.5\n"
            "        # packs HF q/k/v into qkv_proj. Keep PEFT q/v targets unchanged;\n"
            "        # scope only the vLLM deployment wrapper and disable unused vision.\n"
            "        if getattr(self.model_config.hf_config, \"model_type\", None) == \"qwen3_5\":\n"
            "            args[\"language_model_only\"] = True\n"
            "            if self.model_config.lora_rank > 0:\n"
            "                args[\"lora_target_modules\"] = [\"qkv_proj\"]\n"
            "\n"
            "        if self.config.prometheus.enable:\n",
            "qwen35_native_v019_text_lora_binding",
        )

    # AQLEVON_VLLM019_LEVEL2_LORA_BACKPORT: minimal adaptation of upstream
    # vLLM PR #39935 (merged 2026-08-06) for v0.19.1. Do not flatten the
    # PyTorch module tree; delegate checkpoint loading through LoRA wrappers
    # and invalidate disposable LoRA GPU state after each base-weight replace.
    if "AQLEVON_VLLM019_LORA_WRAPPER_LOAD_WEIGHTS" not in vllm_lora_base:
        vllm_lora_base=replace_once(
            vllm_lora_base,
            "from typing import TYPE_CHECKING, overload\n",
            "from collections.abc import Iterable\n"
            "from typing import TYPE_CHECKING, overload\n",
            "vllm019_lora_base_iterable_import",
        )
        vllm_lora_base=replace_once(
            vllm_lora_base,
            "class BaseLayerWithLoRA(nn.Module):\n",
            "class BaseLayerWithLoRA(nn.Module):\n"
            "    # AQLEVON_VLLM019_LORA_WRAPPER_LOAD_WEIGHTS\n"
            "    def load_weights(\n"
            "        self, weights: Iterable[tuple[str, torch.Tensor]]\n"
            "    ) -> Iterable[str]:\n"
            "        \"\"\"Load checkpoint weights into the wrapped base layer.\"\"\"\n"
            "        base_load_weights = getattr(self.base_layer, \"load_weights\", None)\n"
            "        if callable(base_load_weights):\n"
            "            return base_load_weights(weights)\n"
            "        from vllm.model_executor.models.utils import AutoWeightsLoader\n"
            "        return AutoWeightsLoader(self.base_layer).load_weights(weights)\n"
            "\n",
            "vllm019_lora_wrapper_load_weights",
        )

    if "AQLEVON_VLLM019_LORA_LOGITS_MAPPING_RESET" not in vllm_lora_logits:
        vllm_lora_logits=replace_once(
            vllm_lora_logits,
            "        else:\n"
            "            self.sharded_to_full_mapping_gpu = None\n"
            "\n"
            "    def reset_lora(self, index: int):\n",
            "        else:\n"
            "            self.sharded_to_full_mapping_gpu = None\n"
            "\n"
            "    # AQLEVON_VLLM019_LORA_LOGITS_MAPPING_RESET\n"
            "    def reset_sharded_to_full_mapping(self) -> None:\n"
            "        mapping_gpu = self.sharded_to_full_mapping_gpu\n"
            "        if mapping_gpu is not None:\n"
            "            mapping_gpu.copy_(\n"
            "                torch.tensor(\n"
            "                    self.sharded_to_full_mapping,\n"
            "                    device=mapping_gpu.device,\n"
            "                    dtype=mapping_gpu.dtype,\n"
            "                )\n"
            "            )\n"
            "\n"
            "    def reset_lora(self, index: int):\n",
            "vllm019_lora_logits_mapping_reset",
        )

    if "AQLEVON_VLLM019_LORA_MANAGER_MAPPING_RESET" not in vllm_lora_manager:
        vllm_lora_manager=replace_once(
            vllm_lora_manager,
            "    def remove_all_adapters(self):\n"
            "        \"\"\"Remove all LoRAModels from the manager.\"\"\"\n"
            "        self._registered_adapters.clear()\n"
            "        self.lora_index_to_id = [None] * self.lora_slots\n"
            "        self._active_adapters.clear()\n",
            "    def remove_all_adapters(self):\n"
            "        \"\"\"Remove all LoRAModels from the manager.\"\"\"\n"
            "        self._registered_adapters.clear()\n"
            "        self.lora_index_to_id = [None] * self.lora_slots\n"
            "        self._active_adapters.clear()\n"
            "        # AQLEVON_VLLM019_LORA_MANAGER_MAPPING_RESET\n"
            "        self._last_mapping = None\n",
            "vllm019_lora_manager_mapping_reset",
        )

    if "AQLEVON_VLLM019_RESET_LORA_STATE" not in vllm_lora_runner:
        vllm_lora_runner=replace_once(
            vllm_lora_runner,
            "class LoRAModelRunnerMixin:\n"
            "    def load_lora_model(\n",
            "class LoRAModelRunnerMixin:\n"
            "    # AQLEVON_VLLM019_RESET_LORA_STATE\n"
            "    def reset_lora_state(self) -> None:\n"
            "        if not self.lora_config:\n"
            "            return\n"
            "        from vllm.lora.layers.logits_processor import LogitsProcessorWithLoRA\n"
            "        self.lora_manager.remove_all_adapters()\n"
            "        for module in self.get_model().modules():\n"
            "            if isinstance(module, LogitsProcessorWithLoRA):\n"
            "                module.reset_sharded_to_full_mapping()\n"
            "\n"
            "    def load_lora_model(\n",
            "vllm019_reset_lora_state",
        )

    if "AQLEVON_VLLM019_RESET_AFTER_DIRECT_BASE_LOAD" not in vllm_rollout:
        vllm_rollout=replace_once(
            vllm_rollout,
            "                model.load_weights(weights)\n",
            "                model.load_weights(weights)\n"
            "                # AQLEVON_VLLM019_RESET_AFTER_DIRECT_BASE_LOAD:\n"
            "                # SDPO bypasses GPUModelRunner.reload_weights(), so apply\n"
            "                # upstream PR #39935's post-base-replacement invariant here.\n"
            "                model_runner.reset_lora_state()\n",
            "vllm019_reset_after_direct_base_load",
        )

    MODEL.write_text(model)
    FSDP.write_text(fsdp)
    VLLM_ASYNC.write_text(vllm_async)
    VLLM_ROLLOUT.write_text(vllm_rollout)
    VLLM_LORA_BASE.write_text(vllm_lora_base)
    VLLM_LORA_LOGITS.write_text(vllm_lora_logits)
    VLLM_LORA_MANAGER.write_text(vllm_lora_manager)
    VLLM_LORA_RUNNER.write_text(vllm_lora_runner)
    py_compile.compile(str(MODEL),doraise=True)
    py_compile.compile(str(FSDP),doraise=True)
    py_compile.compile(str(VLLM_ASYNC),doraise=True)
    py_compile.compile(str(VLLM_ROLLOUT),doraise=True)
    py_compile.compile(str(VLLM_LORA_BASE),doraise=True)
    py_compile.compile(str(VLLM_LORA_LOGITS),doraise=True)
    py_compile.compile(str(VLLM_LORA_MANAGER),doraise=True)
    py_compile.compile(str(VLLM_LORA_RUNNER),doraise=True)

    if "AQLEVON_TF5_VISION_ALIAS" not in model or "AQLEVON_TF5_VISION_ALIAS" not in fsdp:
        raise SystemExit("tf5_alias_missing_after_patch")
    if "AQLEVON_QWEN35_NATIVE_V019_TEXT_LORA_BINDING" not in vllm_async:
        raise SystemExit("qwen35_native_v019_binding_missing_after_patch")
    if "AQLEVON_VLLM019_PRESERVE_MAX_MODEL_LEN" not in vllm_async:
        raise SystemExit("vllm019_preserve_max_model_len_missing_after_patch")
    if "AQLEVON_VLLM019_WORKER_DISPATCH" not in vllm_rollout:
        raise SystemExit("vllm019_worker_dispatch_missing_after_patch")
    if "AQLEVON_VLLM019_LORA_WRAPPER_LOAD_WEIGHTS" not in vllm_lora_base:
        raise SystemExit("vllm019_lora_wrapper_load_weights_missing_after_patch")
    if "AQLEVON_VLLM019_LORA_LOGITS_MAPPING_RESET" not in vllm_lora_logits:
        raise SystemExit("vllm019_lora_logits_mapping_reset_missing_after_patch")
    if "AQLEVON_VLLM019_LORA_MANAGER_MAPPING_RESET" not in vllm_lora_manager:
        raise SystemExit("vllm019_lora_manager_mapping_reset_missing_after_patch")
    if "AQLEVON_VLLM019_RESET_LORA_STATE" not in vllm_lora_runner:
        raise SystemExit("vllm019_reset_lora_state_missing_after_patch")
    if "AQLEVON_VLLM019_RESET_AFTER_DIRECT_BASE_LOAD" not in vllm_rollout:
        raise SystemExit("vllm019_reset_after_direct_base_load_missing_after_patch")

    print("AQLEVON_SDPO_TF5_NATIVE_VLLM019_PATCH_PASS")
    print("MODEL_SHA256:",sha256(MODEL))
    print("FSDP_SHA256:",sha256(FSDP))
    print("VLLM_ASYNC_SHA256:",sha256(VLLM_ASYNC))
    print("VLLM_ROLLOUT_SHA256:",sha256(VLLM_ROLLOUT))
    print("VLLM_LORA_BASE_SHA256:",sha256(VLLM_LORA_BASE))
    print("VLLM_LORA_LOGITS_SHA256:",sha256(VLLM_LORA_LOGITS))
    print("VLLM_LORA_MANAGER_SHA256:",sha256(VLLM_LORA_MANAGER))
    print("VLLM_LORA_RUNNER_SHA256:",sha256(VLLM_LORA_RUNNER))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
