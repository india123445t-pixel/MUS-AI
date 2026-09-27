# AGENT 03 — 27B TRAINER / CONTROL-PLANE HARDENING AUDIT

FREE-ONLY. No paid GPU.

Mission:
Independently audit the exact trainer/control path that produced AQLEVON-27B-R0.

Audit:
- model/revision/precision pins
- Qwen architecture class
- 32 q/v LoRA targets
- 1,507,328 trainable params
- dataset split / no sealed leakage
- loss masking / sequence construction
- optimizer/LR schedule
- baseline vs final eval comparability
- save/reload hash
- timeout/budget/cleanup
- artifact export order
- concurrency/single-use authorization

Run all free syntax/unit/static tests. Patch only a dedicated branch. Do not change the recipe merely to improve metrics.

Write timestamped reports under docs/coordination/accel-wave-20260927/Agent_03_Output/.
