#!/usr/bin/env python3
"""Install AQLEVON P4 startup compatibility for every Python/Ray worker.

The pinned SDPO commit imports Transformers symbols removed in Transformers 5.17.
Ray workers are fresh Python interpreters, so launch-time PYTHONPATH/runtime-env
injection is too late for startup sitecustomize semantics. This installer writes
one .pth file into the active interpreter site-packages so every future Python
process adds the versioned AQLEVON compatibility directories before Python loads
sitecustomize.

This changes no model weights, data, training hyperparameters, or SDPO Git HEAD.
"""
from __future__ import annotations

import hashlib
import site
from pathlib import Path

AGENT03 = Path("/workspace/MUS-AI/research/weight_factory/agent03")
RUNTIME_COMPAT = AGENT03 / "runtime_compat"
PTH_NAME = "aqlevon_p4_runtime_compat.pth"


def payload() -> str:
    return str(RUNTIME_COMPAT) + "\n" + str(AGENT03) + "\n"


def main() -> int:
    if not (RUNTIME_COMPAT / "sitecustomize.py").is_file():
        raise SystemExit("missing_runtime_compat_sitecustomize")
    candidates = [Path(p) for p in site.getsitepackages()]
    if not candidates:
        raise SystemExit("no_sitepackages_found")
    target_dir = candidates[0]
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / PTH_NAME
    data = payload()
    target.write_text(data, encoding="utf-8")
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
    print("AQLEVON_P4_PTH:", target)
    print("AQLEVON_P4_PTH_SHA256:", digest)
    print("AQLEVON_P4_PTH_INSTALL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
