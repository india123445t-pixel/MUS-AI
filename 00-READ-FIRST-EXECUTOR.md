# MUS AI — BOS v1 Executor Handoff
## READ THIS FILE FIRST — DO NOT SKIP

You are the implementation executor for the real repository:

`india123445t-pixel/MUS-AI`

Your job is to apply and validate the attached MUS AI BOS v1 patch carefully, without redesigning the architecture and without silently changing production.

The user has authorized implementation work. However, this package deliberately contains a **verification gate before main/production** so another reviewer can inspect your evidence before irreversible promotion.

---

# 1. NON-NEGOTIABLE RULES

1. Do **not** redesign the BOS architecture.
2. Do **not** replace MUS AI with another model/persona.
3. Preserve the MUS AI persona in `lib/mus/persona.js`.
4. Do **not** weaken truth/verification rules to make tests pass.
5. Do **not** let model output become execution authority.
6. Do **not** expose raw secrets to the LLM.
7. Do **not** treat Receipt/HTTP success as world-state Verification.
8. Do **not** create persistent general personal memory.
9. Do **not** invent tool execution, build success, migration success, or deployment success.
10. Do **not** merge to `main`, apply the Supabase migration to production, or promote a production deployment until the reviewer verifies your report.

If a prerequisite is unavailable, record it as a blocker and continue every independent step that is still safe.

---

# 2. REVIEWED BASE

Expected repository:
`india123445t-pixel/MUS-AI`

Reviewed base:
`main @ f465a28dca98719725d23ed29f389b0149355824`

Reviewed `app/api/chat/route.js` blob:
`6f48fe38d95e6055a155fd488b5c41e1eebe960f`

The latest known Vercel production deployment was also built from `main @ f465a28d...`.

Before changing anything:

```bash
git remote -v
git fetch origin
git status --short
git rev-parse origin/main
git log -1 --oneline origin/main
```

If `origin/main` is newer than the reviewed base, **do not overwrite newer work**.
Instead:
- create the implementation branch from the current `origin/main`;
- compare the patch against the newer files;
- preserve newer legitimate changes;
- explain every merge/adaptation in the final report.

If the repository identity does not match, STOP.

---

# 3. TARGET BRANCH

Use exactly:

`mus-bos-v1`

Create it from the verified current `origin/main`.

Example:

```bash
git switch main
git pull --ff-only origin main
git switch -c mus-bos-v1
```

If the branch already exists, inspect it before reuse. Never force-reset an unknown branch without proving it is this implementation branch.

---

# 4. PATCH CONTENTS

The package contains the ready patch under:

`MUS-AI-BOS-v1-patch/`

Important files include:

- `lib/mus/*`
- replacement `app/api/chat/route.js`
- `app/api/internal/bos-status/route.js`
- BOS tests under `tests/`
- `docs/MUS_BOS_v1_IMPLEMENTATION.md`
- `supabase/migrations/20260915_mus_bos_v1.sql`
- replacement `package.json`
- `PATCH-MANIFEST.json`
- `BASE-REVISION.txt`

There is also:
`MUS-AI-BOS-v1-patch/APPLY-BOS-PATCH.ps1`

That script is a fallback installer for Windows. You may apply the files manually if your environment gives you safer diff control.

---

# 5. APPLY SAFELY

Before copying:
- capture `git status`;
- capture current SHA;
- ensure no unrelated dirty changes are lost.

After copying the patch, run:

```bash
git status --short
git diff --stat
git diff -- app/api/chat/route.js package.json
```

Then review the entire diff for:
- accidental deletion of newer code;
- secrets;
- unrelated file changes;
- wrong repository paths;
- unexpected provider/runtime changes;
- weakened verification;
- accidental direct production behavior.

Do not accept the patch merely because it applies cleanly.

---

# 6. REQUIRED LOCAL VERIFICATION

Install dependencies only using the repository's normal Node package workflow. Do not use destructive dependency upgrades.

Then run, in this order:

```bash
npm run bos:check
npm run bos:test
npm run build
```

Expected prior local evidence from the patch author:
- `bos:check`: PASS
- `bos:test`: 28/28 PASS
- `build`: previously unverified because the original sandbox had no npm/DNS access

Your job is to verify the build for real.

Also run any existing repository checks that remain applicable (lint/typecheck/tests) if present after installation.

