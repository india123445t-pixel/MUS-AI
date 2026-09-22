#!/usr/bin/env python3
from pathlib import Path
import hashlib
import py_compile
import subprocess

SDPO=Path("/opt/aqlevon/runtime/SDPO")
EXPECTED_COMMIT="7c457fc1b1f636ae794eb0362ba37d4743b06fbc"
MODEL=SDPO/"verl/utils/model.py"
FSDP=SDPO/"verl/workers/fsdp_workers.py"
VLLM_ASYNC=SDPO/"verl/workers/rollout/vllm_rollout/vllm_async_server.py"

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

    MODEL.write_text(model)
    FSDP.write_text(fsdp)
    VLLM_ASYNC.write_text(vllm_async)
    py_compile.compile(str(MODEL),doraise=True)
    py_compile.compile(str(FSDP),doraise=True)
    py_compile.compile(str(VLLM_ASYNC),doraise=True)

    if "AQLEVON_TF5_VISION_ALIAS" not in model or "AQLEVON_TF5_VISION_ALIAS" not in fsdp:
        raise SystemExit("tf5_alias_missing_after_patch")
    if "AQLEVON_QWEN35_NATIVE_V019_TEXT_LORA_BINDING" not in vllm_async:
        raise SystemExit("qwen35_native_v019_binding_missing_after_patch")

    print("AQLEVON_SDPO_TF5_NATIVE_VLLM019_PATCH_PASS")
    print("MODEL_SHA256:",sha256(MODEL))
    print("FSDP_SHA256:",sha256(FSDP))
    print("VLLM_ASYNC_SHA256:",sha256(VLLM_ASYNC))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
