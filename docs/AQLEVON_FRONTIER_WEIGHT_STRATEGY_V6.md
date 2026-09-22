# AQLEVON Frontier Weight Strategy V6 — Verified Capability Genome Program

**Status:** ACTIVE / OWNER-DIRECTED FRONTIER RESEARCH
**Date:** 2026-09-18
**Purpose:** Define the strongest currently defensible path to produce genuinely new AQLEVON weights from a sovereign open-weight base without incompatible tensor splicing or unverifiable performance claims.

## 1. V6 decision

AQLEVON will be developed as a **verified capability genome system**, not as one monolithic fine-tune.

A capability gene is a same-base trainable artifact (adapter/delta/checkpoint branch) with:
- exact base revision;
- training recipe and code revision;
- dataset/provenance manifest;
- verifier definition;
- public/private eval vector;
- interference fingerprint against other genes;
- mergeability score;
- cost/latency impact;
- quantization survival result.

Only genes that are Pareto-positive on the frozen harness can teach, merge, or enter consolidation.

The target integration pipeline is:

`frozen base -> defect atlas -> specialist genes -> merge-aware specialist training -> verifier-grounded RL -> self-evolving curriculum -> prompt-level verified teacher selection -> on-policy integration -> merge tournament -> consolidation -> quantization -> frozen external evaluation`

## 2. Key V6 upgrade: teacher selection is per-prompt, not merely per-domain

Routed MOPD remains valuable, but V6 changes the default decision rule.

A teacher is not trusted because it belongs to the matching domain. For each training prompt:
1. generate a small probe/answer from eligible teachers;
2. run the strongest available objective verifier;
3. only teachers that pass become eligible to supervise that sample;
4. if no teacher passes, fall back to verifier-grounded RL/self-learning rather than distilling a possibly wrong answer;
5. retain teacher disagreement as training/evaluation metadata.

V6 therefore prioritizes:
- TGOPD-style prompt-level gating;
- answer-verified multi-teacher selection / MT-SDPO-style eligibility;
- routed MOPD only after per-sample reliability has been checked where objective verification is possible.

Core principle:
**verified correctness outranks teacher reputation, benchmark rank, or domain label.**

## 3. Merge-aware gene training

V5 treated merging primarily as a downstream tournament. V6 adds **mergeability as a training objective**.

For any specialist expected to enter a weight merge:
- baseline optimizer branch: ordinary specialist training;
- challenger: merge-aware optimizer / robust weight-space training inspired by MergOPT;
- periodically simulate candidate merge offsets during training;
- measure loss/behavior under likely merge perturbations;
- retain the branch only if specialist gain survives simulated integration.

This reduces the common failure pattern:
`excellent expert -> destructive merge -> weak generalist`.

## 4. Self-evolving curriculum engine

Static datasets are not enough for frontier competition. AQLEVON will maintain a curriculum engine with four roles:
- **Challenger/Proposer:** creates new tasks near or above current capability frontier;
- **Planner:** decomposes long-horizon tasks when applicable;
- **Solver:** current AQLEVON checkpoint or specialist gene;
- **Verifier/Critic:** external deterministic or constrained verifier that decides correctness and curriculum usefulness.

Primary research inspirations:
- Absolute Zero Reasoner: self-propose + self-solve with executable verification;
- SAGE: challenger/planner/solver/critic co-evolution;
- SPELL: long-context questioner/responder/verifier self-play with automated difficulty curriculum;
- RLSVR: transform open-ended tasks into self-verifiable proxy environments;
- learnable-information-gain principle: generated data is retained only if it adds learnable signal rather than recycling already-mastered behavior.

### Curriculum promotion law
A generated task enters training only when all apply:
- provenance and generator revision recorded;
- not overlapping protected eval sets;
- verifier is objective or explicitly bounded;
- task difficulty is within the learnable frontier (not trivial, not impossible noise);
- solving it would exercise a measured AQLEVON weakness;
- retained examples improve a held-out probe set in ablation.

