#!/usr/bin/env python3
"""AQLEVON P4 compatibility repair for vLLM 0.10.2 with Transformers 5.x tokenizers."""
from __future__ import annotations
import hashlib
from importlib.metadata import version
from pathlib import Path

MARKER = "AQLEVON_VLLM_TRANSFORMERS5_TOKENIZER_COMPAT_PASS"
OLD = """    tokenizer_all_special_tokens_extended = (
        tokenizer.all_special_tokens_extended)
"""
NEW = """    # AQLEVON_VLLM_TRANSFORMERS5_TOKENIZER_COMPAT:
    # Transformers 5 removed all_special_tokens_extended. vLLM 0.10.2
    # only uses this cached value as a tokenizer property, so preserve the
    # v4 behavior when available and fall back to all_special_tokens on v5.
    tokenizer_all_special_tokens_extended = getattr(
        tokenizer, "all_special_tokens_extended", tokenizer_all_special_tokens
    )
"""

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    if version("vllm") != "0.10.2":
        raise SystemExit("vllm_version_mismatch:" + version("vllm"))
    import vllm.transformers_utils.tokenizer as tok
    target = Path(tok.__file__).resolve()
    text = target.read_text(encoding="utf-8")
    if "AQLEVON_VLLM_TRANSFORMERS5_TOKENIZER_COMPAT:" in text:
        raise SystemExit("vllm_tokenizer_patch_already_applied")
    if text.count(OLD) != 1:
        raise SystemExit("vllm_tokenizer_patch_anchor_count:" + str(text.count(OLD)))
    target.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    import py_compile
    py_compile.compile(str(target), doraise=True)
    patched = target.read_text(encoding="utf-8")
    for required in (
        "AQLEVON_VLLM_TRANSFORMERS5_TOKENIZER_COMPAT:",
        '"all_special_tokens_extended", tokenizer_all_special_tokens',
    ):
        if required not in patched:
            raise SystemExit("vllm_tokenizer_patch_missing:" + required)
    print(MARKER)
    print("VLLM_TOKENIZER_SHA256:", sha256(target))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
