# AQLEVON — NEW CHAT START HERE / Recovery Handoff

**Created:** 2026-09-18 after a conversation-state glitch and full recovery audit.  
**Status:** AUTHORITATIVE ENTRYPOINT FOR THE NEXT CHAT  
**Purpose:** prevent restarting work, losing Library-only research, or confusing deployed product state with weight-development state.

---

## 0. Mandatory startup rule for the next chat

Before making any architectural/model/runtime change, read in this order:

1. `/AQLEVON/AQLEVON_NEW_CHAT_START_HERE_2026-09-18.md` — this file.
2. `/AQLEVON/AQLEVON_RECOVERY_SNAPSHOT_2026-09-18.md`.
3. `/AQLEVON/AQLEVON_MASTER_PROJECT_MAP.md` — newest sections first.
4. `/AQLEVON/AQLEVON_NEW_CHAT_HANDOFF.md` — newest sections first.
5. `/AQLEVON/Research/AQLEVON_FRONTIER_WEIGHT_STRATEGY_V6.md`.
6. `/AQLEVON/Research/AQLEVON_FRONTIER_WEIGHT_STRATEGY_V2.md`.
7. `/AQLEVON/Research/AQLEVON_CAPABILITY_COMPILER_V1.md`.
8. `/AQLEVON/Research/AQLEVON_EVOLUTION_LOOP_V1.md`.
9. `/AQLEVON/Implementation/WeightFactory/Genome/source_registry_v5.json`.
10. `/AQLEVON/Research/AQLEVON_PRODUCT_ECONOMICS_STRATEGY_V1.md`.

Then verify the current GitHub `main` and Production before writing anything.

Do **not** rely on remembered conversation order if it conflicts with these persisted artifacts.

---

## 1. Project identity and owner objective

Project/product/model family: **AQLEVON**.

Owner objective:
- a sovereign AI product, not a permanent wrapper over hosted proprietary APIs;
- own Workspace, BOS, tools, memory, verification, runtime and eventually versioned AQLEVON weight artifacts;
- commercially viable Free + Paid architecture with strong margins;
- frontier-model development based on measured capability gains, not slogans;
- ambition to compete with strong systems such as ChatGPT/Claude/Kimi/GLM/DeepSeek/Qwen-class systems, but **never claim superiority without frozen common-harness evidence**.

Core truth boundary:
**No new AQLEVON trained checkpoint exists yet.**
A real AQLEVON weight artifact requires a parameter-changing training run, non-zero delta, save/reload, hashes, provenance/data manifest, and frozen evaluation/regression gates.

---

## 2. Current production truth — verified during this recovery audit

Repository:
`india123445t-pixel/MUS-AI`

Current verified `main`:
`7f2a2ab46636e79dc7e733d6756ab77c94cd8ba8`

Latest commit message:
`docs: add AQLEVON autonomous evolution loop v1`

Open pull requests at audit time:
**none**.

Production deployment:
`dpl_WzpBRvJzDZJYmZyswE8EF7pq97D5`

Production state:
**READY**

Canonical public URL:
`https://mus-ai-probe.vercel.app`

Verified live behavior:
- `/` HTTP 200;
- renders the full AQLEVON Workspace, not the old simple-chat shell;
- navigation includes Chats / Projects / Work / Developer / Automations / Library / Apps & plugins / Settings;
- logo/icon are AQLEVON assets;
- old simple-chat shell is absent;
- production deployment SHA matches current `main` above.

Do not redo the old Workspace migration or simple-chat replacement.

---

## 3. AQLEVON Commons Runtime — deployed transport, no live worker yet

Commons transport is already implemented and merged. Do not rebuild it from scratch.

Architecture:
`Workspace -> /api/commons/chat -> existing /api/chat first -> on 503, Commons pull queue if a worker is active -> worker local OpenAI-compatible AQLEVON endpoint -> result -> conservative BOS governance`.

Implemented:
- Supabase queue/RPC layer;
- RLS + direct table access revoked;
- rate limits / queue cap / expiry / lease / retry controls;
- SHA-256 worker-token authentication;
- Supabase Edge Function `aqlevon-commons`;
- keyless public Commons client;
- `scripts/commons-worker.mjs` for llama.cpp/vLLM/OpenAI-compatible local endpoint;
- no inbound public port required for worker;
- `/api/commons/health` production route.