## 5. Open-ended capability through self-verifiable transformations

AQLEVON should not restrict RLVR to code/math.

V6 adds an RLSVR lane:
- transform open-ended tasks into environments with hidden/verifiable state;
- use reconstruction, consistency, retrieval, constrained planning, pairwise information asymmetry, or executable simulation as reward sources;
- only map proxy-task gains back to open-ended capability after independent evaluation.

Candidate domains:
- summarization factuality;
- research evidence selection;
- planning consistency;
- instruction following;
- tool orchestration;
- long-form writing constraints;
- Arabic/Darija register control.

## 6. Long-context self-evolution

Long context becomes a dedicated gene, not a side effect.

R0-J / long-context lane:
- raw documents -> generated questions/claims -> answer/reference creation -> verifier -> curriculum length growth;
- automatic document-length curriculum;
- answer localization and citation checks;
- distractor injection;
- multi-document contradiction tasks;
- context compression and retrieval ablations;
- measure useful-context utilization, not advertised context window.

SPELL-style multi-role self-play is a principal candidate, but must be compared against simpler supervised/continued-pretraining baselines at matched compute.

## 7. Capability Genome Bank schema

Every gene has a machine-readable record:

- `gene_id`
- `base_model`
- `base_revision`
- `domain`
- `method`
- `training_code_sha`
- `dataset_manifest_sha`
- `license_status`
- `teacher_sources`
- `objective_verifier`
- `public_eval_vector`
- `private_eval_vector`
- `regression_vector`
- `interference_fingerprint`
- `mergeability_score`
- `tokens_per_verified_success`
- `gpu_seconds_per_verified_success`
- `peak_vram`
- `quantization_survival`
- `promotion_state`
- `artifact_sha256`

No artifact without this record is an AQLEVON gene.

## 8. Interference Atlas

Before combining genes, evaluate every pair/triple on a fixed micro-harness.

Store:
- target gain retained after merge;
- non-target regression;
- cosine/task-vector relationship;
- layer-wise conflict concentration;
- output-style conflict;
- tool/template conflict;
- Arabic/English cross-lingual interference;
- reasoning-length inflation;
- quantization sensitivity.

Use the atlas to choose:
- direct merge;
- MOPD/TGOPD integration;
- sequential training with replay;
- separate expert in future MoE;
- rejection.

## 9. Integration tournament V6

Once >=3 promotion-eligible genes exist, compare at matched evaluation budget:

1. mixed SFT baseline;
2. sequential specialist training + replay;
3. Task Arithmetic/interpolation;
4. TIES;
5. DARE-TIES;
6. DELLA;
7. Iso-C / Iso-CTS;
8. Expert Merging / layer-wise calibration;
9. MergOPT-trained genes + merge tournament;
10. Routed MOPD;
11. prompt-level gated OPD (TGOPD-style);
12. answer-verified multi-teacher integration (MT-SDPO-style);
13. gated OPD + replay;
14. MoT branch cycles for long reasoning where appropriate.

Winner is not the highest mean benchmark score. Winner must be Pareto-best on:
- verified task success;
- weakest-domain floor;
- hallucination/calibration;
- regression vector;
- inference cost;
- latency;
- quantization survival.

## 10. Architecture escalation track

R0 stays practical and same-base around the canonical Qwen3.8-27B research line.

R1 evaluates whether proven genes should be transferred into a higher-capacity architecture rather than endlessly forcing all capability into one dense 27B.

Candidates:
- dense-to-MoE sparse upcycling;
- specialist expert banks with learned router;
- merge-aware expert construction;
- diverse intermediate-checkpoint experts;
- router pretraining on verified domain/task labels;
- Nash-style or behavior-aware expert merging only if it wins matched-compute ablations.

R1 is allowed to increase total parameters only when activated compute / verified-success improves enough to justify serving complexity.

## 11. Teacher portfolio law

Teacher hierarchy is dynamic and evidence-based.

