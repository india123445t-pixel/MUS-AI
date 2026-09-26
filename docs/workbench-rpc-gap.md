# AQLEVON Workbench — Repository RPC Gap

As of 2026-09-26, the repository migration directory contains `20260915_aqlevon_bos_v1.sql` and does not define these production RPCs referenced by the public application:

- `get_aqlevon_runtime_config`
- `get_aqlevon_runtime_lessons`
- `public_chat_allowed`
- `log_public_exchange_v2`

Per the AQLEVON Workbench V2 production-state directive, these RPCs are defined directly in the production Supabase project and are absent from the repository migration history. This document records that repository gap only; it does not recreate, infer, or alter any SQL definition.

Recommendation: later export the exact production definitions, review them for secrets, ownership semantics, `security invoker` / `security definer` behavior, and `search_path`, then add a dedicated additive migration that reproduces the verified definitions. Do not invent signatures from call sites.
