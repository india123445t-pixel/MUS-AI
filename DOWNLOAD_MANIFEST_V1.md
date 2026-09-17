# MUS AI — DOWNLOAD MANIFEST V1

Purpose: immutable acquisition record for the future sovereign self-hosted model runtime. This file is a manifest template only. **No model weights were downloaded by Sovereign Runtime Prep v1.**

## Target model

- repo: `Qwen/Qwen3.8-27B-FP8`
- exact revision: `PENDING — pin an immutable Hugging Face commit SHA before download`
- serving runtime: `vLLM` OpenAI-compatible server
- MUS runtime mode: `self_hosted_only`
- server path: `PENDING — recommended: /srv/mus/models/Qwen3.8-27B-FP8/<REVISION>/`

## Acquisition inventory

| repo | exact revision | file | SHA-256 | size bytes | server path | integrity test | pass/fail |
|---|---|---|---|---:|---|---|---|
| Qwen/Qwen3.8-27B-FP8 | PENDING | PENDING | PENDING | PENDING | PENDING | sha256 + manifest match | PENDING |

## Totals

- total files: `PENDING`
- total size bytes: `PENDING`
- total size GiB: `PENDING`
- manifest generated at: `PENDING`
- downloaded by: `PENDING`

## Required validation before activation

1. Pin the repository to an immutable exact revision/commit SHA; never deploy floating `main` as the recorded production artifact.
2. Record every downloaded model/config/tokenizer/template file and exact byte size.
3. Compute SHA-256 for every file after download and after transfer to the GPU server.
4. Fail activation if any file, hash, size, or revision differs from this manifest.
5. Start vLLM with the exact server path/revision and exact served model name.
6. Run `npm run sovereign:test` before endpoint activation.
7. Run `npm run sovereign:eval` against the real endpoint and record reasoning, coding, Arabic, Moroccan Darija, tool-use, and latency results.
8. Mark pass/fail per artifact and per runtime test. Do not mark PASS from download success alone.

## Retention / deletion rule

- Keep the active immutable revision and the immediately previous known-good revision while rollback is required.
- Never delete the only known-good active artifact before a replacement passes integrity + health + sovereign evaluation.
- Delete failed/corrupt/incomplete revisions after evidence is retained (revision, hashes, failure reason, timestamps); do not reuse a directory that failed integrity verification.
- Credentials/API keys are never written into this manifest, model directory, logs, or hashes.
- Weight deletion is an explicit operator action; MUS/LLM text alone has no deletion authority.
