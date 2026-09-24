#!/usr/bin/env python3
from pathlib import Path
import hashlib
import importlib.util
import inspect
import py_compile
import subprocess

SDPO=Path("/opt/aqlevon/runtime/SDPO")
EXPECTED_COMMIT="7c457fc1b1f636ae794eb0362ba37d4743b06fbc"
MODEL=SDPO/"verl/utils/model.py"
FSDP=SDPO/"verl/workers/fsdp_workers.py"
FSDP_UTILS=SDPO/"verl/utils/fsdp_utils.py"
VLLM_UTILS=SDPO/"verl/utils/vllm/utils.py"
VLLM_ASYNC=SDPO/"verl/workers/rollout/vllm_rollout/vllm_async_server.py"
VLLM_ROLLOUT=SDPO/"verl/workers/rollout/vllm_rollout/vllm_rollout.py"
AGENT_LOOP=SDPO/"verl/experimental/agent_loop/agent_loop.py"
VLLM_SPEC=importlib.util.find_spec("vllm")
VLLM_ROOT=(
    Path(next(iter(VLLM_SPEC.submodule_search_locations)))
    if VLLM_SPEC is not None and VLLM_SPEC.submodule_search_locations
    else None
)
VLLM_LORA_BASE=VLLM_ROOT/"lora/layers/base.py" if VLLM_ROOT else None
VLLM_LORA_LOGITS=VLLM_ROOT/"lora/layers/logits_processor.py" if VLLM_ROOT else None
VLLM_LORA_MANAGER=VLLM_ROOT/"lora/model_manager.py" if VLLM_ROOT else None
VLLM_LORA_RUNNER=VLLM_ROOT/"v1/worker/lora_model_runner_mixin.py" if VLLM_ROOT else None

def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n=text.count(old)
    if n != 1:
        raise SystemExit(f"{label}:expected_once:found_{n}")
    return text.replace(old,new,1)


def patch_sdpo_first_wake_base_sync_dedup(text: str) -> str:
    """Reuse the initial full-base snapshot and avoid loading it twice.

    At base_sync_done=False the earlier `params` collection is already the
    full base model. The sleep_level=2 branch used to collect the same full
    model again and then send both snapshots to the same direct load_weights
    path. Keep one snapshot and one load on the first wake; later cycles still
    collect/reload base weights separately from the LoRA-only `params`.
    """
    marker = "AQLEVON_SDPO_FIRST_WAKE_BASE_SYNC_DEDUP"
    if marker in text:
        return text

    old_base_collection = (
        '        if peft_config is not None and getattr(self.rollout, "sleep_level", None) == 2:\n'
        "            base_model_params = collect_lora_params(\n"
        "                module=self.actor_module_fsdp,\n"
        "                layered_summon=self.layered_summon,\n"
        "                base_sync_done=False,\n"
        "            )\n"
        "            base_model_params = {replace_lora_wrapper(k, peft_config): v for k, v in base_model_params.items()}\n"
        "            base_model_params = convert_weight_keys(\n"
        "                base_model_params, getattr(self.actor_module_fsdp, \"_fsdp_wrapped_module\", self.actor_module_fsdp)\n"
        "            )\n"
    )
    new_base_collection = (
        '        # AQLEVON_SDPO_FIRST_WAKE_BASE_SYNC_DEDUP\n'
        '        first_level2_base_sync = (\n'
        '            peft_config is not None\n'
        '            and getattr(self.rollout, "sleep_level", None) == 2\n'
        '            and not self.base_sync_done\n'
        '        )\n'
        '        if peft_config is not None and getattr(self.rollout, "sleep_level", None) == 2:\n'
        '            if first_level2_base_sync:\n'
        '                # `params` is already the full base snapshot on the first sync.\n'
        '                # Reuse it instead of gathering a second full model copy.\n'
        '                base_model_params = params\n'
        '                print("AQLEVON_SDPO_FIRST_WAKE_BASE_SNAPSHOT_REUSED", flush=True)\n'
        '            else:\n'
                '                base_model_params = collect_lora_params(\n'
                '                    module=self.actor_module_fsdp,\n'
                '                    layered_summon=self.layered_summon,\n'
        '                    base_sync_done=False,\n'
        '                )\n'
        '                base_model_params = {replace_lora_wrapper(k, peft_config): v for k, v in base_model_params.items()}\n'
        '                base_model_params = convert_weight_keys(\n'
        '                    base_model_params, getattr(self.actor_module_fsdp, "_fsdp_wrapped_module", self.actor_module_fsdp)\n'
        '                )\n'
    )
    text = replace_once(text, old_base_collection, new_base_collection, "sdpo_first_wake_base_snapshot")

    old_lora_update = (
        "        await self.rollout.update_weights(per_tensor_param, peft_config=peft_config, base_sync_done=self.base_sync_done)\n"
    )
    new_lora_update = (
        '        if first_level2_base_sync:\n'
        '            # The base snapshot was already applied through the sleep-level-2 path above.\n'
        '            # Do not apply the same full checkpoint a second time on the first wake.\n'
        '            print("AQLEVON_SDPO_FIRST_WAKE_DUPLICATE_BASE_LOAD_SKIPPED", flush=True)\n'
        '        else:\n'
        '            await self.rollout.update_weights(per_tensor_param, peft_config=peft_config, base_sync_done=self.base_sync_done)\n'
    )
    text = replace_once(text, old_lora_update, new_lora_update, "sdpo_first_wake_duplicate_load")
    return text


