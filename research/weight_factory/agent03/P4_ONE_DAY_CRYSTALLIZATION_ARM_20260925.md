# AQLEVON One-Day Verified-Trajectory Crystallization Arm

Status: FROZEN DESIGN BEFORE PAID TRAINING

This arm is conditional on the public pass@N probe returning `MATERIAL_LATENT_CAPABILITY`.
It does not use Worker05 sealed/private evaluation and it does not change the base model.

## Data boundary
- Training source: verifier-passed outputs from PUBLIC `discovery` only.
- PUBLIC `shadow` is never used for gradient updates.
- Worker05 is untouched until a packaged adapter passes the public shadow gate.
- Repair outputs may be used only when the deterministic verifier marked them passed.

## Frozen training recipe
- Base: Qwen/Qwen3.5-4B-Base @ daa9c16f371249f9ad1c75a9ed6f956c08ea08f5
- BF16, no quantization.
- LoRA r=4 alpha=4, q_proj/v_proj only on full-attention layers 3,7,11,15,19,23,27,31.
- 16 target modules / 32 A+B tensors / 458,752 trainable parameters.
- Up to 24 unique verified discovery trajectories, deterministic seed 1701, no repeats.
- One optimizer update per verified trajectory.
- AdamW, initial LR 1e-5 cosine-decay to 1e-6, weight decay 0.05.
- Supervise answer JSON only; prompt tokens masked.

## Public acceptance gate
Evaluate the 28 PUBLIC shadow tasks before and after training with identical seeds and the probe's generation settings.
The adapter is marked ready for Worker05 only if:
- post-training shadow pass@1 improves by >= 0.10 absolute, AND
- at least 3 additional shadow tasks pass.

This public gate is not a capability claim. Worker05 remains the independent truth gate.

## Spend rule
No paid training unless Auth05 produces a durable material probe result and a separately bounded single-use Auth06 is created under the owner's fresh $5 envelope.
