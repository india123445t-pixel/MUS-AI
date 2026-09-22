# AQLEVON Sovereign Runtime Connection Contract V1

Status: deployment/runtime contract for the public Workspace and Owner Core integration.

## 1. Runtime authority
AQLEVON's production inference authority is the owned AQLEVON model runtime.

The public application MUST NOT require OpenRouter, Groq, Gemini, Mistral, Cerebras, Hugging Face, or any other external AI-provider API key in order to operate its core chat/work features.

The enforced public runtime mode is:

```
self_hosted_only
```

External-provider environment variables may exist in historical infrastructure, but the public runtime contract must not route to them while this contract is active.

## 2. Direct model endpoint
The owned model runtime exposes an OpenAI-compatible chat-completions interface.

Required connection variable:

```
AQLEVON_MODEL_URL
```

Accepted values include either a base API URL or the full chat-completions endpoint, for example:

```
http://aqlevon-runtime:8000/v1
http://aqlevon-runtime:8000/v1/chat/completions
```

Optional variables:

```
AQLEVON_MODEL_NAME
AQLEVON_MODEL_HEALTH_URL
AQLEVON_MODEL_KEY
```

- `AQLEVON_MODEL_NAME` is the served model identifier. If omitted, the app uses the AQLEVON runtime default label.
- `AQLEVON_MODEL_HEALTH_URL` overrides automatic health discovery. If omitted, health is derived from the model endpoint origin as `/health`.
- `AQLEVON_MODEL_KEY` is optional and is only for protecting an owned/private AQLEVON endpoint. It is not an external provider credential.
- No model key may be requested or stored in the public browser UI.

## 3. Health contract
The owned runtime health endpoint must return an HTTP 2xx response when the model service is ready to accept inference.

The public Workspace is allowed to enable chat/work only when either:
1. the direct AQLEVON self-hosted health check is healthy, or
2. AQLEVON Commons reports at least one available authenticated worker connected to the owned model runtime.

A configured-but-unhealthy external provider MUST NOT make the public Workspace ready.

## 4. Inference request contract
The direct runtime must accept:

```json
{
  "model": "<AQLEVON_MODEL_NAME>",
  "messages": [{"role":"user","content":"..."}],
  "temperature": 0.4,
  "stream": false
}
```

and return an OpenAI-compatible response containing:

```json
{
  "model": "<served-model>",
  "choices": [
    {"message":{"role":"assistant","content":"..."}}
  ]
}
```

## 5. Commons worker contract
AQLEVON Commons is a transport/fallback for the same owned AQLEVON model, not a third-party inference provider.

Worker variables:

```
AQLEVON_COMMONS_WORKER_TOKEN
AQLEVON_MODEL_URL
AQLEVON_MODEL_NAME
AQLEVON_MODEL_KEY        # optional, owned endpoint only
```

The worker claims Commons jobs, calls the owned AQLEVON OpenAI-compatible endpoint, and returns the governed result.

The existing Commons edge endpoint binding is intentionally separate from the application's Supabase database binding and must not be silently replaced.

## 6. Public UI truth rules
Until the owned model runtime is healthy:
- Chat Send remains disabled.
- Work task Start remains disabled.
- UI must say AQLEVON model/runtime is not connected yet.
- It must not ask the user for OpenRouter or another external AI-provider key.
- Web Search, Deep Research, image generation, code execution, GitHub, scheduler, browser execution, and other adapters remain separately fail-closed unless their own trusted adapters are connected.

## 7. Deployment acceptance
The application is inference-ready only after all applicable checks pass:
1. `/api/status` reports `runtime_mode=self_hosted_only`, `sovereign_runtime=true`, and `external_provider_routing=false`.
2. `/api/inference-health` reports `runtime_mode=self_hosted_only` and `inference_ready=true` from AQLEVON self-hosted health.
3. OR `/api/commons/health` reports `available=true` with a real authenticated worker connected to the owned model.
4. A harmless live chat request returns an AQLEVON response.
5. No external AI-provider call appears in the sovereign-runtime regression tests.
6. Owner Core authentication and fail-closed adapter boundaries remain intact.

## 8. Non-goals
This contract does not select or alter training weights, Gene promotion, evaluation acceptance, GPU recipes, or model research. Those remain governed by the AQLEVON training/evaluation pipeline.

It only defines how the finished owned model connects to the application safely and truthfully.
