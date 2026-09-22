#!/usr/bin/env python3
from pathlib import Path
import hashlib
import py_compile
import subprocess

SDPO=Path("/opt/aqlevon/runtime/SDPO")
EXPECTED_COMMIT="7c457fc1b1f636ae794eb0362ba37d4743b06fbc"
MODEL=SDPO/"verl/utils/model.py"
FSDP=SDPO/"verl/workers/fsdp_workers.py"

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

    MODEL.write_text(model)
    FSDP.write_text(fsdp)
    py_compile.compile(str(MODEL),doraise=True)
    py_compile.compile(str(FSDP),doraise=True)

    if "AQLEVON_TF5_VISION_ALIAS" not in model or "AQLEVON_TF5_VISION_ALIAS" not in fsdp:
        raise SystemExit("tf5_alias_missing_after_patch")

    print("AQLEVON_SDPO_TF5_NATIVE_VLLM019_PATCH_PASS")
    print("MODEL_SHA256:",sha256(MODEL))
    print("FSDP_SHA256:",sha256(FSDP))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
