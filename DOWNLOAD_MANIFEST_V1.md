# MUS AI — DOWNLOAD MANIFEST V1

Purpose: immutable acquisition record for the sovereign self-hosted model runtime. **No model weights are marked acquired until the pinned revision is downloaded and verified.**

## Target model

- repo: `Qwen/Qwen3.8-27B-FP8`
- exact revision: `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
- license: `Apache-2.0`
- serving runtime: `vLLM` OpenAI-compatible server
- pinned vLLM version for the first Modal runtime: `0.29.0`
- MUS runtime mode: `self_hosted_only`
- first context target: `4096` tokens
- Modal model volume: `mus-model-store`
- Modal vLLM cache volume: `mus-vllm-cache`
- server path: `/models/Qwen3.8-27B-FP8/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/`
- deployment definition: `infra/modal/sovereign_runtime.py`

## Acquisition inventory

The authoritative per-file inventory is generated only after download by `infra/modal/sovereign_runtime.py` and persisted as:

`/models/Qwen3.8-27B-FP8/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/MUS_RUNTIME_MANIFEST.json`

That runtime manifest records every downloaded file, byte size, and SHA-256 hash.

| repo | exact revision | file | SHA-256 | size bytes | server path | integrity test | pass/fail |
|---|---|---|---|---:|---|---|---|
| Qwen/Qwen3.8-27B-FP8 | 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a | PENDING DOWNLOAD | PENDING DOWNLOAD | PENDING DOWNLOAD | /models/Qwen3.8-27B-FP8/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a/ | SHA-256 + revision + manifest match | PENDING |

## Totals

- upstream repository size observed before acquisition: approximately `30.9 GB`
- total downloaded files: `PENDING DOWNLOAD`
- total downloaded size bytes: `PENDING DOWNLOAD`
- total downloaded size GiB: `PENDING DOWNLOAD`
- manifest generated at: `PENDING DOWNLOAD`
- downloaded by: `PENDING DOWNLOAD`

## First Modal runtime safety envelope

1. Run model acquisition on CPU first; do not start the L40S merely to download weights.
2. The first GPU definition is exactly one `L40S` with `max_containers=1` and `min_containers=0`.
3. The server scales to zero and uses a short idle shutdown window.
4. The HTTP server must require `MUS_MODEL_KEY` bearer authentication through the Modal secret `mus-model-runtime`.
5. Do not add OpenRouter, Gemini, Claude, OpenAI, Groq, Mistral, Cerebras, Hugging Face inference, or another external inference fallback to `self_hosted_only`.
6. Do not run a second paid GPU attempt without fresh owner approval.
7. Owner-authorized actual usage/spend cap for the first real experiment remains **USD $1 total**.

## Required validation before activation

1. Acquire only the exact repository revision above; never deploy floating `main` as the recorded artifact.
2. Record every downloaded model/config/tokenizer/template file and exact byte size.
3. Compute SHA-256 for every file after download and persist the generated runtime manifest.
4. Fail activation if any artifact, hash, size, repository identity, or revision differs from the manifest.
5. Start vLLM from the exact server path above with served model name `Qwen/Qwen3.8-27B-FP8`.
6. Run `npm run sovereign:test` before endpoint activation.
7. Run `npm run sovereign:eval` against the real endpoint and record reasoning, coding, Arabic, Moroccan Darija, tool-use, and latency results.
8. Verify `/health` and `/v1/chat/completions` return successfully through the self-hosted runtime.
9. Verify MUS uses `runtime_mode=self_hosted_only` and no external inference provider is contacted on either success or failure.
10. Mark pass/fail per artifact and per runtime test. Do not mark PASS from download success alone.

## Retention / deletion rule

- Keep the active immutable revision and the immediately previous known-good revision while rollback is required.
- Never delete the only known-good active artifact before a replacement passes integrity + health + sovereign evaluation.
- Delete failed/corrupt/incomplete revisions after evidence is retained (revision, hashes, failure reason, timestamps); do not reuse a directory that failed integrity verification.
- Credentials/API keys are never written into this manifest, model directory, logs, hashes, Git, or model metadata.
- Weight deletion is an explicit operator action; MUS/LLM text alone has no deletion authority.