### Allowed teacher classes
- local/open-weight model whose license permits the intended training use;
- AQLEVON's own older checkpoints;
- specialist AQLEVON genes;
- public datasets with compatible provenance and license;
- executable/verifier-generated synthetic trajectories.

### Closed hosted models
Closed APIs are benchmark references only unless their current terms explicitly permit using outputs to train a competing model. No hidden or indirect laundering of prohibited hosted outputs into training data.

### Current high-value open-weight references (re-check license before every training run)
- Qwen3.8 frontier family — architecture/teacher/reference line; large Max/A95B line uses its own license;
- GLM-5.3 — open weights under GLM-5.3 license; strong long-context/frontier reference;
- Kimi-K3 — open weights under Kimi-K3 custom license; commercial/MaaS thresholds require monitoring;
- other current open-weight frontier teachers may enter only after exact license + revision + architecture + hardware review.

No external teacher becomes a tensor donor unless it is architecture-compatible and the license permits it.

## 12. Frontier benchmark strategy

AQLEVON must beat strong models by measured capability, not by branding.

The frozen evaluation portfolio must contain:
- repository coding / SWE-style tasks;
- long-horizon terminal/agent tasks;
- tool/function calling;
- research/citation entailment;
- factuality/calibration;
- math/science reasoning;
- long-context retrieval + reasoning;
- Arabic MSA;
- Moroccan Darija + Arabizi + French code-switch;
- minimal-diff/repository safety;
- recovery after tool/test failure;
- private unseen tasks;
- adversarial instruction/authority tasks.

External leaderboards are used only for target selection and context; AQLEVON promotion uses reproducible local/private harnesses.

## 13. V6 immediate execution sequence

### V6-G0 — freeze Genome Bank + Interference Atlas schemas
Create machine-readable registries now.

### V6-G1 — first physical parameter delta
Run the existing one-step R0-A probe on compatible GPU, save adapter/checkpoint, prove non-zero delta, reload, hash, eval.

### V6-G2 — R0-A coding gene
Train coding/repo gene with executable tests and failure recovery.

### V6-G3 — merge-aware twin
Train a second R0-A branch with merge-aware regularization/optimizer and compare merge robustness.

### V6-G4 — R0-B tool gene + R0-D Arabic/Darija gene
Build independently with strict domain evals.

### V6-G5 — self-evolving curriculum pilot
Run reduced-scale Absolute-Zero/SAGE-style proposer-solver-verifier curriculum on a smaller compatible model first; measure whether generated tasks increase learnable information before using expensive 27B compute.

### V6-G6 — verified teacher integration tournament
With >=3 strong genes, compare MOPD, TGOPD-style gating, answer-verified multi-teacher selection, and parameter merges.

### V6-G7 — consolidated AQLEVON checkpoint
Only consolidate if a candidate improves the broad frozen vector and survives reload + quantization.

### V6-G8 — R1 architecture escalation
Only after R0 proves repeatable gain, test dense-to-MoE / larger-base transfer.

## 14. Novel AQLEVON hypothesis

The project will test a combination not represented by any single published recipe:

**Defect Atlas
+ merge-aware specialist genes
+ verifier-grounded RLVR/VPR
+ self-evolving learnable-information curriculum
+ per-prompt verified teacher gating
+ on-policy multi-teacher integration
+ interference-aware merge tournament
+ optional sparse expert upcycling
+ private regression gates
+ cost-per-verified-success optimization.**

This is a research hypothesis, not a performance claim.

## 15. Hard truth boundary

AQLEVON is not called stronger than ChatGPT, Claude, Kimi, GLM, DeepSeek, Qwen Max, or any frontier system until:
- new AQLEVON parameters exist;
- exact artifact hashes exist;
- evaluation sets were frozen before testing;
- contamination checks pass;
- broad independent/private comparisons show superiority or a defined Pareto advantage;
- reliability and serving cost remain acceptable.

The program is designed to maximize the probability of frontier performance while keeping every improvement attributable, reproducible, legal, and measurable.