Current production health verified now:
- HTTP 200;
- `edge_reachable=true`;
- `active_workers=0`;
- `available=false`.

Interpretation:
**Transport is live; real persistent inference is not currently online because there is no active worker.**

Do not falsely claim public AQLEVON inference is operational until a real worker is attached.

---

## 4. Product economics strategy — LOCKED

Canonical Library document:
`/AQLEVON/Research/AQLEVON_PRODUCT_ECONOMICS_STRATEGY_V1.md`

GitHub mirror:
`docs/AQLEVON_PRODUCT_ECONOMICS_STRATEGY_V1.md`

Locked principles:
- Free must not mean paid GPU for every request;
- compute order: Local/Edge -> personal swarm -> Commons -> idle paid capacity -> cheap interruptible overflow -> trusted warm GPU;
- Free Paid-Compute Budget firewall;
- proposed budget control: `min(Fixed Marketing Budget, 10%–15% of MRR)` until real economics justify change;
- paid traffic preempts Free on trusted paid capacity;
- internal AQ Compute Units/Energy should meter GPU seconds, tokens, context, reasoning effort and tool/research cost;
- initial target inference COGS <= ~20% of subscription revenue on average;
- BYOC/Private and AQLEVON Edge are strategic high-margin paths;
- contributor rewards start as non-cash Compute Credits;
- pricing/quota remains provisional until real COGS benchmarks;
- sell outcomes/Workspace/Work/Research/Agents, not raw token price.

Do not reopen this strategy from zero unless the owner explicitly asks.

---

## 5. Sovereign/runtime base provenance — keep the two revisions separate

### Runtime frozen FP8 provenance
`Qwen/Qwen3.8-27B-FP8 @ 017b9c7af6b5689d5dd426a76e0bc077eb5ca20a`
Apache-2.0.
Previously acquired artifact: 81 files / 30,890,049,597 bytes.

