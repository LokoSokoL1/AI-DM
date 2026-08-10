# Dungeon Manager Project Status

## Checkpoint

- Branch: develop
- Checkpoint scope: the completed seven-milestone First Playable Vertical Slice, the formally accepted Phase 2 low-fidelity interface design baseline, and completed and verified Phase 2 M1, M2, and M3
- Completed slice milestone: **Milestone 7 — End-to-End First Playable Validation**
- Accepted Phase 2 design source: SHA-256 `21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3` on 2026-07-29
- Accepted Phase 2 decisions on 2026-07-29: **D6 — Core/client API/adapter/permission/save/sync boundaries** and **D10 — Implementation sequencing**
- Completed Phase 2 milestone: **M1 — Client-Neutral Authority and Operation Contracts**
- Completed Phase 2 milestone: **M2 — Identity, Permission, Assignment and Visibility Core**
- Completed Phase 2 milestone: **M3 — Durable Operation Identity and Idempotent Submission Core**

The headless engine-level first playable is complete. The Phase 2 interface
design baseline is accepted, but the described UI and Foundry integration remain
unimplemented. M1 is implemented and verified within its minimum-contract
constraint. M2 is implemented and verified within its bounded
controlled-fixture authorization scope. M3 is implemented and verified for the
same fixture's authorized state-changing submissions only. Voice remains
outside this checkpoint.

## Accepted Phase 2 design baseline

[LOW_FIDELITY_INTERFACE_SPEC_V1.md](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md)
is the formally accepted Phase 2 low-fidelity interface design baseline. The
project owner accepted the exact draft on 2026-07-29 with SHA-256
`21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3`.
Acceptance approves its product behavior and 42 acceptance criteria, not
implementation. D6 and D10 were accepted on 2026-07-29; the remaining eight
deferred implementation decisions, D1–D5 and D7–D9, remain open. Future
technical design and implementation must conform to the baseline and accepted
decisions or record an explicit revision.

## Accepted Phase 2 decision state

- D6 accepts the ports-and-adapters ownership direction for the deterministic
  core, client-neutral application boundary, dedicated edge adapters,
  permission-filtered views, saves, and synchronization boundaries without
  implementing those future systems here.
- D10 accepts a contract-first bounded implementation sequence. Later milestone
  ordering is not permanently frozen and may change only through an explicit
  accepted decision.
- M1 is completed and verified. Its binding scope remains only the minimum
  client-neutral authority and operation contracts needed to represent the
  existing controlled fixture and support the next bounded milestones.
- M1 must not prematurely finalize detailed contracts or behavior belonging to
  later permission, transport, Foundry, multiplayer, save, branch, snapshot, or
  reconciliation milestones.
- The project owner accepted the bounded scope of M2 — Identity, Permission,
  Assignment and Visibility Core — on 2026-07-29. M2 is implemented and
  deterministically verified.
- [PHASE_2_M2_SCOPE_PROPOSAL.md](PHASE_2_M2_SCOPE_PROPOSAL.md) and
  [PHASE_2_M2_IMPLEMENTATION_TASK.md](PHASE_2_M2_IMPLEMENTATION_TASK.md) are the
  accepted scope and final next-step records.
- M2 adds a client-neutral, fail-closed authorization core around the M1
  controlled-fixture boundary while keeping session identity, participant role,
  speaker mode, controlled actor, assignment, Speak-as grant, Act-as grant,
  viewing perspective, and visibility audience distinct. Client-supplied labels
  never prove authority.
- Authentication, pairing, transport, Foundry, multiplayer, durable permission
  persistence, saves, snapshots, and reconciliation remain unimplemented and
  undecided where previously open. All M2 exclusions remain binding.
- If M2 implementation requires D1–D5 or D7–D9, it must stop rather than select
  one of those decisions.
- The project owner accepted the bounded scope of M3 — Durable Operation
  Identity and Idempotent Submission Core — on 2026-07-30. M3 is implemented
  and deterministically verified.
- [PHASE_2_M3_SCOPE_PROPOSAL.md](PHASE_2_M3_SCOPE_PROPOSAL.md) and
  [PHASE_2_M3_IMPLEMENTATION_TASK.md](PHASE_2_M3_IMPLEMENTATION_TASK.md) are the
  accepted scope and single-pass execution records.
- M3 persists campaign-scoped canonical operation identity, lifecycle, and
  sanitized terminal evidence for selection and controlled-round submissions.
  It neither persists permission state nor changes M1 or engine authority.
