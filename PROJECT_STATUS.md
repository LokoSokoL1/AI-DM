# Dungeon Manager Project Status

## Checkpoint

- Branch: develop
- Checkpoint scope: the completed seven-milestone First Playable Vertical Slice, plus the formally accepted Phase 2 low-fidelity interface design baseline and canonical documentation
- Completed slice milestone: **Milestone 7 — End-to-End First Playable Validation**
- Accepted Phase 2 design source: SHA-256 `21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3` on 2026-07-29
- Accepted Phase 2 decisions on 2026-07-29: **D6 — Core/client API/adapter/permission/save/sync boundaries** and **D10 — Implementation sequencing**
- Approved next milestone: **M1 — Client-Neutral Authority and Operation Contracts — unstarted**
- Next action: the bounded M1 implementation task, after this documentation checkpoint is committed and the checkout is clean

The headless engine-level first playable is complete. The Phase 2 interface
design baseline is accepted, but the described UI and Foundry integration remain
unimplemented. M1 code and tests have not been produced. Voice also remains
outside this checkpoint.

## Accepted Phase 2 design baseline

[LOW_FIDELITY_INTERFACE_SPEC_V1.md](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md)
is the formally accepted Phase 2 low-fidelity interface design baseline. The
project owner accepted the exact draft on 2026-07-29 with SHA-256
`21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3`.
Acceptance approves its product behavior and 42 acceptance criteria, not
implementation. D6 and D10 were accepted on 2026-07-29; the remaining eight
deferred implementation decisions remain open. Future technical design and
implementation must conform to the baseline and accepted decisions or record an
explicit revision.

## Accepted Phase 2 decision state

- D6 accepts the ports-and-adapters ownership direction for the deterministic
  core, client-neutral application boundary, dedicated edge adapters,
  permission-filtered views, saves, and synchronization boundaries without
  implementing those future systems here.
- D10 accepts a contract-first bounded implementation sequence. Later milestone
  ordering is not permanently frozen and may change only through an explicit
  accepted decision.
- M1 is approved but unstarted. Its binding scope is only the minimum
  client-neutral authority and operation contracts needed to represent the
  existing controlled fixture and support the next bounded milestones.
- M1 must not prematurely finalize detailed contracts or behavior belonging to
  later permission, transport, Foundry, multiplayer, save, branch, snapshot, or
  reconciliation milestones.
- M2 — Identity, Permission, Assignment and Visibility Core — is only the
  provisional following milestone.

This documentation checkpoint implements no Phase 2 capability. No M1 source
code or tests exist yet.

## Implemented behavior

### Local application foundation

- Local configuration and logging.
- Character, item, and campaign models backed by JSON storage and managers.
- Character create/load tools with immutable ToolSpec metadata and registry validation.
- Provider interface, Ollama adapter, AI manager, typed tool-call parser, central tool registry, one-shot executor, and bounded ToolAgent observation/response loop.
- Opt-in loopback-only live Ollama validator, separate from deterministic verification.

### Deterministic engine and durable state

- Immutable commands, provenance, results, game events, and audit records.
- Exact synchronous command dispatch with controlled failures and no retry.
- Per-capability automation policy, optional human approval, fail-closed gate resolution, and a policy-gated dispatcher with process-local replay protection.
- Audited command coordination, atomic event batches, append-only in-memory event and audit journals, world-state projection, synchronization health, and explicit recovery/rebuild.
- Identity-checked SQLite EventJournalStore with durable-before-memory publication and all-or-nothing startup hydration into fresh in-memory journal and projection objects.

### First Playable Vertical Slice Milestones 1–7

