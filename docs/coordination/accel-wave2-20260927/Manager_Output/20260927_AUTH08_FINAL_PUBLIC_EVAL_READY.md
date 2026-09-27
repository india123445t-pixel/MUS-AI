# AQLEVON Auth08 — Final Public Evaluation READY

Timestamp: 2026-09-27
Manager state: **READY_FOR_ONE_PAID_UNIFIED_PUBLIC_EVAL**

## Candidate

- model: AQLEVON-27B-R0
- base: Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
- adapter SHA256: 5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74
- adapter-state SHA256: 1e3ff8a0fbc88686a2d96f93d4f04fdd66db2034ffdfafc2cc91e532ed0bf80f
- candidate-manifest SHA256: e020c6b140ffba104d1fe4485333fb225afd29c52dc03bf9a62d0f8c614e01c5
- durable candidate artifact ID: 10936543533

## Evaluation preparation completed

### Frozen structural generalization

Prep branch:
manager/auth08-generalization-eval-prep-20260927

CPU run:
36338123679 — SUCCESS

Prepared manifest:
25fa2777010255bd8d91431632ba65d72355340086250fe4bce8dffa64e33b0f

Matrix:
- 16 tasks
- 4 common seeds
- base + candidate
- 64 attempts/system
- 128 attempts total

### Frozen paired public evaluation

Prep branch:
manager/auth08-paired-public-eval-prep-20260927

CPU run:
36338128347 — SUCCESS

Binding SHA256:
b5f26e20bcdd13cead301623cc5e3496e231b32418a98c895e31db5dfdf9a888

Scientific contract:
484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d

Matrix:
- 56 public held-out tasks/system
- 2 common seeds/task
- 112 attempts/system
- 224 attempts total

## Unified evaluator

Branch:
manager/auth08-unified-eval-20260927

Free preflight run:
36338875829 — SUCCESS

The single runner now:
1. loads exact 27B base once;
2. executes frozen generalization base attempts;
3. executes paired-public base attempts;
4. attaches exact Auth08 LoRA;
5. executes the same frozen candidate matrices;
6. emits exactly 352 dispatches total;
7. retries no dispatched model answer;
8. returns raw outputs and a runtime receipt;
9. scores both frozen protocols on GitHub CPU;
10. emits one combined public verdict.

Control-plane hardening:
- fixed single-flight concurrency;
- fresh single-use evaluation authorization required;
- no historical/private W05 material;
- candidate/prep identities hash-bound before provider create;
- encrypted runpodctl send/receive transfer for adapter/prep bundle;
- <= USD 1.60/hour A100 gate;
- <= 3300 billed seconds;
- <= USD 1.50 per evaluation-run ceiling;
- fail-closed pod stop on controller error;
- evidence must upload durably before pod deletion;
- command currently read-only status;
- no paid eval has been authorized or launched by this preparation.

## Remaining gate

The next action is one paid A100 evaluation run only.

A fresh explicit paid authorization is required because the prior USD 4 standing retry authority terminated when the target training run succeeded.

Recommended authorization:
- one fresh Auth08 unified public evaluation
- max total cost USD 1.50
- max hourly rate USD 1.60
- max billed seconds 3300

No further training is planned.

## Truth boundary after the run

If both frozen public evaluations pass, this supplies strong independent public/generalization evidence.

It still does not reconstruct or substitute historical W05 sealed evaluation. Any canonical private promotion claim remains a separate governance gate.

**FINAL: READY_FOR_ONE_PAID_UNIFIED_PUBLIC_EVAL**
