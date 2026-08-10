# Dungeon Manager Architecture

## Status and scope

This document describes the architecture implemented on develop through all
seven First Playable Vertical Slice milestones and Phase 2 M3. Future work is
labelled explicitly. The frozen product behavior is in
[FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md).

Dungeon Manager is local first. The deterministic engine is authoritative for validated game actions and facts; AI components are clients, not state authorities; Foundry VTT is the intended presentation layer and is not implemented yet.

The
[Phase 2 low-fidelity interface design baseline](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md)
was formally accepted on 2026-07-29 from source SHA-256
`21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3`.
It approves future product behavior and acceptance criteria; it does not
describe implemented architecture. The interface and Foundry integration remain
unimplemented. On 2026-07-29, the project owner accepted D6's
ports-and-adapters ownership direction and D10's contract-first bounded Phase 2
implementation sequence. The other eight deferred implementation decisions
remain open as D1–D5 and D7–D9. The project owner accepted the bounded M2
architectural direction on 2026-07-29 and M3 durable-operation direction on
2026-07-30. The resulting client-neutral cores are implemented and
deterministically verified within those scopes. Future technical design and
implementation must conform to this baseline and the accepted decisions or
record an explicit revision.

[RI-001](docs/research/RI-001.md) provides evidence for several present boundaries and future candidate systems. Implemented architecture remains defined by the actual code and verified tests; research-derived candidates are not implemented merely because they appear in RI-001.

## Accepted Phase 2 architectural direction

D6 — Core/client API/adapter/permission/save/sync boundaries — establishes the
accepted ports-and-adapters ownership direction for future Phase 2 work:

- The existing deterministic engine remains the authoritative domain core.
- A client-neutral application layer will coordinate authority-facing
  operations without becoming a second source of mechanical truth.
- Durable operation identity belongs at the application/persistence boundary.
- Permission-filtered views remain separate from objective world state.
- Foundry and D&D 5e remain dedicated edge adapters. Foundry is the intended
  interaction and presentation surface, not campaign authority.
- AI components remain non-authoritative clients.

D10 — Implementation sequencing — establishes a contract-first bounded Phase 2
order. M1 — Client-Neutral Authority and Operation Contracts — introduced only
the minimum client-neutral authority and operation contracts needed to
represent the existing controlled fixture and support the immediate bounded
milestones. It did not finalize detailed contracts or behavior belonging to
later permission, transport, Foundry, multiplayer, save, branch, snapshot, or
reconciliation milestones. The later milestone sequence remains revisable only
through an explicitly accepted decision.

### Phase 2 M2 identity, permission, assignment, and visibility core

M2 wraps the M1 authority-facing façade without changing M1 V1 semantics:

    client-neutral caller
      -> PermissionedControlledFixtureFacade
      -> trusted identity, permission-state, clock, and visibility ports
      -> pure permission evaluation
      -> ControlledFixtureFacade only when allowed
      -> explicit audience filtering
      -> permissioned client view

`dungeon_manager.application.permission_contracts` owns the standard-library-
only immutable M2 contracts. Its explicit `phase2-m2-v1` version keeps opaque
session reference, resolved participant identity and base role, speaker
selection, controlled actor, player-character assignment, scoped Speak-as and
Act-as grants, viewing perspective, visibility audience, permission decision,
and actor-control disposition distinct. Unknown or untyped versions, roles,
speaker modes, capabilities, grant states, and audience states fail closed.

`dungeon_manager.application.permissions` performs exact, deterministic,
side-effect-free evaluation. A resolved active identity may inspect and discover
capabilities. OOC is a speaker mode with no mechanical authority. DM speaker and
DM perspective require the resolved DM role, but DM speaker mode alone grants no
actor control. A controlled player-character assignment authorizes speaking and
acting as that actor. Speak-as and Act-as grants are independently scoped to one
participant, campaign, actor, and capability; revocation and optional UTC
expiry are evaluated through the trusted injected clock. Only an assignment or
active Act-as grant yields direct actor control; otherwise NPC, companion, and
AI-party-member disposition remains AI-default.

