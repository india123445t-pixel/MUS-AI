# Agent 01 Checkpoint — 27B Artifact Recovery Audit

Timestamp: 2026-09-27T11:51:24Z
Role: AQLEVON Agent 01
Lane: 27B artifact recovery and persistence
State: ACTIVE / FREE-ONLY

## Verified target
- GitHub Actions run: 36307917194
- Model result: AQLEVON-27B-R0 public PASS
- Expected adapter SHA256: c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e
- Expected adapter-state SHA256: e5a9b8260e7cfc08f3f9c5b072b617bdafc5ed06a645b15c10ee7937d5465bde
- Evidence archive SHA256 reported by controller: eca1b1023f000fc49e9c5c3579aa330bb73121cd54a00b16327d068e74de1bb6

## Durable-source checks completed
1. GitHub Actions run 36307917194 concluded success.
2. GitHub Actions artifacts endpoint for the run returns total_count=0.
3. Execute job log proves the controller downloaded /evidence.tgz from the pod to /tmp/aq27-evidence.tgz.
4. The controller then stopped and deleted the pod before any durable upload step.
5. The controller parsed candidate/candidate_manifest.json and candidate/training_receipt.json out of the temporary archive and committed only the JSON result receipt.
6. The bootstrap package_evidence function includes the entire candidate directory in evidence.tgz, so the actual adapter bytes were inside the temporary archive on the ephemeral GitHub runner.
7. GitHub Releases currently contain only Auth16 4B runtime assets; no AQLEVON-27B-R0 release asset exists.
8. Library scan under /AQLEVON found no recent binary archive or adapter matching the 27B run.
9. Exact hash searches in repository default-branch index and Library did not locate the adapter bytes.
10. Current coordination branch contained no Agent_02/03/04 output folders yet when checked.

## Root durability defect
The run controller downloads the evidence archive to the ephemeral GitHub Actions runner, computes/records its SHA, then deletes the RunPod pod. It never uploads the archive to Actions artifacts, a Release, Git, or Library before pod deletion.

The durable record therefore proves the expected adapter hash and successful save/reload result, but does not itself preserve the adapter bytes.

## Current verdict
Provisional: IRRECOVERABLE_AFTER_POD_DELETE unless a still-unchecked durable copy is found.

## Mutations
None to scientific/training code.
None to main.
No paid compute.
No GPU.
No W05 sealed/private material accessed.

## Next safe action
- Finish remaining durable-source checks.
- If no byte-identical copy is found, create a dedicated Agent 01 branch from current ops/runpod-control-v1 HEAD.
- Patch only artifact persistence/control-plane behavior: verify the downloaded archive and internal adapter SHA, persist it before pod deletion, verify the persistent upload, and fail closed on export failure.