def patch_sdpo_lora_target_modules_save(text: str) -> str:
    """Preserve PEFT regex targets in the pinned SDPO checkpoint config."""
    marker = "AQLEVON_SDPO_LORA_TARGET_MODULES_PRESERVED"
    if marker in text:
        return text
    old = '                peft_config["target_modules"] = list(peft_config["target_modules"])\n'
    new = (
        "                target_modules = peft_config[\"target_modules\"]\n"
        "                # AQLEVON_SDPO_LORA_TARGET_MODULES_PRESERVED: keep regexes intact.\n"
        "                if isinstance(target_modules, str):\n"
        "                    peft_config[\"target_modules\"] = target_modules\n"
        "                    target_modules_kind = \"regex\"\n"
        "                elif isinstance(target_modules, (list, tuple, set)):\n"
        "                    peft_config[\"target_modules\"] = sorted(target_modules)\n"
        "                    target_modules_kind = \"list\"\n"
        "                else:\n"
        "                    raise TypeError(f\"unsupported_target_modules_type:{type(target_modules).__name__}\")\n"
        "                print(f\"AQLEVON_SDPO_LORA_TARGET_MODULES_PRESERVED type={target_modules_kind}\", flush=True)\n"
    )
    return replace_once(text, old, new, "sdpo_lora_target_modules_serialization")


def _aqlevon_extract_qwen35_lora_state_dict(full_state_dict, adapter_name="default"):
    """Extract the frozen Qwen3.5 q/v LoRA tensors from FSDP's raw state dict.

    PEFT 0.21 discovers adapter keys structurally from named_modules(). FSDP's
    nested wrapper names do not line up with the normalized root state-dict keys
    in this path, so that API can return an empty adapter state even when the
    raw FSDP state dict contains all 32 tensors. Normalize only the known
    default-adapter key segment and enforce the exact frozen target topology.
    """
    if not isinstance(adapter_name, str) or not adapter_name:
        raise RuntimeError("AQLEVON_FSDP_LORA_ADAPTER_NAME_INVALID")
    expected = {
        f"base_model.model.model.language_model.layers.{layer}.self_attn.{projection}.lora_{kind}.weight"
        for layer in (3, 7, 11, 15, 19, 23, 27, 31)
        for projection in ("q_proj", "v_proj")
        for kind in ("A", "B")
    }
    raw_keys = sorted(key for key in full_state_dict if ".lora_" in key)
    extracted = {}
    for key in raw_keys:
        for kind in ("A", "B"):
            suffix = f".lora_{kind}.{adapter_name}.weight"
            if not key.endswith(suffix):
                continue
            canonical = key[:-len(suffix)] + f".lora_{kind}.weight"
            if canonical in extracted:
                raise RuntimeError("AQLEVON_FSDP_LORA_DUPLICATE_KEY:" + canonical)
            extracted[canonical] = full_state_dict[key]
            break
    missing = sorted(expected - set(extracted))
    extra = sorted(set(extracted) - expected)
    if len(raw_keys) != 32 or missing or extra:
        raise RuntimeError(
            "AQLEVON_FSDP_LORA_STATE_KEYS:"
            f"raw={len(raw_keys)}:extracted={len(extracted)}:expected_32:"
            f"missing={missing[:4]}:extra={extra[:4]}"
        )
    return {key: extracted[key] for key in sorted(expected)}