`PermissionedControlledFixtureFacade` resolves identity and evaluates every
permission before calling M1. Denied views contain one bounded public reason and
no fixture, capability, command, event, mechanical, or presentation payload.
Authorized operations delegate through the next configured client-neutral
boundary only after permission succeeds. The original M2 composition delegates
directly to M1; the M3 composition routes only state-changing selection and
controlled-round submissions through the durable coordinator first. Command
gating, dice, durable-before-local publication, projection, synchronization,
narration eligibility, and restart behavior remain unchanged. A requested
actor, client label, speaker choice, existing engine selection, command ID, or
event ID is never proof of authority.

Visibility filtering consumes immutable entries carrying an explicit audience:
public, an exact participant set, DM-only, or no-client-disclosure. It returns
only admitted entries, exposes no audience metadata or placeholder for omitted
entries, and never derives visibility from prose, event type, UI state,
speaker selection, or AI interpretation. Objective M1/engine state remains
unchanged behind this participant-view boundary.

`InProcessPermissionContext` is the sole concrete M2 adapter. It defensively
copies preconfigured identities, assignments, grants, audiences, and a fixed
trusted UTC time, exposes only the four narrow read-only ports, and composes the
permissioned controlled fixture. This state is process-local verification state,
not authentication, credential handling, durable permission persistence,
reconnection restoration, multiplayer admission, or save integration.

The deterministic engine remains mechanical authority, durable committed event
history remains world-fact authority, M1 remains the authority-facing
client-neutral operation boundary, and AI remains non-authoritative. M2 did not
select D1–D5 or D7–D9.

### Phase 2 M3 durable operation identity and idempotent submission core

M3 adds one optional bounded composition without changing M1 or M2 contracts:

    client-neutral caller
      -> PermissionedControlledFixtureFacade
      -> M2 identity resolution and permission evaluation
      -> DurableOperationCoordinator for authorized state-changing calls
      -> DurableOperationStorePort
      -> SQLiteDurableOperationStore
      -> ControlledFixtureFacade only after an atomic dispatch claim
      -> existing runtime, engine, and durable event journal

`dungeon_manager.application.durable_operation_contracts` owns immutable
`phase2-m3-v1` contracts. A `CampaignOperationKey` scopes the caller operation
key to one campaign. `CanonicalOperationIdentity` binds the resolved participant,
campaign, bounded operation kind, M1 request contract version, applicable actor,
and complete frozen request payload. Canonical sorted JSON and a SHA-256 digest
make equality stable; the adapter compares both exact canonical content and the
digest, so a key reused for different content is a collision. Client labels and
presentation text are absent from this identity.

`DurableOperationStorePort` provides exact lookup, first reservation,
reserved-to-dispatch-started transition, and dispatch-started-to-terminal
recording. `SQLiteDurableOperationStore` is the sole M3 persistence adapter. It
uses an exact format, store identity, schema version, canonical JSON, per-record
integrity digest, `synchronous=FULL`, and transaction-guarded conditional
updates. Incompatible metadata/schema and malformed rows fail closed without
repair, migration, deletion, or internal-detail disclosure.

`DurableOperationCoordinator` reserves and atomically claims dispatch before
calling M1 once. Terminal exact retry returns sanitized stored correlation,
mechanical, event, publication, projection, and synchronization evidence
without invoking M1. Different canonical content collides. A dispatch-started
record never redispatches automatically. It may become terminal only when M1's
existing reconstruction path finds committed durable events for the stored
command without reroll, dispatch, append, projection, provider, or tool work;
otherwise it remains recovery-required.

The terminal record deliberately excludes transient presentation status and
text. Initial eligible narration may still run once and return transient text
to the authorized caller, but retry never renarrates or treats that text as
authority. Rejected, input-required, failed, successful, and eventless M1
results become terminal when returned normally; an eventless crash after the
dispatch claim remains safely ambiguous.

`compose_durable_permissioned_controlled_fixture` supplies the bounded
composition and path-bound store. M2 authorization always precedes ledger
access and outcome disclosure. Inspection, capability discovery,
reconstruction, permission evaluation, and denied calls do not reserve an
operation. M3 implements no durable permission state, transport, authentication,
Foundry, broader mechanics, save/snapshot system, repair, background work, or
general distributed coordination, and it does not select D1–D5 or D7–D9.