### Weight-research laboratory base
`Qwen/Qwen3.8-27B @ 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
Apache-2.0.

Do not silently substitute one revision/model artifact for the other.

CPU sovereign protocol proof already exists with Qwen3.8-27B Q4 + llama.cpp. It proves protocol/routing feasibility, not final production performance and not the first trained AQLEVON checkpoint.

---

## 6. Physical weight milestone — still NOT completed

The next real model milestone is still:

**G1 / R0-A FIRST PARAMETER DELTA**

Existing implementation:
- `/AQLEVON/Implementation/WeightFactory/aqlevon_r0a_topology_probe.py`
- `/AQLEVON/Implementation/WeightFactory/aqlevon_r0a_one_step_probe.py`
- `/AQLEVON/Implementation/WeightFactory/README_WEIGHT_FACTORY_PREFLIGHT.md`

Required proof:
1. exact research base/revision;
2. compatible GPU;
3. BF16 LoRA preferred first path;
4. one optimizer step;
5. prove non-zero parameter delta;
6. save artifact;
7. reload artifact;
8. SHA256 hash;
9. target-module/topology identity proof;
10. frozen eval/regression checks;
11. full run/data/provenance manifest.

Until this passes, there are **no real new AQLEVON weights**.

---

## 7. Frontier weight research — IMPORTANT: Library is ahead of GitHub

Do not restart frontier research from V1.

### Library currently contains newer active research

Key files:
- `AQLEVON_FRONTIER_WEIGHT_STRATEGY_V6.md`
- `AQLEVON_FRONTIER_METHOD_REGISTRY_V6.json`
- `AQLEVON_FRONTIER_WEIGHT_STRATEGY_V2.md` — later extended Capability Forge research layer; do not assume filename number means older content is superseded
- `AQLEVON_CAPABILITY_COMPILER_V1.md`
- `AQLEVON_EVOLUTION_LOOP_V1.md`

V6 defines the Verified Capability Genome Program including:
- per-prompt verified teacher selection;
- merge-aware gene training;
- self-evolving curriculum;
- RLSVR/open-ended self-verifiable transformations;
- dedicated long-context gene;
- Capability Genome Bank;
- Interference Atlas;
- integration tournament;
- future sparse/MoE escalation;
- evidence-based teacher portfolio;
- frozen broad benchmark strategy.

V2 contains additional Capability Forge lanes including:
- cross-architecture/tokenizer distillation experiments with verified-output-only control arm;
- verifier-weighted curriculum;
- RLVR verifier hierarchy;
- adaptive reasoning/RPO experiments;
- evolutionary same-base merge search;
- MoE research;
- automated researcher loop;
- failure-conditioned teacher transfer;
- economics-aware training hypotheses.

**Do not arbitrarily declare V2 or V6 obsolete.** They are layered active research until explicitly consolidated by owner decision.

---

## 8. Capability Genome — current Library control plane

Path:
`/AQLEVON/Implementation/WeightFactory/Genome/`

Newest Library controls include:
- `source_registry_v5.json`
- `source_registry_v5_additions.json`
- `cross_arch_distillation_policy_v1.json`
- `evolutionary_merge_policy_v1.json`
- `adaptive_reasoning_policy_v1.json`
- `merge_safety_policy_v3.json`
- `interference_atlas.py`
- `test_interference_atlas.py`
- `test_frontier_policies.py`
- plus foundation: `genome_manifest_v2.json`, `capability_acquisition_matrix_v2.json`, `self_evolution_policy_v1.json`, `genome_gate.py`, `merge_safety_gate.py`, `merge_tournament_v1.json`, `expert_mesh_v1.json`.

Recovery-audit test rerun on 2026-09-18:
**26/26 PASS** across:
- `test_genome_gate.py`
- `test_merge_safety_gate.py`
- `test_interference_atlas.py`
- `test_frontier_policies.py`

Important: these tests verify control-plane logic/metadata gates, not frontier capability and not a trained checkpoint.

---

## 9. TeacherCouncil — implemented; do not rebuild

Path:
`/AQLEVON/Implementation/WeightFactory/TeacherCouncil/`

Current system includes:
- local/open-weight teacher registry;
- routing;
- candidate collection;
- objective verifier layer;
- training-mix builder;
- adversarial seed generation;
- public-data intake gate;
- protected-eval exclusions.

Recovery-audit rerun with correct package layout:
**9/9 PASS** across:
- `test_teacher_council.py`
- `test_router.py`
- `test_data_gate.py`.

Do not rebuild TeacherCouncil from zero. Evolve it toward the verified per-prompt Teacher Swarm defined in frontier research.

Training-output policy remains fail-closed:
- hosted OpenAI/Claude/Gemini outputs are denied for competitive-model training harvest under the currently recorded policy;
- open-weight/local teachers may be used only according to the source/license registry;
- protected benchmark data never enters training.

---

## 10. Exact GitHub vs Library synchronization gap

Current GitHub `main` contains, among other frontier artifacts:
- `docs/AQLEVON_FRONTIER_WEIGHT_STRATEGY_V1.md` through `V5.md`;
- `docs/AQLEVON_FRONTIER_METHOD_REGISTRY_V1.json` and `V5.json`;
- `docs/AQLEVON_CAPABILITY_COMPILER_V1.md`;
- `docs/AQLEVON_EVOLUTION_LOOP_V1.md`;
- Genome baseline including `source_registry_v2.json`, `source_registry_v3.json`, `merge_safety_policy_v2.json`, `merge_safety_gate.py`, `test_merge_safety_gate.py`, `capability_acquisition_matrix_v2.json`.

At recovery-audit time, GitHub **does not contain** the newest Library-only frontier controls, including:
- `AQLEVON_FRONTIER_WEIGHT_STRATEGY_V6.md`;
- `AQLEVON_FRONTIER_METHOD_REGISTRY_V6.json`;
- `source_registry_v4.json`;
- `source_registry_v5.json`;
- `source_registry_v5_additions.json`;
- `merge_safety_policy_v3.json`;
- `interference_atlas.py` + test;
- `cross_arch_distillation_policy_v1.json`;
- `evolutionary_merge_policy_v1.json`;
- `adaptive_reasoning_policy_v1.json`;
- `test_frontier_policies.py`.

**This synchronization gap is intentional/known and must not be forgotten.**
A Library file existing does not mean it is deployed or mirrored in GitHub.

---

## 11. Current branch/PR caution

Open PRs at audit time: **none**.

Repository still contains historical branches including:
- `feature/aqlevon-commons-runtime-v0`
- `release/aqlevon-workspace-v1`
- `release/workspace-public-ui`
- `research/frontier-weight-foundry-v3`
- `research/frontier-weight-v4`
- CPU experiment branches and old fix/backup branches.

Do not merge or delete historical branches merely because they exist. `main` is the deployed source unless a new explicitly reviewed branch is created.

---

## 12. What not to redo

Do not redo from scratch:
- AQLEVON branding/logo/icon migration;
- full Workspace port to Production;
- removal of old simple-chat shell;
- PWA cache retirement;
- Supabase public-client restoration;
- Commons queue / Edge Function / worker transport;
- product-economics strategy;
- CPU sovereign protocol proof;
- WeightFactory R0-A topology/one-step probes;
- TeacherCouncil V1;
- training-data intake gate;
- benchmark harness/data-manifest groundwork;
- Capability Genome baseline;
- merge-safety/interference policies already present;
- Frontier V1–V6 research from scratch;
- Capability Compiler V1;
- Evolution Loop V1.

---

## 13. What the next chat should do first

### If no compatible GPU is available
The first useful non-duplicative task is:

**SYNC REVIEW GATE:** review the Library-only frontier control files listed in Section 10 and mirror only the accepted/current ones into GitHub on a dedicated branch/PR, preserving hashes and without declaring research recipes production-ready.

Then:
- audit unresolved licenses/code availability for research-only methods;
- consolidate V2 + V6 only if owner explicitly wants a canonical V7; preserve every accepted constraint;
- prepare smallest deterministic R0-A training shard/run manifest;
- improve verifier/benchmark/data-contamination infrastructure without touching protected eval answers.

### If a compatible GPU becomes available
Do **not** begin a long training run.
Run only the G1 / R0-A one-step parameter-delta proof first.
If it fails/OOMs/numerically breaks, record the failure; do not silently change base/revision/template/precision.

---

## 14. Model-development strategy boundary

The project is trying to collect **capabilities**, not illegally/incompatibly splice arbitrary tensors.

Allowed/high-leverage mechanisms include:
- exact-same-base LoRA/adapters/deltas;
- compatible task-vector / TIES / DARE / controlled merge experiments;
- behavior distillation from legally usable open/local teachers;
- objective-verifier filtered synthetic data;
- RLVR / executable rewards;
- self-play / self-evolving curricula;
- cross-architecture distillation only as controlled output/representation experiments, never direct incompatible tensor splice;
- later architecture/MoE escalation after the 27B laboratory proves recipes.

Never treat teacher majority vote as truth. Objective verification outranks teacher reputation.

---

## 15. Frozen claims policy

Never claim:
- “AQLEVON is stronger than ChatGPT/Kimi/Claude/etc.” without frozen, common, contamination-safe evidence;
- “new AQLEVON weights exist” without real parameter delta + save/reload/hash/eval;
- “public inference is live” while Commons has zero workers and no self-hosted endpoint;
- “Library research is deployed” unless it is actually mirrored/merged/deployed.

---

## 16. Exact recovery-audit evidence captured now

Verified during this recovery pass:
- GitHub `main`: `7f2a2ab46636e79dc7e733d6756ab77c94cd8ba8`.
- no open PRs.
- Vercel Production deployment: `dpl_WzpBRvJzDZJYmZyswE8EF7pq97D5`, READY, same Git SHA.
- public Workspace `/`: HTTP 200, full Workspace UI.
- `/api/commons/health`: HTTP 200, `edge_reachable=true`, `active_workers=0`, `available=false`.
- Library Genome tests: **26/26 PASS**.
- Library TeacherCouncil tests: **9/9 PASS** with correct package layout.
- Library contains frontier files newer than GitHub, especially V6 + Genome v4/v5-era controls.
- no trained AQLEVON checkpoint yet.

---

## 17. Single-sentence continuation instruction

**Continue AQLEVON from the persisted Recovery/Frontier state; do not restart research or product migration; first reconcile the Library-only frontier control plane with GitHub (unless a compatible GPU is immediately available, in which case run only the G1 one-step parameter-delta proof), and never claim new weights or public inference before the corresponding evidence exists.**
