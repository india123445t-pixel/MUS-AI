# AQLEVON 27B — Authorization 08 SUCCESS / Artifact Preserved

Timestamp: 2026-09-27
Manager state: **TARGET_RUN_SUCCEEDED / PAID_RETRIES_STOPPED**

## Successful run

Authorization:
`P4-AQLEVON-27B-R0-FRESH-20260927-1606-08`

GitHub Actions:
- run: `36332132785`
- execute job: `108656002803`
- conclusion: **SUCCESS**
- source SHA: `e07d41dd140c7a56b3a27a45fb8ca04b5e03ac74`

Provider:
- pod id: `y06z4plp60plbc`
- rate: USD 1.59/hour
- location selected by controller: `EU-RO-1`
- final stage: **DONE**
- billed seconds estimate: `2122`
- compute estimate: **USD 0.937217**

## Scientific result

Candidate:
- model: `AQLEVON-27B-R0`
- base: `Qwen/Qwen3.8-27B@1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`
- trainable parameters: `1,507,328`
- optimizer updates: `672`
- elapsed training seconds: `1224.143`
- loss first: `0.3523574471473694`
- loss last: `0.021733809262514114`
- reload hash match: true
- public dev: `2/28 -> 25/28`
- public shadow: `1/28 -> 23/28`
- sealed/private W05 consumed: false
- public status: `AQLEVON_27B_R0_PUBLIC_PASS`

Adapter identities:
- adapter SHA256: `5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74`
- adapter-state SHA256: `1e3ff8a0fbc88686a2d96f93d4f04fdd66db2034ffdfafc2cc91e532ed0bf80f`
- manifest SHA256: `e020c6b140ffba104d1fe4485333fb225afd29c52dc03bf9a62d0f8c614e01c5`
- evidence archive SHA256: `335ece52ae8aae5c41ad92cc964880fea583e4a2e834b879200d053e162a969b`
- runtime versions SHA256: `e4422e5f20b44aa6e8caeb1409f176e2ae3bcd8475dc5adeec1bbad5ae0ffa94`

Runtime:
- Python 3.12.13
- torch 2.10.0+cu129
- transformers 5.17.0
- peft 0.21.0
- accelerate 1.15.0
- safetensors 0.8.0

## Durable artifact

GitHub Actions artifact:
- artifact ID: `10936543533`
- artifact name: `aqlevon-27b-r0-preserve-36332132785`
- size: `9,411,478` bytes
- expires: `2026-10-11T16:44:21Z`
- GitHub artifact ZIP digest: `sha256:b41c4d8f0c3f89bfab76a2616378454e2f2f10b2e70a35261bb774aa5567922f`

Manager independently downloaded the artifact after the run.

Local byte verification:
- downloaded artifact ZIP SHA256 exactly matches GitHub digest:
  `b41c4d8f0c3f89bfab76a2616378454e2f2f10b2e70a35261bb774aa5567922f`
- inner evidence archive size: `9,408,629` bytes
- inner evidence SHA256:
  `335ece52ae8aae5c41ad92cc964880fea583e4a2e834b879200d053e162a969b`
- extracted adapter model size: `6,038,744` bytes
- extracted adapter SHA256:
  `5ed9a22e963eca99f5ebd00f13a46fa6afadd9b74bb9d2e501b23c1ff9219c74`

Artifact contents verified to include:
- adapter model
- adapter config
- tokenizer/chat template
- candidate manifest
- training receipt
- runtime versions
- train log
- exact trainer/W02 input copies
- hardware receipt

## Provider cleanup

Post-success read-only status at `2026-09-27T17:26:26Z` does not list the successful-run Pod `y06z4plp60plbc`.

Only the historical stopped attempt-05 Pod remains listed as `EXITED`; no active AQLEVON 27B GPU exists.

The successful run's finalizer passed:
`AQLEVON_27B_DURABLE_ARTIFACT_BEFORE_DELETE_PASS artifact_id=10936543533`

## Authorization closure

Authorization 08 is now:
- fresh_authorization: false
- training_authorized: false
- consumed: true
- final_stage: DONE
- must never be reused

`command.json` is restored to read-only `status`.

No additional paid retry is authorized or needed under the standing retry directive because the target run succeeded.

## Cumulative budget

- Auth03: USD 0.00 GPU
- Auth04: USD 0.00 GPU
- Auth05: USD 1.326767
- Auth06: USD 0.00 (provider create not attempted)
- Auth07: USD 0.00 (provider create not attempted)
- Auth08: USD 0.937217

Total actual/estimated GPU compute:
**USD 2.263984**

Owner cumulative ceiling:
**USD 4.00**

Unused ceiling:
**USD 1.736016**

## Truth boundary

This is a real parameter-changing 27B LoRA artifact with durable byte custody and strong public in-family held-out evidence.

It is **not yet a final W05/private capability-promotion claim**.

Historical W05 material remains unavailable and must not be reconstructed/substituted. Future independent/public generalization evaluation and/or future newly preregistered private evaluation remain separate gates.

**FINAL STATE: AQLEVON_27B_R0_AUTH08_SUCCESS_ARTIFACT_DURABLY_PRESERVED**