The other eight deferred implementation decisions, D1–D5 and D7–D9, remain
open.

## Phase 2 M1 client-neutral application boundary

M1 adds a narrow ports-and-adapters boundary without changing engine authority:

    client-neutral caller
      -> ControlledFixtureFacade
      -> ControlledFixtureAuthorityPort
      -> InProcessControlledFixtureAdapter
      -> existing campaign and controlled-round runtimes
      -> existing deterministic engine and durable publication pipeline

`dungeon_manager.application.contracts` owns standard-library-only immutable
client contracts:

- `AuthorityReference` plus `IdentityKind` distinguish campaign, scene, actor,
  command, event, and caller-operation identities.
- `ControlledFixtureView` reports the exact controlled campaign, scene, actors,
  selectable and selected character, complete event-reference tail, projection
  sequence, synchronization state, and controlled-round completion state.
- `CapabilityDescriptor` reports supported, unsupported, or currently
  unavailable controlled-fixture capabilities. Unknown versions, identity
  kinds, capability keys, and operation-state values fail closed.
- `SelectPlayerCharacterRequest`, `ResolveControlledRoundRequest`, and
  `OperationCorrelationRequest` carry only the inputs required by the existing
  fixture. Caller operation correlation remains distinct from authoritative
  command and event identity.
- `OperationView` independently reports submission, mechanical resolution,
  durable commitment, process-local publication, projection, synchronization,
  and optional transient presentation. `ClientDiagnostic` exposes only fixed
  sanitized codes and messages.

`ControlledFixtureFacade` performs version/type checks, capability discovery,
and sanitized fail-closed coordination against the narrow
`ControlledFixtureAuthorityPort`. Inspection and capability discovery read only
the already composed process-local runtime and do not compose combat, dispatch,
roll dice, append events, invoke providers, or mutate state.

`InProcessControlledFixtureAdapter` is the sole M1 concrete adapter. It maps
the existing controlled selection and round results into the client-neutral
views, lazily composes only the existing controlled combat path when a round is
submitted, and optionally invokes the existing verified narration boundary
only after synchronized mechanical success. It does not change fixture
validation, command gating, dice behavior, durable-before-local ordering,
projection, restart hydration, or narration eligibility.

Operation reconstruction accepts a caller-supplied operation reference and
authoritative command reference, then correlates them with existing durable
event facts in a freshly hydrated runtime. The caller operation reference is
not persisted as authority, is not an authorization credential, and provides
no durable cross-process request/outcome deduplication guarantee. No general
outcome ledger was added.

The application contract, port, and façade modules do not import concrete
runtimes, persistence, providers, tools, legacy managers, Foundry, D&D 5e, UI,
or transport code. The adapter depends inward on those client-neutral
contracts and on the existing fixture composition paths. The authoritative
engine imports neither the application nor adapter layer.

## Implemented dependency direction

The principal implemented flow is:

    caller
      -> campaign/combat runtime composition
      -> GameCommand
      -> automation policy and optional human approval
      -> GameEngine exact handler dispatch
      -> GameResult with zero or more GameEvents
      -> durable EventJournalStore
      -> process-local GameEventJournal
      -> WorldStateProjector
      -> WorldStateHolder

Command-audit records are appended to a separate process-local CommandAuditJournal around policy, gate, dispatch, publication, projection, and completion stages. The deterministic engine does not depend on AI providers, tools, managers, legacy JSON storage, Foundry, or a UI. Composition modules may inject those lower-level engine boundaries into a runtime.

## Implemented components

### Local application foundation

- config_loader.py reads local configuration.
- logger.py configures the local application log.
- models/ contains character, item, and campaign records.
- storage/json_storage.py owns legacy JSON persistence.
- managers/ owns model-specific create/load coordination.
- tools/ contains character tools, immutable ToolSpec schemas, and the central ToolRegistry.
- main.py composes the early local application path.

These legacy components remain supported. They are not the authoritative event-sourced engine state.

### Provider and AI tool boundary

AIProvider defines the provider interface. OllamaProvider is the current local adapter, and AIManager constructs it from configuration.

