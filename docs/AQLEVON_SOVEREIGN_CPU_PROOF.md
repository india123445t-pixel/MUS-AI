# AQLEVON Sovereign CPU Proof

Date: 2026-09-17
Repository: `india123445t-pixel/MUS-AI`
Branch: `experiment/aqlevon-cpu-sovereign-proof`
Workflow: `.github/workflows/aqlevon-cpu-sovereign-proof.yml`
Successful run: `35257757091`
Successful job: `105325519460`
Commit under test: `495513d953c17a6b0234890273a9d2e52322dab5`

## What this proves

AQLEVON successfully ran a local, private, OpenAI-compatible inference endpoint inside a standard GitHub Actions Linux runner using `llama.cpp` and a quantized Qwen3.8-27B GGUF artifact.

The successful path was:

`GitHub Actions runner -> llama.cpp -> local 127.0.0.1:8080 -> /v1/chat/completions -> AQLEVON-27B alias -> response`

Observed successful response:

```json
{"choices":[{"finish_reason":"stop","index":0,"message":{"role":"assistant","content":"OK"}}],"model":"AQLEVON-27B","object":"chat.completion"}
```

The workflow emitted:

`AQLEVON_OPENAI_COMPATIBLE_HTTP_PASS`

## Runtime facts

- Model artifact: `ggml-org/Qwen3.8-27B-GGUF`
- File: `Qwen3.8-27B-Q4_K_M.gguf`
- Artifact size observed: `18,973,870,432` bytes
- llama.cpp version observed: `0.4.1-dev`, commit `972d231`
- Runner CPU count: 4
- Runner RAM: ~15 GiB
- Swap: 3 GiB
- Endpoint bind: `127.0.0.1:8080`
- Context size used: 256
- Reasoning disabled for deterministic smoke test:
  - `--reasoning off`
  - `--reasoning-budget 0`
  - `--no-reasoning-preserve`

## Performance observed

For the successful smoke request:

- prompt tokens: 15
- completion tokens: 2
- total tokens: 17
- prompt eval time: ~60.15 s
- completion eval time: ~25.22 s
- total inference time: ~85.37 s

This proves functional CPU inference, but standard GitHub Actions is far too slow to be treated as a practical always-on AQLEVON serving engine.

## Important provenance boundary

This is a sovereign runtime/protocol proof using a quantized GGUF derivative of `Qwen/Qwen3.8-27B`.

It is **not** the final proof for the frozen upstream checkpoint:

`Qwen/Qwen3.8-27B-FP8`

Frozen revision:

`017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`

The exact FP8 provenance/runtime gate remains separate and must not be claimed as satisfied by this GGUF run.

## Engineering conclusion

The GitHub-native architecture is now technically validated for zero-cost sovereign OpenAI-compatible inference. GitHub Actions should remain a bounded CI/proof mechanism. The next practical runtime target is a larger CPU/RAM GitHub Codespace or a future accelerator host, while preserving `self_hosted_only` and fail-closed routing.