- Exact terminal retries bypass M1 and presentation work; collisions and
  dispatch-started ambiguity fail closed. Existing durable event facts may
  prove completion only through M1's no-reroll correlation path.

The other eight deferred implementation decisions, D1–D5 and D7–D9, remain
open. M2 and M3 did not select or finalize any of them.

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

### Phase 2 M1 — Client-Neutral Authority and Operation Contracts

- Standard-library-only immutable contracts for typed campaign, scene, actor,
  command, event, and caller-operation references; exact contract version;
  controlled capability descriptors; selection, round, and reconstruction
  requests; fixture inspection; sanitized diagnostics; transient presentation;
  and stage-separated operation views.
- One `ControlledFixtureAuthorityPort` and `ControlledFixtureFacade` that depend
  only on client-neutral contracts. Unknown versions, identity kinds,
  capability keys, and operation states fail closed.
- One `InProcessControlledFixtureAdapter` over the existing controlled fixture.
  It maps selection and round results without replacing engine decisions or
  changing command gating, dice, durable-before-local publication, projection,
  synchronization, narration eligibility, or restart behavior.
- Side-effect-free inspection and capability discovery. The bounded capability
  set explicitly reports supported, unsupported, and currently unavailable
  states without composing combat or invoking files, commands, dice, providers,
  tools, or mutation paths.
- Caller-supplied operation correlation remains distinct from command and event
  identity. A fresh hydrated façade may correlate that caller reference with an
  existing authoritative command's durable events without reroll, dispatch,
  append, tool/provider execution, repair, or a durable outcome ledger.
- Operation views keep accepted/rejected/unknown submission, mechanical
  success/input-required/failure, durable commitment, process-local
  publication, projection, synchronization, and optional transient
  presentation independent. Fixed diagnostics expose no raw exception,
  traceback, credential, prompt, hidden payload, storage path, or provider
  detail.
- Dependency guards prevent the contract/application layer from importing
  Foundry, D&D 5e, UI, transport, providers, ToolAgent, tools, legacy managers,
  persistence, or concrete runtimes. The engine remains independent of both the
  application and adapter layers.

### Phase 2 M2 — Identity, Permission, Assignment and Visibility Core

- Standard-library-only immutable `phase2-m2-v1` contracts keep session,
  participant, Player/DM role, OOC/DM/actor speaker mode, controlled actor,
  player-character assignment, Speak-as grant, Act-as grant, viewing
  perspective, visibility audience, permission decision, and actor-control
  disposition distinct.
- An injected trusted identity authority resolves opaque session references.
  Unknown, revoked, expired, mismatched, or malformed identity results fail
  closed; M2 issues, verifies, stores, and transports no credential.
- Exact pure permission evaluation runs before M1 delegation. OOC grants no
  mechanical authority; DM speaker mode requires the resolved DM role but does
  not grant arbitrary actor control. A player-character assignment authorizes
  that participant's assigned actor.
- Speak-as and Act-as grants are independently participant-, campaign-, actor-,
  and capability-scoped. Revocation and optional UTC expiry use the injected
  trusted clock. Only the assignment or an active Act-as grant yields direct
  control; other actor disposition remains AI-default.
- `PermissionedControlledFixtureFacade` gates inspection, capability discovery,
  selection, controlled-round resolution, and operation reconstruction. Every
  denial returns only a bounded reason, delegates zero times to M1, and exposes
  no command, event, mechanical, presentation, or hidden identity payload.
- Authorized calls delegate exactly once through the unchanged M1 façade.
  Existing command gating, dice, durable-before-local publication, projection,
  synchronization, narration eligibility, and restart reconstruction remain
  unchanged.
- Immutable entries use explicit public, participant-set, DM-only, or
  no-client-disclosure audiences. Filtering returns only admitted entries,
  emits no placeholder or audience metadata, and never infers visibility from
  prose, event type, speaker choice, UI state, or AI interpretation.
- `InProcessPermissionContext` provides defensively copied process-local
  identities, assignments, grants, audiences, and fixed trusted UTC time for
  the controlled fixture. It makes no durable permission, authentication,
  reconnect, multiplayer, admission, or save claim.
- Dependency guards keep M2 contracts and evaluation client-neutral, concrete
  adapters pointing inward, the M1 authority adapter independent of M2, and the
  deterministic engine independent of both application and adapter layers.