The tool path is deliberately bounded:

1. ToolAgent sends one deterministic prompt containing the sorted registry catalog.
2. The Tool Call Parser classifies one complete response as ordinary text, one valid whole-response JSON call, one clean JSON fence, or a controlled malformed result. It does not search prose for embedded JSON.
3. ToolRegistry resolves the exact registered tool and exposes immutable schema metadata.
4. ToolExecutor validates callable arguments and invokes at most one tool once, with no retry or fallback.
5. For a valid call, ToolAgent serializes one structured observation and makes at most one final provider request.

The ToolAgent loop is implemented for the character-tool path, but it is not connected to the game engine, controlled combat, or narration. The live Ollama harness is opt-in, loopback-only, temporary-storage isolated, and excluded from deterministic verification.

Verified combat narration uses a separate NarrationProvider interface. It accepts exactly one immutable VerifiedNarrationPacket and returns a typed result associated with the same source event ID and sequence. The interface supplies no ToolAgent, tool schema, parser, registry, executor, command, runtime, storage, or state-mutation capability.

### Deterministic command authority

GameCommand is an immutable intention with exact command type, command ID, actor ID, provenance, and deeply frozen JSON payload. Creating a command does not authorize it.

AutomationPolicy evaluates exact per-capability rules. Optional HumanApprovalDecision records are human-only. resolve_automation_gate returns a fail-closed disposition without executing behavior. PolicyGatedCommandDispatcher invokes GameEngine only for a ready command and records process-local command-ID replay protection before dispatch.

GameEngine registers one synchronous handler per exact command type and invokes at most one handler once. Unknown commands, invalid input, handler exceptions, invalid results, and invalid event collections become controlled GameResult outcomes. A successful result may contain an ordered tuple of immutable GameEvent facts.

### Audit, event, and projection boundary

GameEvent records a durable world fact. CommandAuditRecord records lifecycle evidence. They are separate because a denied or failed command can be audited without claiming that the world changed.

GameEventJournal and CommandAuditJournal are typed append-only process-local containers. Event batch preparation validates the complete ordered batch and assigns contiguous sequences before mutation. Batch append is all or nothing.

WorldState is immutable derived state. WorldStateProjector resolves every exact event-type/schema reducer before applying the batch in order. WorldStateHolder replaces its state only after complete projection success and separately tracks synchronization health.

AuditedCommandPipeline is the synchronous coordinator. It serializes submissions and prevents same-thread re-entry. It records proposal/policy/approval/gate/dispatch lifecycle stages, preserves the policy-gated result, publishes eligible events, projects the published entries, and records completion. It does not retry dispatch, publication, or projection.

### Durable event authority and restart

EventJournalStore owns the local SQLite event journal and its journal identity. SQLite details remain behind DurableJournalBinding.

For a successful event-producing command, the publication order is:

1. The handler creates complete GameEvent objects inside GameResult.
2. The pipeline validates and prepares one exact sequenced event batch against the current tail.
3. EventJournalStore atomically commits that batch first and returns verified identity/tail metadata.
4. The same prepared entry objects are appended atomically to the process-local GameEventJournal.
5. WorldStateProjector applies exactly those entries; WorldStateHolder publishes the new complete state once.
6. Completion audit records are appended independently.

Durable history is therefore authoritative. A durable failure exposes no local event or projection. If durable commit is confirmed but local append or projection later fails, the durable fact is not rolled back; synchronization health fails closed and a fresh hydration or explicit projection recovery is required. A later audit failure also does not roll back an already committed event or state.

hydrate_durable_runtime loads an existing journal, verifies its identity and complete ordered contents, constructs fresh in-memory journal and state-holder objects from an explicit sequence-zero base, and exposes a runtime only when durable, local, and projected tails agree. Hydration never dispatches, rerolls, appends, rewrites, repairs, or infers missing facts.