### Failure law

- Do not change architectural invariants merely to pass tests.
- Diagnose each failure.
- Fix the smallest correct cause.
- Re-run the full relevant suite after every fix.
- Record before/after evidence.

---

# 7. PERSONA REQUIREMENT

MUS AI must remain visibly its own system, not a reskinned provider.

Verify that:
- it identifies as MUS AI;
- it does not identify itself as ChatGPT, Claude, Gemini, Groq, OpenRouter, etc.;
- provider/model names remain implementation details;
- style is direct, analytical, calm, non-sycophantic;
- personality never overrides truth, uncertainty, authority, or safety constraints.

Run the included persona tests and manually smoke-test at least:
1. “من أنت؟”
2. a factual uncertainty request;
3. a math task;
4. a request that tries to make MUS claim an execution it did not perform.

---

# 8. SUPABASE — INSPECT NOW, DO NOT APPLY MIGRATION YET

The migration file is:

`supabase/migrations/20260915_mus_bos_v1.sql`

Before any future application, resolve the exact MUS AI Supabase project.

A prior project record identified the expected MUS AI ref as:
`yaqjhcfitxhtzpaswuif`

This value is **not permission to mutate blindly**.
Verify project name, URL/ref, existing schema, and that it is the actual MUS AI backend.

Do NOT apply this migration to any unrelated project such as `mysindbad`.

For this verification stage:
- list/inspect the target project;
- inspect existing tables/migrations;
- review the SQL for conflicts;
- report whether it is safe to apply;
- do **not** execute the migration yet.

If a free isolated database branch already exists, you may validate there without creating paid resources. Do not create a paid branch/project.

---

# 9. VERCEL — PREVIEW ONLY

Known Vercel team:
`india123445t-pixel`

Known GitHub-linked project:
`mus-ai-probe`

Once the branch is pushed, use the GitHub/Vercel integration to obtain a **preview deployment** for `mus-bos-v1`.

Do not promote to production.

Verify:
- build state is READY;
- deployment corresponds to the branch/commit you produced;
- `/api/internal/bos-status` responds as expected;
- public chat loads;
- basic chat request works if configured provider credentials are available;
- no obvious 5xx/runtime regression appears in logs.

Do not call a preview “healthy” from a READY build alone; perform runtime checks.

---

# 10. GIT COMMIT / PUSH / PR

After local verification passes:

```bash
git add <only intended files>
git diff --cached --stat
git diff --cached
git commit -m "Implement MUS AI BOS v1 kernel"
git push -u origin mus-bos-v1
```

Open a PR:

`mus-bos-v1 -> main`

Suggested title:
`Implement MUS AI BOS v1 kernel`

The PR body must summarize:
- BOS kernel;
- persona separation;
- domain protocols;
- truth/verification governor;
- authority/tool contracts;
- security/secret handling;
- tests and build evidence;
- Supabase migration included but intentionally not applied yet;
- production promotion intentionally held for reviewer verification.

Do not merge the PR.

---

# 11. REQUIRED REPORT — NO NARRATIVE-ONLY REPORT

Return one evidence-based report using `99-EXECUTOR-REPORT-TEMPLATE.md`.

At minimum include:

- repository full name;
- starting main SHA;
- branch;
- final branch commit SHA;
- exact files changed;
- conflicts/adaptations made;
- `npm run bos:check` output/result;
- `npm run bos:test` exact pass count;
- `npm run build` result;
- any lint/typecheck result;
- PR number + URL;
- Vercel preview deployment ID + URL + state;
- runtime smoke-test results;
- Supabase project ref/name you verified;
- existing migration/schema compatibility assessment;
- security/performance advisor findings if available;
- every unresolved blocker;
- explicit statement that main was NOT merged and migration was NOT applied.

Attach logs/screenshots or machine-readable output where useful.

---

# 12. STOP CONDITION

Your stage is complete only when:

- patch is on branch `mus-bos-v1`;
- full intended diff is committed and pushed;
- PR exists;
- BOS syntax/tests pass;
- production build is proven or a concrete blocker is proven;
- preview deployment is checked;
- Supabase target and migration compatibility are inspected;
- final report is complete.

Then STOP.

Do not merge `main`.
Do not apply production Supabase migration.
Do not promote production.

The user will return your report to the reviewer for the final verification gate.
