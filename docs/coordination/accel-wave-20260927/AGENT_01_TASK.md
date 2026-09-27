# AGENT 01 — 27B ARTIFACT RECOVERY & PERSISTENCE

FREE-ONLY. Lane: artifact recovery/durability only.

Mission:
1. Search all durable sources for the real adapter from run 36307917194.
2. Verify any recovered bytes against SHA256 c91f007acd1004ba5a2b2dae6014d13664ce9ccef665802e60aa975e47d32b0e.
3. Verdict: RECOVERED_AND_VERIFIED / RECOVERABLE_PATH_FOUND / IRRECOVERABLE_AFTER_POD_DELETE.
4. If not recovered, patch a dedicated branch so future runs package adapter+manifest+receipt, verify SHA, upload artifact BEFORE pod deletion, and fail closed if export fails.
5. Do not trigger paid compute.

Write timestamped reports under docs/coordination/accel-wave-20260927/Agent_01_Output/.