Milestone 6 proves the complete controlled round across a genuine process boundary. The proof releases the original campaign/combat runtime, journal mirror, projection, dispatcher, handlers, binding, provider, narration boundary, and result objects; it then composes two separate runtimes from newly constructed JSONStorage and EventJournalStore objects at the same fixture and SQLite paths. Only serialized durable event facts and derived projection facts are compared. The fresh runs neither call dice, dispatch, resolution, append, provider, ToolAgent, parser, registry, executor, nor tool boundaries. Fixture files, SQLite main database, and WAL when present are byte-hashed after the original store operation has completed; the SQLite `-shm` coordination sidecar is deliberately excluded from durable-content claims.

recover_world_state provides explicit catch-up and full-rebuild paths for process-local projection recovery. Recovery works from one immutable authoritative journal snapshot and commits a replacement state only if the journal tail remains unchanged.

## First Playable Vertical Slice architecture

### Campaign runtime and fixture

campaign_runtime.py owns one explicit V1 fixture, not campaign discovery:

- campaign: vertical-slice-v1
- journal: vertical-slice-v1-events
- scene: controlled-goblin-encounter
- selectable player character: nekria
- hostile participant: goblin-1

initialize_controlled_fixture is the only operation allowed to create its caller-supplied JSON and SQLite targets. It refuses existing or partial targets. load_controlled_campaign_runtime validates the manifest and referenced legacy records, constructs an explicit sequence-zero state, hydrates durable history, registers reducers and handlers, and exposes CampaignRuntime only after all dependencies agree.

campaign.select_player_character is the first slice command. Selecting Nekria produces one campaign.player_character_selected event through the same durable-before-memory pipeline. Invalid selection is eventless; repeated valid selection is idempotent and eventless.

### Dice

engine/dice.py is provider-neutral and storage-free. DiceRollRequest identifies a bounded dice expression. Both modes use the same total calculation:

- manual mode accepts explicit natural faces and records human_manual provenance;
- automatic mode consumes exactly one face per die from an injected AutomaticFaceSource and records engine_automatic provenance.

SystemRandomFaceSource is the production adapter. SequenceFaceSource provides deterministic faces for tests and controlled callers. Missing manual input returns the next request; invalid input or source failure exposes no partial roll and performs no retry.

### Controlled combat data

engine/combat_domain.py contains immutable fixture data only: Nekria and goblin-1 roles, initiative modifiers, armor class, hit points, and Nekria's nekria-rapier attack. combat_runtime.py validates this data against a hydrated runtime with Nekria selected before exposing ControlledCombatDomain and its explicitly unstarted seed.

This is not a general D&D rules engine, combat manager, or content system.

### Controlled player-attack round

engine/controlled_round.py is the pure adjudicator. controlled_round_runtime.py binds it to the existing command, policy, durable publication, and projection pipeline.

One combat.resolve_controlled_round command uses the fixed possible stage order:

1. Nekria initiative, 1d20+3.
2. goblin-1 initiative, 1d20+2.
3. Nekria rapier attack, 1d20+5.
4. Rapier damage, 1d8+3, only on a hit.

Initiative sorts by descending total, descending modifier, then ascending stable participant ID. Nekria-first begins directly on Nekria. Goblin-first records controlled_slice_no_goblin_behavior and advances without a goblin action or die roll.

Only a complete sequence creates one aggregate combat.controlled_round_resolved schema-1 event. The payload contains the rolls and provenance, initiative/order data, controlled no-action fact when applicable, attack and conditional damage, HP transition, defeat state, final round, encounter status, and active participant. The reducer validates that payload and projects it as one state transition.

Input-required and failed stages return no event and do not change initiative, turns, HP, or completion state. On restart, hydration replays the aggregate event and reconstructs the same state without calling the dice source or handler.

### Verified AI DM narration boundary

engine/verified_narration.py owns immutable narration facts and verifies that one `combat.controlled_round_resolved` journal entry exactly matches the current synchronized `controlled_combat` projection. The packet is bound to the source event ID and journal sequence and contains only stable encounter references, recorded roll faces/modifiers/totals/provenance, initiative order, controlled no-action fact, attack and conditional damage, HP transition, defeat, and final turn state.

