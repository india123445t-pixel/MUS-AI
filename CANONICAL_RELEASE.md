# AQLEVON Canonical Unified Release — 2026-09-25

This branch is the single deployment source for the current AQLEVON product surface.

Canonical source:
- `main` (production)
- RunPod endpoint ID `qyb4is6cl1hn22` is non-secret and has a code fallback; only the server-side inference key remains secret.

Included current surfaces:
- Public Workspace: `/`, `/chat`, projects, work, developer, scheduled, library, plugins, settings.
- Owner Control Center: `/admin`.
- Child Lab: `/admin/child-lab`.
- Sovereign inference route: exact frozen Auth16 through RunPod Serverless.
- Public and Child Lab share the same frozen Auth16 weights but use separate prompt/runtime contracts.
- Worker03/P4 training state is not writable from the UI/runtime.

Runtime policy:
- RunPod Serverless Flex.
- workers_min = 0.
- workers_max = 1.
- idle timeout = 5 seconds.
- no network volume.
- no always-on Pod.
- no external model fallback.
- API secret remains server-side only.

Frozen model:
- Base: Qwen/Qwen3.5-4B-Base @ daa9c16f371249f9ad1c75a9ed6f956c08ea08f5
- Adapter SHA256: 2d4f0c3528129e702dfa0af27fad467d411f355b9ea72e771942d0f6703e2b2a
- Candidate: Auth16
- Public shadow: 3/28 -> 28/28
- Status: Public-verified; Worker05 sealed evaluation still separate.

Historical research/evidence remains in the repository because it is required for provenance and reproducibility. Obsolete packaged UI copies are removed from this release branch.


## Production publication receipt — 2026-09-26

- Production merge commit: `c69ee465d9bd34acd6bc26e661c827769773b462`.
- Workspace Sovereign Readiness CI: PASS on production merge.
- GitHub Pages build/deployment: PASS on production merge.
- Canonical serverless endpoint: `qyb4is6cl1hn22`.
- Serverless policy: workers_min=0, workers_max=1, idle_timeout=5s.
- Public runtime and Child Lab runtime remain fail-closed until their server-side inference credentials are accepted by RunPod.