- Explicit V1 fixture identities for campaign vertical-slice-v1, journal vertical-slice-v1-events, scene controlled-goblin-encounter, Nekria, and goblin-1.
- All-or-nothing fixture loading; Nekria is the only selectable player character. Selection creates one durable event and is restart safe.
- Manual and automatic dice modes share one calculation path and record distinct provenance. Automatic randomness is injected; deterministic sequence sources support tests.
- Static controlled combat data for initiative modifiers, armor class, hit points, and Nekria's rapier.
- One complete combat.resolve_controlled_round command resolves Nekria initiative (1d20+3), goblin initiative (1d20+2), rapier attack (1d20+5), and conditional damage (1d8+3) in fixed order.
- Initiative ordering uses total, then modifier, then stable participant ID. Both Nekria-first and goblin-first paths are supported; goblin-first records the controlled no-action advancement.
- Miss, nonlethal hit, and lethal hit outcomes preserve the correct round number and active participant. Defeating the goblin completes the encounter with no active participant.
- A successful complete sequence creates one aggregate combat.controlled_round_resolved event. Durable append, local publication, and projection expose no partial round.
- Manual input requirements and every controlled failure are eventless and preserve prior initiative, turn, hit-point, and completion state.
- Restart hydration validates and reconstructs the exact recorded round without rerolling, requesting input, inferring facts, or appending another event.
- Verified narration packets are constructed only from one exact controlled-round journal entry and its synchronized projection. They retain source event identity and sequence plus the minimum recorded combat facts needed for narration.
- A dedicated narration-only provider receives only the immutable packet. ToolAgent, tool schemas, parsers, registries, executors, commands, runtime objects, and storage handles are excluded from that interface.
- Provider output is transient presentation text. One eligible event is attempted at most once per narration boundary with no retry or fallback; provider failure leaves the durable event, local journal, projection, dice history, and combat result unchanged.
- A completed controlled round has been restart-proven by discarding the original runtime graph and loading two independent fresh runtimes from the existing JSON fixture files and SQLite journal only.
- Each fresh hydration reproduces event identity, sequence, ordering, payload, selected character, initiative, controlled goblin advancement, attack, damage, hit points, defeat, final turn, completion state, and synchronized tails without dice, dispatch, append, narration, tools, replay, inference, or repair.
- Fixture files plus the SQLite database and WAL when present are compared after the original SQLite operation is complete. The `-shm` sidecar is process-local SQLite coordination state and is not claimed as durable campaign content.
- Two end-to-end acceptance journeys exercise the public fixture, runtime,
  selection, controlled-round, SQLite publication, projection, verified
  narration, shutdown, and fresh-hydration boundaries. Manual input remains
  eventless until complete; automatic dice consume only their required faces.

## Verified milestone coverage

All seven milestones of the accepted vertical slice are implemented and verified. The tests cover exact fixture identity and validation, selection durability, manual and automatic dice, immutable combat data, both initiative orders, tie-breaking, staged input requests, hit/miss/lethal outcomes, aggregate event publication, projection, failure atomicity, idempotency, restart reconstruction, narration eligibility, exact source binding, provider isolation, narration failure containment, disposal of the original runtime graph, repeated durable-only hydration, and end-to-end public-composition acceptance journeys.

## Verification

- Focused Milestone 7 end-to-end first-playable acceptance: **2 passed**.
- Directly affected runtime, controlled-round, journal, projection, hydration, narration, pipeline, and dependency suite: **188 passed**.
- Complete engine suite: **537 passed**.
- Complete deterministic pytest suite: **609 passed**, with dungeon_manager/ai/test_live_tool_loop_validation.py explicitly excluded.
- Five isolated legacy smoke modules: **passed** for models, storage, managers, tools, and registry.
- Normal data/ and logs/ manifest: **unchanged** by path, type, size, UTC modification timestamp, and SHA-256.
- Live validator, Ollama, and all external AI providers: **not invoked**.

The two deterministic guard tests stored in dungeon_manager/ai/test_live_tool_loop_validation.py are excluded together with that file so the checkpoint command is visibly incapable of entering the live validator path.

## Known limitations

- Narration is implemented only for the single verified controlled-round event. It does not provide semantic proof of unrestricted provider prose, general event narration, persistence, streaming, retry, fallback, or automatic replay after restart.
- ToolAgent and tools are not part of the narration path and remain disconnected from controlled combat.
- Process-local audit history, replay guards, provider history, narration text, and Python object identity do not survive restart; no new persistence mechanism was added for them.
- All seven frozen slice milestones are complete; M1 is approved as the next
  bounded Phase 2 milestone but remains unstarted.
- The slice is one fixed campaign, one selectable player character, one hostile goblin, one permitted rapier attack, and one aggregate controlled-round event.
- Goblin tactical behavior is deliberately absent; the goblin-first path records only the accepted no-action advancement.
- Foundry VTT integration, UI, voice, general D&D rules, movement, spells, campaign discovery, editors, and broader content systems are not implemented.
- Event history is durable. Command-audit history, replay protection, and world-state snapshots remain process-local.
- Recovery, migration, repair, retries, polling, background workers, and cross-process coordination are not general product features.
- Ollama behavior has prior opt-in validation but remains nondeterministic and outside this checkpoint's pass/fail evidence.

## Next action

No unstarted milestone remains in the frozen seven-milestone slice. After this
documentation checkpoint is committed and the checkout is clean, the next
bounded task is M1 — Client-Neutral Authority and Operation Contracts. M1
remains unstarted, and its minimum-contract constraint remains binding.
