#!/usr/bin/env python3
"""Apply the minimal Transformers-5 compatibility patch to pinned SDPO.

The pinned SDPO commit still imports AutoModelForVision2Seq, removed from
Transformers 5.17.0. This patch changes only those imports/usages needed by the
P4 training path, aliasing the removed class name to AutoModelForImageTextToText.
It does not modify model weights, data, training hyperparameters, or the Git HEAD.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

SDPO = Path("/workspace/SDPO")
EXPECTED_COMMIT = "7c457fc1b1f636ae794eb0362ba37d4743b06fbc"

MODEL = SDPO / "verl/utils/model.py"
FSDP = SDPO / "verl/workers/fsdp_workers.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected exactly one match, observed {n}")
    return text.replace(old, new, 1)


def main() -> int:
    head = subprocess.check_output(
        ["git", "-C", str(SDPO), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != EXPECTED_COMMIT:
        raise SystemExit(f"sdpo_commit_mismatch:{head}")

    model = MODEL.read_text(encoding="utf-8")
    fsdp = FSDP.read_text(encoding="utf-8")

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

    MODEL.write_text(model, encoding="utf-8")
    FSDP.write_text(fsdp, encoding="utf-8")

    subprocess.run(
        ["python", "-m", "py_compile", str(MODEL), str(FSDP)],
        check=True,
    )

    diff = subprocess.check_output(
        ["git", "-C", str(SDPO), "diff", "--", "verl/utils/model.py", "verl/workers/fsdp_workers.py"],
        text=True,
    )
    if not diff.strip():
        raise SystemExit("compat_patch_produced_no_diff")

    print("AQLEVON_SDPO_TF5_COMPAT_PATCH_PASS")
    print("MODEL_SHA256:", sha256(MODEL))
    print("FSDP_SHA256:", sha256(FSDP))
    print("=== PATCH DIFF ===")
    print(diff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
