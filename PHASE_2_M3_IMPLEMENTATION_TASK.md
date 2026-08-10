Dungeon Manager Phase 2 M3 Implementation Task

Status: Accepted. Executable only with the final single-pass instruction.

The project owner accepted PHASE_2_M3_SCOPE_PROPOSAL.md on 2026-07-30. This task becomes executable when sent with the final single-pass instruction and exact expected repository checkpoint.

Goal

In the authoritative repository at "E:\Dungeon Manager" ("LokoSokoL1/AI-DM"), implement only Phase 2 M3 — Durable Operation Identity and Idempotent Submission Core as defined by the accepted scope.

Make one authorized, state-changing controlled-fixture operation at-most-once across exact retry and process restart. Preserve M2 authorization and existing M1/engine authority. Do not begin Foundry research or any later milestone.

Preflight

The final instruction must provide the exact expected HEAD. The current verified planning checkpoint is "79437f246dd54b53d5abd19e68fd5bad5cc4e510".

Before editing:

1. Verify repository identity, path, clean "develop", exact HEAD, origin, upstream, and 0 ahead / 0 behind.
2. Read all applicable "AGENTS.md" and current repository sources needed for M1, M2, the command path, persistence, restart, projection/synchronization, narration, acceptance fixtures, and dependency guards.
3. Confirm M1/M2 are complete, D6/D10 accepted, D1–D5/D7–D9 open, and the exact M3 scope explicitly approved.

The local repository is implementation authority. Do not substitute attachments, historical snapshots, Library files, earlier prompts, or chat recollections for current code or status.

Stop before editing on any material mismatch. Do not pull, fetch, switch, merge, rebase, or modify GitHub to reconcile it.

Required change

Maintain:

client-neutral caller
  -> M2 authorization
  -> M3 durable operation coordinator
  -> M1 controlled-fixture authority
  -> existing runtime, engine, and durable event journal

Implement the accepted scope with:

1. Immutable, versioned, client-neutral contracts for campaign-scoped operation keys, bounded kinds, canonical request identity/fingerprint, lifecycle, replay disposition, sanitized terminal correlation/outcome, and fixed public diagnostics.
2. One deterministic canonical identity that binds resolved participant, campaign, operation kind, contract version, applicable actor, and complete bounded payload while excluding labels and presentation text.
3. One narrow client-neutral durable-operation port for exact lookup, first reservation, dispatch-started transition, terminal recording, and exact conflict/ambiguity reporting.
4. One SQLite adapter using exact store/schema identity, stable serialization, transactions, and fail-closed malformed/incompatible-state handling.
5. One coordinator beneath M2 and above M1:
   - new key/new request reserves, marks dispatch-started, and delegates once;
   - same key/same request with terminal evidence replays a sanitized recorded/reconstructed result without M1;
   - same key/different request returns collision;
   - dispatch-started without terminal proof never redispatches;
   - durable event proof reconstructs only through the existing no-reroll path; and
   - ambiguous completion returns recovery-required without authoritative or presentation effects.
6. One bounded controlled-fixture composition. Side-effect-free inspection, discovery, and permission evaluation create no operation record.

Preserve M1/M2 compatibility, validation/policy gates, dice behavior, durable-before-local publication, projection, synchronization, transient narration eligibility, and restart reconstruction. Transient narration text must not become authoritative durable state.

Failure and scope boundaries

- M2 authorization precedes ledger access and disclosure.
- Unknown/malformed contracts, store errors, incompatible schema, malformed state, collisions, and ambiguity fail closed.
- Public diagnostics expose no exception, traceback, path, SQL, payload, credential, hidden identity/event detail, or presentation content.
- No retry rerolls, redispatches, reappends, reprojects, resynchronizes, reinvokes tools/providers, or renarrates.
- Ambiguity may strand an operation but must never duplicate authority work.

All accepted-scope non-goals are binding. In particular, do not implement or decide D1–D5/D7–D9; transport; authentication; Foundry; multiplayer; durable permissions; saves/snapshots; reconciliation; broader mechanics; ToolAgent or provider retry; narration persistence; migration/repair; background work; or later milestones.

Stop and report the smallest blocker if implementation requires anything excluded or undecided.

Tests

Add deterministic coverage for:

- contract validation, equality, copying, and serialization;
- canonical identity/fingerprint stability and difference detection;
- new reservation with one delegation;
- terminal exact retry with zero repeated effects;
- same-key/different-request collision;
- dispatch-started recovery-required behavior;
- replay, collision, and ambiguity after fresh restart;
- authorization before ledger inspection/disclosure;
- rejected, input-required, successful, failed, and eventless M1 stages;
- no duplicate dice, commands, events, projections, synchronization, provider/tool calls, or narration;
- incompatible schema and malformed durable state;
- M1/M2 compatibility; and
- dependency-direction enforcement.

Use focused tests while developing. For final verification, disable bytecode and pytest caching, then:

1. Capture "data/" and "logs/" manifests by path, type, size, UTC mtime, and SHA-256.
2. Run "git diff --check".
3. Run the complete deterministic suite once, excluding "dungeon_manager/ai/test_live_tool_loop_validation.py".
4. Run the five isolated smoke entry points: models, storage, managers, tools, and registry.
5. Confirm unchanged manifests and no ".pytest_cache", "__pycache__", or ".pyc".
6. Review the complete final diff.

Do not invoke Foundry, Ollama, live validation, browser automation, or network-dependent tests. On failure, do not stage, commit, or push; preserve the diagnostic state and report it concisely.

Records, commit, and push

As part of this same milestone:

- add the exact accepted scope;
- add this finalized task as PHASE_2_M3_IMPLEMENTATION_TASK.md;
- update "ARCHITECTURE.md", "PROJECT_PLAN.md", and "PROJECT_STATUS.md" only as required for accepted, implemented, verified M3 behavior; and
- add another M3 technical record only if genuinely required.

Keep D1–D5 and D7–D9 open and claim no excluded capability. There is no documentation-only checkpoint or later review/commit run.

If and only if implementation, documentation, final diff, and verification all succeed:

1. Stage only intended M3 files with explicit paths and confirm nothing unrelated or unstaged remains.
2. Commit once as "feat: add Phase 2 durable operation identity".
3. Push once directly to "origin/develop"; on rejection, stop without pulling, fetching, merging, rebasing, or force-pushing.
4. Verify a clean worktree and 0 ahead / 0 behind.

The final execution instruction authorizes only this one commit and push. It does not authorize a pull request, force-push, Library change, other GitHub change, or later milestone.

Concise handoff

Return roughly 12 bullets covering:

- starting/ending HEAD, branch/upstream, push, and final status;
- exact files changed;
- contracts, port, adapter, coordinator, and composition;
- retry, collision, ambiguity, restart, and authorization behavior;
- exact verification results and unchanged manifests/cache audit;
- records updated;
- unchanged M1/M2/engine authority and open decisions; and
- any blocker or evidence requiring attention.

Stop after the M3 handoff.