def patch_sdpo_lora_state_sync(text: str) -> str:
    """Extract the frozen q/v LoRA state from the exact FSDP root state dict.

    Retry19X proved that PEFT 0.21's structural state-dict filter returns zero
    adapter tensors here although FSDP's raw state dict contains the exact 32
    keys. Normalize the default adapter segment directly and validate all 16
    Qwen3.5 full-attention q/v targets before the vLLM sync.
    """
    marker = "AQLEVON_SDPO_QWEN35_RAW_FSDP_LORA_STATE"
    if marker in text:
        return text
    extractor_marker = "def _aqlevon_extract_qwen35_lora_state_dict("
    if extractor_marker not in text:
        anchor = "def collect_lora_params("
        if text.count(anchor) != 1:
            raise SystemExit(f"sdpo_fsdp_lora_extractor_anchor:expected_once:found_{text.count(anchor)}")
        extractor_source = inspect.getsource(_aqlevon_extract_qwen35_lora_state_dict)
        text = text.replace(anchor, extractor_source + "\n\n" + anchor, 1)
    old = (
        "                if base_sync_done:\n"
        "                    lora_params = get_peft_model_state_dict(peft_model)\n"
        "                    lora_params = {\n"
        "                        name: param.full_tensor().detach().cpu()\n"
        "                        if hasattr(param, \"full_tensor\")\n"
        "                        else param.detach().cpu()\n"
        "                        for name, param in lora_params.items()\n"
        "                    }\n"
    )
    new = (
        "                if base_sync_done:\n"
        "                    # AQLEVON_SDPO_QWEN35_RAW_FSDP_LORA_STATE\n"
        "                    # PEFT's structural prefixes miss these FSDP-normalized keys.\n"
        "                    full_state_dict = module.state_dict()\n"
        "                    raw_lora_keys = sorted(k for k in full_state_dict if \".lora_\" in k)\n"
        "                    expected_lora_tensors = 32  # 16 frozen targets x (A,B)\n"
        "                    if len(raw_lora_keys) != expected_lora_tensors:\n"
        "                        raise RuntimeError(\n"
        "                            f\"AQLEVON_FSDP_LORA_RAW_STATE_COUNT:{len(raw_lora_keys)}:expected_32:\"\n"
        "                            f\"sample={raw_lora_keys[:8]}\"\n"
        "                        )\n"
        "                    lora_params = _aqlevon_extract_qwen35_lora_state_dict(\n"
        "                        full_state_dict, adapter_name=\"default\"\n"
        "                    )\n"
        "                    a_count = sum(\".lora_A.\" in k for k in lora_params)\n"
        "                    b_count = sum(\".lora_B.\" in k for k in lora_params)\n"
        "                    if len(lora_params) != expected_lora_tensors or (a_count, b_count) != (16, 16):\n"
        "                        raise RuntimeError(\n"
        "                            f\"AQLEVON_FSDP_LORA_AB_COUNT:count={len(lora_params)}:A={a_count}:B={b_count}:expected_32_16_16\"\n"
        "                        )\n"
        "                    print(\n"
        "                        f\"AQLEVON_SDPO_LORA_STATE_EXTRACTED count={len(lora_params)} A={a_count} B={b_count}\",\n"
        "                        flush=True,\n"
        "                    )\n"
        "                    lora_params = {\n"
        "                        name: param.full_tensor().detach().cpu()\n"
        "                        if hasattr(param, \"full_tensor\")\n"
        "                        else param.detach().cpu()\n"
        "                        for name, param in lora_params.items()\n"
        "                    }\n"
    )
    return replace_once(text, old, new, "sdpo_qwen35_fsdp_raw_lora_state")
