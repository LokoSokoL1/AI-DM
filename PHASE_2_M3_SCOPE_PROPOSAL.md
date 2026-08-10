Dungeon Manager Phase 2 M3 Scope Proposal

Status: Accepted on 2026-07-30 for single-pass execution.

Proposed milestone: M3 — Durable Operation Identity and Idempotent Submission Core

Verified planning boundary

Current canonical records and the latest verified handoff place "LokoSokoL1/AI-DM" on clean, synchronized "develop" at "79437f246dd54b53d5abd19e68fd5bad5cc4e510". M1 and M2 are complete. D6 and D10 are accepted; D1–D5 and D7–D9 remain open. The local repository must be verified again before execution and remains implementation authority.

M1 exposes the controlled fixture through a client-neutral authority boundary, but caller-operation identity is not durable across restart. M2 authorizes requests before M1 while keeping its fixture authority data process-local. The engine and committed event journal remain authoritative.

Outcome

M3 adds the smallest durable boundary needed to make one authorized, state-changing controlled-fixture operation at-most-once across exact retry and process restart.

An exact retry must not reroll, redispatch, reappend, reproject, resynchronize, reinvoke tools/providers, or renarrate. Reusing an operation key for different content must fail closed. A record showing that dispatch may have begun must never be automatically redispatched. Authorization must precede inspection or disclosure of stored operation evidence.

M3 remains limited to existing M1/M2 controlled-fixture paths.

Authority direction

client-neutral caller
  -> M2 authorization
  -> M3 durable operation coordinator
  -> M1 controlled-fixture authority
  -> existing runtime, engine, and durable event journal

M3 coordinates durable submission identity and retry behavior only. It does not decide permissions, visibility, mechanics, or presentation. M1 and the engine remain operation authority; committed events remain world-fact authority.

Binding scope

Area| Required behavior
Contracts| Immutable, versioned, client-neutral contracts for campaign-scoped operation key, bounded operation kind, canonical request identity/fingerprint, lifecycle, replay disposition, terminal sanitized correlation/outcome, and fixed collision/incompatible/unavailable/recovery-required diagnostics. Unknown or malformed values fail closed.
Canonical identity| Deterministically bind resolved participant, campaign, operation kind, contract version, target actor when applicable, and the complete bounded payload. Exclude client labels and presentation text. A stored digest may be used, but different canonical requests must never be silently treated as equal.
Port and storage| One narrow client-neutral port for exact lookup, first reservation, dispatch-started transition, terminal recording, and exact conflict/ambiguity reporting. One SQLite adapter with exact store/schema identity, stable serialization, transactions, and fail-closed incompatible/malformed-state handling.
Retry behavior| New key/new request proceeds once. Same key/same request with terminal evidence returns a sanitized recorded/reconstructed result without M1. Same key/different request is a collision. Dispatch-started without terminal proof returns recovery-required. Durable event facts may support reconstruction only through the existing no-reroll correlation path.
Integration| Apply only to state-changing controlled-fixture operations beneath M2 and above M1. Preserve M1/M2 contracts, validation/policy gates, dice, durable-before-local publication, projection, synchronization, transient narration eligibility, and restart reconstruction. Side-effect-free inspection, capability discovery, and permission evaluation reserve nothing.
Restart proof| Fresh composition recognizes completed retries, persistent collisions, and persistent ambiguity without repeated authoritative or presentation work. Unauthorized callers cannot inspect or infer earlier outcomes.

A safely stranded ambiguous operation is preferable to duplicate authoritative work.

Non-goals and stop condition

M3 does not implement or decide:

- D1–D5 or D7–D9;
- transport, schemas, pairing, credentials, authentication, remote clients, multiplayer, admission, reconnect, host transfer, leases, or fencing;
- Foundry hooks/module/UI/chat/users/world discovery or D&D 5e translation;
- durable users, assignments, grants, audiences, preferences, or permission administration;
- saves, branches, snapshots, restoration, migration, repair, reconciliation, or offline-change capture;
- broader actors, actions, rules, campaigns, commands, or mechanics;
- ToolAgent integration, provider retry, narration persistence/replay, AI authority, general audit, or arbitrary legacy-operation replay; or
- changes to the accepted 42 interface criteria.

It also adds no background workers, cleanup, polling, general migration, automatic repair, distributed locking, or broader cross-process coordination.

If M3 requires an open decision or broader behavior, execution must stop and report the smallest blocker.

Required evidence

Deterministic tests must prove:

- contract validation, equality, copying, and stable serialization;
- canonical identity/fingerprint stability and difference detection;
- one reservation and one delegation for a new operation;
- zero repeated work for terminal exact retry;
- collision for same key/different request;
- fail-closed dispatch-started ambiguity;
- replay, collision, and ambiguity after fresh restart;
- authorization before ledger inspection or outcome disclosure;
- preservation of rejected, input-required, successful, failed, and eventless M1 stages;
- incompatible schema and malformed-state handling;
- M1/M2 compatibility and dependency direction; and
- no duplicate dice, command, event, projection, synchronization, provider, tool, or narration effects.

At final verification, run the complete deterministic repository suite once with the live Ollama validator excluded, then the five isolated legacy smoke entry points. "data/" and "logs/" must be unchanged; test cache and bytecode artifacts must be absent. Foundry, Ollama, browser automation, live validation, and network-dependent tests remain excluded.

Lean execution

After explicit approval, use one consolidated Codex run:

1. Verify the authoritative repository, clean "develop", exact expected HEAD, instructions, and decision state.
2. Add the exact accepted scope and final task to the repository as part of the milestone.
3. Implement M3, using focused tests during development.
4. Perform final full verification once, review the complete diff, and update canonical documentation.
5. If everything passes, create one M3 commit and push once to "origin/develop".
6. Return a handoff of roughly 12 bullets and stop.

There is no preliminary documentation commit, separate review/commit run, or duplicated full-suite run. Divergence, scope conflict, open-decision dependency, or verification failure forbids commit and push.

Approval record

The project owner accepted this bounded scope on 2026-07-30. The approval keeps D1–D5 and D7–D9 open and all non-goals and stop conditions binding. It authorizes one consolidated implementation, verification, documentation, commit, and push run only when accompanied by the final single-pass execution instruction.
