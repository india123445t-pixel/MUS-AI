# AQLEVON 27B Fresh Run — Manager GO Packet

Timestamp: 2026-09-27
Manager verdict: **GO_TO_REQUEST_FRESH_AUTH**
Paid execution status: **NOT AUTHORIZED / NOT STARTED**

## Live control-plane state

Operational branch:
`ops/runpod-control-v1`

Agent 01 accepted control-plane head was fast-forwarded into the operational branch with no force push.

Manager read-only preflight:
- trigger commit: `f3fecca9ce9efffce63f84b2b9f5a9fe1c1ac4e4`
- Actions run: `36324701904`
- workflow: `RunPod Control V1`
- conclusion: **SUCCESS**
- status job: SUCCESS
- execute_27b command step: SUCCESS with `AQLEVON_27B_COMMAND_NOT_REQUESTED`
- artifact/finalizer paid-path steps: SKIPPED
- latest provider status: `pod_count=0`

No paid resource is active.

## Frozen execution contract

Scientific contract SHA256:
`484c369ee9e4d19d1142f4d55cce4296a594d49697d5cf47afa13f31da0a283d`

Agent 03 release commit:
`4ddb508ea0dc99ab7e02588e19915915fc67976c`

Base:
`Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`

The next run must keep the frozen historical training recipe and additionally preserve the preregistered same-seed paired public evaluation contract.

## Control protections now live on operational branch

- fixed workflow single-flight concurrency;
- durable reservation/consumption claim before provider create;
- stale concurrent start loses Git CAS before provider create;
- exact scientific-contract hash required before provider create;
- Fresh Authorization V2 only; legacy authorizations rejected;
- runtime package-version receipt mandatory;
- evidence archive verification mandatory;
- adapter SHA bound to manifest + training receipt;
- actions/upload-artifact must succeed before provider deletion;
- upload/digest/runtime receipt failure stops but does not delete pod;
- no main merge;
- sealed/private W05 forbidden in the training run.

## Public/generalization evaluation readiness

Agent 03 paired public contract: READY.
Agent 04 frozen structural-generalization harness: READY.
Agent 02 future W05 evaluator hard binding: READY for future newly preregistered private material only.

Historical W05 remains unavailable and is not used by this run.

## Budget evidence

Historical R0:
- billed seconds estimate: 1283
- rate: $1.59/hour
- compute estimate: $0.566658

New controller hard ceilings:
- max_total_cost_usd <= **1.50**
- max_hourly_rate_usd <= **1.60**
- max_billed_seconds <= **3200**

Recommended owner authorization cap for the next single run:
**USD 1.50 maximum total cost**.

This is a ceiling, not an expected spend.

## Required owner decision

A fresh explicit single-use authorization is the only remaining paid gate.

Until that authorization is explicitly granted:
- no active authorization file is written;
- `command.json` remains `status`;
- no provider create action is permitted.

## Manager status

**GO_TO_REQUEST_FRESH_AUTH**