def patch_sdpo_tensor_lora_sender(text: str) -> str:
    marker="AQLEVON_TENSOR_LORA_SYNC_COUNT"
    if marker in text:
        return text
    old="            weights = dict(weights)\n"
    new=(
        "            weights = dict(weights)\n"
        "            # AQLEVON_TENSOR_LORA_SYNC_COUNT: fail before vLLM if FSDP/PEFT\n"
        "            # extraction or key conversion lost any frozen adapter tensor.\n"
        "            expected_lora_tensors = 32\n"
        "            if len(weights) != expected_lora_tensors:\n"
        "                raise RuntimeError(\n"
        "                    f\"AQLEVON_TENSOR_LORA_SYNC_COUNT:{len(weights)}:expected_{expected_lora_tensors}:\"\n"
        "                    f\"sample={sorted(weights)[:8]}\"\n"
        "                )\n"
        "            a_count = sum(\".lora_A.\" in k for k in weights)\n"
        "            b_count = sum(\".lora_B.\" in k for k in weights)\n"
        "            if (a_count, b_count) != (16, 16):\n"
        "                raise RuntimeError(\n"
        "                    f\"AQLEVON_TENSOR_LORA_AB_COUNT:A={a_count}:B={b_count}:expected_16_16\"\n"
        "                )\n"
        "            print(\n"
        "                f\"AQLEVON_TENSOR_LORA_SYNC_PASS count={len(weights)} A={a_count} B={b_count}\",\n"
        "                flush=True,\n"
        "            )\n"
    )
    return replace_once(text, old, new, "sdpo_tensor_lora_sender_count")


def patch_sdpo_tensor_lora_loader(text: str) -> str:
    marker="AQLEVON_TENSOR_LORA_LOADER_NONEMPTY"
    if marker in text:
        return text
    old=(
        "                if isinstance(lora_request, TensorLoRARequest):\n"
        "                    lora = self._lora_model_cls.from_lora_tensors(\n"
        "                        tensors=lora_tensors,\n"
        "                        **lora_request_kwargs,\n"
        "                    )\n"
        "                else:\n"
    )
    new=(
        "                if isinstance(lora_request, TensorLoRARequest):\n"
        "                    lora = self._lora_model_cls.from_lora_tensors(\n"
        "                        tensors=lora_tensors,\n"
        "                        **lora_request_kwargs,\n"
        "                    )\n"
        "                    # AQLEVON_TENSOR_LORA_LOADER_NONEMPTY: Retry19W exposed\n"
        "                    # vLLM's later StopIteration when zero modules survive mapping.\n"
        "                    mapped = getattr(lora, \"loras\", None)\n"
        "                    if not mapped:\n"
        "                        raise RuntimeError(\n"
        "                            \"AQLEVON_TENSOR_LORA_MAPPING_EMPTY:\"\n"
        "                            f\"input_count={len(lora_tensors or {})}:\"\n"
        "                            f\"sample={sorted((lora_tensors or {}).keys())[:8]}\"\n"
        "                        )\n"
        "                else:\n"
    )
    return replace_once(text, old, new, "sdpo_tensor_lora_loader_nonempty")