verified_narration.py admits only a successful AuditedCommandPipeline result whose single event is durably committed, locally published, projected, and currently synchronized at the exact same tail. It additionally requires exact object identity with the runtime's in-memory journal entry before constructing the packet. ai/narration_provider.py is the dedicated provider-facing interface. One boundary instance attempts one eligible source event at most once, with no retry or fallback. Its text result is transient and is never published, projected, hydrated, parsed as a tool request, or treated as game state.

The implemented one-way flow is:

    durable verified controlled-round event + synchronized projection
      -> immutable VerifiedNarrationPacket
      -> narration-only provider
      -> transient presentation text

### End-to-end first playable acceptance

Milestone 7 exercises the production composition boundaries rather than private
handlers or reducers: explicit fixture initialization, runtime load and
hydration, durable character selection, controlled-combat composition, staged
manual or injected automatic controlled-round resolution, SQLite append,
local publication, projection, verified narration, shutdown, and fresh runtime
hydration. The two deterministic journeys cover Nekria-first surviving and
goblin-first terminal outcomes. They prove that one aggregate event is durable
before local publication, narration receives only its immutable verified packet,
and narration remains transient.

The original runtime graph is released before restart. Fresh composition uses
new JSONStorage and EventJournalStore objects at the durable paths and rebuilds
the same structured event and projected facts without dice, dispatch, combat,
append, provider, ToolAgent, parser, registry, executor, tool, narration replay,
or repair. This is a headless engine-level acceptance proof; it does not add UI,
Foundry, or voice.

## Atomicity and failure behavior

- Policy or approval rejection occurs before handler dispatch and event creation.
- Replay protection is recorded before an authorized dispatch and is process-local.
- Handlers return either a complete valid result or a controlled eventless failure.
- Dice resolution never exposes partial faces.
- Event preparation, SQLite append, in-memory batch append, and state replacement are individually all-or-nothing.
- The pipeline orders durable commit before process-local publication and projection.
- Projection consumes only authoritative published journal entries and commits state only after complete reducer success.
- No layer retries or silently repairs a failed operation.
- Durable/local divergence and projection failure are explicit health states; later dispatch fails closed until hydration or explicit recovery.
- Narration eligibility fails closed before provider invocation for incomplete publication, projection failure, unhealthy tails, malformed events, or event/projection disagreement.
- Narration-provider failure cannot roll back or modify the already authoritative combat event and projection, and it is not retried automatically.
- Sanitized caller results omit raw exception text, tracebacks, credentials, prompts, hidden payloads, and storage internals.

## State ownership

- Local configuration: config/config.json.
- Legacy entity and fixture records: JSONStorage at caller-supplied local paths.
- Authoritative game-event history: EventJournalStore in caller-supplied local SQLite.
- Current event journal mirror: process-local GameEventJournal.
- Current derived state: process-local WorldStateHolder, reconstructed from the journal.
- Command audit history: process-local CommandAuditJournal; it is not restart reconstructed.
- Command replay protection: process-local dispatcher state; it is not restart persistent.
- Caller operation correlation: supplied by the client and returned in M1
  operation views; M1 alone provides no durable deduplication.
- M3 controlled-fixture operation identity and sanitized terminal evidence:
  durable in a separate caller-supplied SQLite operation store. It coordinates
  at-most-once submission but is not world-fact or mechanical authority.
- Session identities, participant roles, controlled-fixture assignments,
  Speak-as and Act-as grants, visibility audiences, and the trusted test clock:
  immutable process-local M2 adapter state; none is durably persisted.
- Verified narration and tool observations: transient presentation data, never authoritative game state unless a future separately accepted owner is introduced.
- Foundry state: no implemented ownership or synchronization path.

## Future architecture

All seven frozen slice milestones are complete. No unstarted milestone remains in
this slice. The accepted Phase 2 interface baseline plus D6 and D10 constrain
future work. M1, M2, and M3 are implemented and verified within their bounded
controlled-fixture scopes. No later Phase 2 milestone is approved by this
checkpoint. General narration, narration persistence or replay,
semantic fact-checking of arbitrary prose, general rules, goblin tactics,
Foundry integration, UI, voice, durable permission persistence, durable audit,
restart-safe replay protection beyond M3's bounded operations, snapshots,
migration/repair, reconciliation,
background work, and cross-process coordination remain future work.
