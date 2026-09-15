# MUS AI BOS v1 Patch

This patch upgrades the current MUS AI chat runtime from a prompt/router-centric design toward the frozen Behavioral Operating System architecture.

## Files to add

- `APPLY-BOS-PATCH.ps1` — Windows fallback installer if the GitHub connector is not writable
- `BASE-REVISION.txt` — reviewed repository base identity

- `lib/mus/constants.js`
- `lib/mus/security.js`
- `lib/mus/persona.js`
- `lib/mus/domain-protocols.js`
- `lib/mus/providers.js`
- `lib/mus/kernel.js`
- `lib/mus/tool-registry.js`
- `lib/mus/authority.js`
- `lib/mus/state-machines.js`
- `lib/mus/context.js`
- `lib/mus/receipts.js`
- `lib/mus/response-governor.js`
- `app/api/internal/bos-status/route.js`
- `tests/mus-kernel.test.mjs`
- `tests/security-regression.test.mjs`
- `tests/authority-contract.test.mjs`
- `tests/response-governor.test.mjs`
- `tests/persona-contract.test.mjs`
- `docs/MUS_BOS_v1_IMPLEMENTATION.md`
- `supabase/migrations/20260915_mus_bos_v1.sql`

## Files to replace

- `app/api/chat/route.js`
- `package.json`

## Safety properties

- distinct MUS AI persona independent of provider;
- no model-generated execution authority;
- no formal VERIFIED from second-model agreement;
- current/source claims fail to INCONCLUSIVE when evidence is unavailable;
- secret-like tokens are redacted before external model providers;
- domain protocol composition without per-domain agents;
- no general personal memory;
- ToolSpec/CapabilitySpec remain registry contracts; Permit remains execution authority.


## Verified locally

- `npm run bos:check`: PASS
- `npm run bos:test`: **28/28 PASS**
- `npm run build`: NOT RUN in this sandbox because npm registry/DNS is unavailable and dependencies are not cached. Do not interpret this as a successful production build.

## External blockers

- GitHub connector can read `india123445t-pixel/MUS-AI` but currently reports `push: false`; the patch has not been pushed to the repository.
- Supabase connector currently exposes only `qkoscgdegnqcypkjrefn` (`mysindbad's Projec`), not the MUS AI project, so the BOS migration has not been applied to an unrelated database.