def main() -> int:
    if VLLM_SPEC is None or VLLM_ROOT is None:
        raise SystemExit("vllm_package_not_found")

    head=subprocess.check_output(["git","-C",str(SDPO),"rev-parse","HEAD"],text=True).strip()
    if head != EXPECTED_COMMIT:
        raise SystemExit(f"sdpo_commit_mismatch:{head}")

    model=MODEL.read_text()
    fsdp=FSDP.read_text()
    fsdp_utils=FSDP_UTILS.read_text()
    vllm_utils=VLLM_UTILS.read_text()
    vllm_async=VLLM_ASYNC.read_text()
    vllm_rollout=VLLM_ROLLOUT.read_text()
    agent_loop=AGENT_LOOP.read_text()
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

    fsdp = patch_sdpo_first_wake_base_sync_dedup(fsdp)
    fsdp = patch_sdpo_lora_target_modules_save(fsdp)
    fsdp_utils = patch_sdpo_lora_state_sync(fsdp_utils)
    vllm_rollout = patch_sdpo_tensor_lora_sender(vllm_rollout)
    vllm_utils = patch_sdpo_tensor_lora_loader(vllm_utils)

    if "AQLEVON_QWEN35_TF5_MM_TOKEN_TYPE_IDS" not in agent_loop:
        old_rope = (
            '        image_grid_thw = multi_modal_inputs.get("image_grid_thw")\n'
            '        video_grid_thw = multi_modal_inputs.get("video_grid_thw")\n'
            '\n'
            "        # Model's get_rope_index has been dynamically bind to the processor.\n"
            '        vision_position_ids, _ = self.processor.get_rope_index(\n'
            '            input_ids=input_ids,\n'
            '            image_grid_thw=image_grid_thw,\n'
            '            video_grid_thw=video_grid_thw,\n'
            '            attention_mask=attention_mask,\n'
            '        )\n'
        )
        new_rope = (
            '        image_grid_thw = multi_modal_inputs.get("image_grid_thw")\n'
            '        video_grid_thw = multi_modal_inputs.get("video_grid_thw")\n'
            '        multi_modal_kwargs = {\n'
            '            "image_grid_thw": image_grid_thw,\n'
            '            "video_grid_thw": video_grid_thw,\n'
            '        }\n'
            '        # AQLEVON_QWEN35_TF5_MM_TOKEN_TYPE_IDS: Transformers 5.17 Qwen3.5\n'
            '        # requires mm_token_type_ids for get_rope_index. Mirror current VERL:\n'
            '        # rebuild modality IDs against the final padded input_ids instead of\n'
            '        # reusing processor-length tensors that may no longer align.\n'
            '        if multi_modal_inputs.pop("mm_token_type_ids", None) is not None:\n'
            '            mm_token_type_ids = torch.zeros_like(input_ids)\n'
            '            def _processor_token_id(token_name):\n'
            '                token_id = getattr(self.processor, f"{token_name}_token_id", None)\n'
            '                if token_id is not None:\n'
            '                    return int(token_id)\n'
            '                token = getattr(self.processor, f"{token_name}_token", None)\n'
            '                tokenizer = getattr(self.processor, "tokenizer", None)\n'
            '                if token is not None and tokenizer is not None:\n'
            '                    converted = tokenizer.convert_tokens_to_ids(token)\n'
            '                    if converted is not None:\n'
            '                        return int(converted)\n'
            '                return None\n'
            '            image_token_id = _processor_token_id("image")\n'
            '            video_token_id = _processor_token_id("video")\n'
            '            if image_token_id is not None:\n'
            '                mm_token_type_ids[0][input_ids[0] == image_token_id] = 1\n'
            '            if video_token_id is not None:\n'
            '                mm_token_type_ids[0][input_ids[0] == video_token_id] = 2\n'
            '            multi_modal_kwargs["mm_token_type_ids"] = mm_token_type_ids\n'
            '\n'
            "        # Model's get_rope_index has been dynamically bind to the processor.\n"
            '        vision_position_ids, _ = self.processor.get_rope_index(\n'
            '            input_ids=input_ids,\n'
            '            attention_mask=attention_mask,\n'
            '            **multi_modal_kwargs,\n'
            '        )\n'
        )
        agent_loop=replace_once(agent_loop, old_rope, new_rope, "qwen35_tf5_mm_token_type_ids")

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

    if "AQLEVON_SDPO_FIRST_WAKE_BASE_SYNC_DEDUP" not in fsdp:
        raise SystemExit("sdpo_first_wake_base_sync_dedup_missing_after_patch")
    if "AQLEVON_SDPO_LORA_TARGET_MODULES_PRESERVED" not in fsdp:
        raise SystemExit("sdpo_lora_target_modules_serialization_missing_after_patch")
    if "AQLEVON_SDPO_FSDP_EXPLICIT_LORA_STATE" not in fsdp_utils:
        raise SystemExit("sdpo_fsdp_explicit_lora_state_missing_after_patch")
    if "AQLEVON_TENSOR_LORA_SYNC_COUNT" not in vllm_rollout:
        raise SystemExit("tensor_lora_sender_count_missing_after_patch")
    if "AQLEVON_TENSOR_LORA_LOADER_NONEMPTY" not in vllm_utils:
        raise SystemExit("tensor_lora_loader_nonempty_missing_after_patch")

    MODEL.write_text(model)
    FSDP.write_text(fsdp)
    FSDP_UTILS.write_text(fsdp_utils)
    VLLM_UTILS.write_text(vllm_utils)
    VLLM_ASYNC.write_text(vllm_async)
    VLLM_ROLLOUT.write_text(vllm_rollout)
    AGENT_LOOP.write_text(agent_loop)
    VLLM_LORA_BASE.write_text(vllm_lora_base)
    VLLM_LORA_LOGITS.write_text(vllm_lora_logits)
    VLLM_LORA_MANAGER.write_text(vllm_lora_manager)
    VLLM_LORA_RUNNER.write_text(vllm_lora_runner)
    py_compile.compile(str(MODEL),doraise=True)
    py_compile.compile(str(FSDP),doraise=True)
    py_compile.compile(str(FSDP_UTILS),doraise=True)
    py_compile.compile(str(VLLM_UTILS),doraise=True)
    py_compile.compile(str(VLLM_ASYNC),doraise=True)
    py_compile.compile(str(VLLM_ROLLOUT),doraise=True)
    py_compile.compile(str(AGENT_LOOP),doraise=True)
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
    if "AQLEVON_QWEN35_TF5_MM_TOKEN_TYPE_IDS" not in agent_loop:
        raise SystemExit("qwen35_tf5_mm_token_type_ids_missing_after_patch")
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
    if "AQLEVON_SDPO_LORA_TARGET_MODULES_PRESERVED" not in fsdp:
        raise SystemExit("sdpo_lora_target_modules_serialization_missing_after_patch")

    print("AQLEVON_SDPO_TF5_NATIVE_VLLM019_PATCH_PASS")
    print("MODEL_SHA256:",sha256(MODEL))
    print("FSDP_SHA256:",sha256(FSDP))
    print("FSDP_UTILS_SHA256:",sha256(FSDP_UTILS))
    print("VLLM_UTILS_SHA256:",sha256(VLLM_UTILS))
    print("VLLM_ASYNC_SHA256:",sha256(VLLM_ASYNC))
    print("VLLM_ROLLOUT_SHA256:",sha256(VLLM_ROLLOUT))
    print("AGENT_LOOP_SHA256:",sha256(AGENT_LOOP))
    print("VLLM_LORA_BASE_SHA256:",sha256(VLLM_LORA_BASE))
    print("VLLM_LORA_LOGITS_SHA256:",sha256(VLLM_LORA_LOGITS))
    print("VLLM_LORA_MANAGER_SHA256:",sha256(VLLM_LORA_MANAGER))
    print("VLLM_LORA_RUNNER_SHA256:",sha256(VLLM_LORA_RUNNER))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