### Phase 2 M3 — Durable Operation Identity and Idempotent Submission Core

- Immutable `phase2-m3-v1` contracts define campaign-scoped operation keys,
  bounded selection/round kinds, canonical request identity and SHA-256
  fingerprint, reserved/dispatch-started/terminal lifecycle, replay
  disposition, sanitized terminal correlation/outcome, and fixed diagnostics.
- Canonical identity binds the resolved participant, campaign, operation kind,
  M1 contract version, target actor, and complete bounded request payload.
  Labels and presentation text are excluded.
- `DurableOperationStorePort` owns exact lookup, first reservation,
  dispatch-started transition, and terminal recording. The dedicated
  `SQLiteDurableOperationStore` validates exact format/store/schema identity,
  canonical serialization, record integrity, and transaction-guarded state
  transitions.
- `DurableOperationCoordinator` runs only after M2 authorization and before M1.
  A new request claims dispatch once; a terminal exact retry returns stored
  sanitized evidence without M1; changed content under the same key collides;
  ambiguous dispatch never redispatches.
- A dispatch-started record may become terminal only when M1's existing
  correlation path finds committed durable event evidence. Eventless or
  otherwise unproven completion remains recovery-required.
- `compose_durable_permissioned_controlled_fixture` supplies the bounded M3
  composition. Inspection, capability discovery, permission evaluation, and
  unauthorized calls create no operation record and disclose no stored result.
- Initial eligible narration remains transient. Its text may be returned once
  to the authorized caller but is excluded from terminal durable evidence;
  replay neither persists nor regenerates it.
- Dependency guards keep contracts and coordinator client-neutral, SQLite in a
  concrete adapter, and the engine independent of application and adapters.

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

- Focused Phase 2 M3 contracts, store, coordinator, authorization, real-fixture
  effects, restart, collision, ambiguity, and replay tests: **21 passed**.
- Focused dependency-direction and M2 compatibility tests: **36 passed**.
- Complete client-neutral application suite, including M1/M2 compatibility:
  **87 passed**.
- Complete deterministic pytest suite: **701 passed**, with
  `dungeon_manager/ai/test_live_tool_loop_validation.py` explicitly excluded.
- Five isolated legacy smoke modules: **passed** for models, storage, managers, tools, and registry.
- Normal data/ and logs/ manifest: **unchanged** by path, type, size, UTC modification timestamp, and SHA-256.
- Live validator, Ollama, and all external AI providers: **not invoked**.

The two deterministic guard tests stored in dungeon_manager/ai/test_live_tool_loop_validation.py are excluded together with that file so the checkpoint command is visibly incapable of entering the live validator path.

## Known limitations

- Narration is implemented only for the single verified controlled-round event. It does not provide semantic proof of unrestricted provider prose, general event narration, persistence, streaming, retry, fallback, or automatic replay after restart.
- ToolAgent and tools are not part of the narration path and remain disconnected from controlled combat.
- Process-local audit history, command replay guards, provider history, narration text, and Python object identity do not survive restart. M3 persists only its bounded operation ledger and sanitized terminal evidence.
- All seven frozen slice milestones plus Phase 2 M1, M2, and M3 are complete and
  verified. No later Phase 2 milestone is approved by this checkpoint.
- The slice is one fixed campaign, one selectable player character, one hostile goblin, one permitted rapier attack, and one aggregate controlled-round event.
- Goblin tactical behavior is deliberately absent; the goblin-first path records only the accepted no-action advancement.
- Foundry VTT integration, UI, voice, general D&D rules, movement, spells, campaign discovery, editors, and broader content systems are not implemented.
- Event history and the bounded M3 operation ledger are durable. Command-audit
  history, dispatcher replay protection, and world-state snapshots remain
  process-local.
- M2 identities, assignments, grants, audiences, and clock data are
  process-local only; authentication and durable permission persistence are not
  implemented.
- Recovery, migration, repair, retries, polling, background workers, and cross-process coordination are not general product features.
- Ollama behavior has prior opt-in validation but remains nondeterministic and outside this checkpoint's pass/fail evidence.

## Next action

No unstarted milestone remains in the frozen seven-milestone slice. Phase 2 M1
and M1–M3 are complete and verified. No later Phase 2 milestone is approved or
scheduled; the next action requires a separately accepted bounded proposal.
D1–D5 and D7–D9 remain open, and the M2/M3 exclusions remain binding.
