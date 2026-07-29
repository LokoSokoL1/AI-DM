Dungeon Manager Phase 2 M2 Implementation Task
Status: Scope accepted by the project owner on 2026-07-29. Do not execute until that acceptance and this task are recorded in the authoritative repository and the resulting documentation checkpoint is clean and synchronized.
We are continuing development of Dungeon Manager, a modular local AI-powered tabletop RPG engine designed to work with Foundry VTT.
This task runs from the authoritative local repository at E:\Dungeon Manager. The repository is LokoSokoL1/AI-DM. Do not use automatically attached files, historical snapshots, ChatGPT Library copies, earlier prompts, or chat recollections to determine the current implementation state.
Implement only Phase 2 M2 — Identity, Permission, Assignment and Visibility Core. Do not begin transport, Foundry, multiplayer, persistence, save, or any later milestone.
Required accepted state
Before this task may be executed, the canonical repository documentation must record the project owner's acceptance of PHASE_2_M2_SCOPE_PROPOSAL.md, including:
trusted resolution of an opaque session reference through an injected client-neutral identity authority;
strict separation of participant identity, role, speaker mode, controlled actor, assignment, Speak-as grant, Act-as grant, viewing perspective, and visibility audience;
fail-closed permission evaluation before M1 delegation;
explicit audience filtering separate from objective world state;
a permissioned wrapper around the existing M1 controlled-fixture façade;
process-local bounded permission state only; and
all eight remaining Section 16 decisions staying open.
If that exact acceptance is not present, stop without editing.
Repository safety and preflight
Before editing:
Verify repository identity, local path, branch, HEAD, origin, upstream relationship, divergence, and Git status.
Confirm the branch is develop, the checkout is synchronized, and the working tree is clean.
Read the root AGENTS.md and every applicable nested AGENTS.md.
Read the current repository versions of:
README.md
ARCHITECTURE.md
DOCUMENTATION.md
GDD.md
FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md
PROJECT_PLAN.md
PROJECT_STATUS.md
PHASE_2_M1_IMPLEMENTATION_TASK.md
the accepted M2 scope record
docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md
docs/research/README.md
docs/research/RI-001.md
Inspect the full M1 contract, façade, authority-port, adapter, composition, dependency, and test surfaces.
Inspect current command provenance, policy gating, controlled fixture, durable publication, projection, synchronization, narration, and restart boundaries relevant to M2.
Verify M1 is committed and documented as complete, M2 is approved but unstarted, and D1–D5 and D7–D9 remain open.
If repository identity, branch, working-tree state, applicable instructions, canonical acceptance, or implementation structure differs, stop and report the discrepancy without editing.
Do not pull, fetch, switch branches, commit, push, create a pull request, modify GitHub, modify ChatGPT Library, invoke Foundry, or invoke Ollama.
Objective
Add the smallest coherent client-neutral authorization core that can:
resolve a caller's opaque session reference to a trusted participant identity without implementing authentication;
represent Player and DM roles while treating OOC as a non-authoritative speaker mode;
represent the controlled player-character assignment and separate scoped, revocable Speak-as and Act-as grants;
evaluate exact permissions and active actor-control disposition deterministically and fail closed;
filter explicitly audience-scoped client-neutral entries without mutating or replacing objective world state;
gate controlled-fixture inspection, capability discovery, selection, controlled-round resolution, and operation reconstruction before M1 delegation; and
preserve every existing M1 authority, ordering, mechanical, persistence, projection, synchronization, narration, and restart invariant.
Every new public contract must be required by this bounded controlled-fixture integration or by a concrete M2 invariant.
Required ownership boundaries
The deterministic engine remains the sole mechanical authority.
Durable committed event history remains authoritative for world facts.
M1 remains the authority-facing client-neutral operation boundary.
M2 authorizes and filters; it does not adjudicate mechanics or infer world facts.
AI remains non-authoritative and never interprets permissions.
Objective state and participant-visible projection remain separate.
Client-supplied names, roles, speaker labels, actor labels, and presentation fields are untrusted.
Authentication implementations, credentials, transport, Foundry, D&D 5e, multiplayer, saves, and synchronization adapters remain edge concerns outside M2.
Permission and visibility contracts must not import M1's concrete adapter, engine runtimes, persistence, providers, tools, UI, transport, Foundry, or D&D 5e.
The engine and M1 authority adapter must not import M2.
Minimum in-scope model
Choose exact names and module placement according to the repository's current conventions. At minimum, M2 needs immutable, validated, deterministic contracts for:
an explicit M2 contract version;
opaque session reference and participant reference;
Player and DM base roles;
OOC, DM, and actor speaker modes;
campaign-scoped player-character assignment;
separate Speak-as and Act-as grant capabilities;
grant identity, participant, campaign, actor, active/revoked state, optional UTC expiry, and deterministic evaluation;
viewing perspective kept distinct from speaker and actor;
explicit visibility audience supporting public, participant-set, DM-only, and no-client-disclosure cases;
permission request, allow/deny decision, and bounded sanitized reason codes;
an actor-control disposition that distinguishes AI-default from active direct control; and
permission-filtered inspection, capability, operation, and reconstruction views needed by the controlled fixture.
Unknown versions, identities, roles, speaker modes, capabilities, grant states, visibility states, or permission states must fail closed.
Required ports and bounded adapters
Add only the narrow ports required to:
resolve a session reference to its authoritative participant identity and base role;
read the participant's controlled-fixture assignment and active grants;
obtain the trusted current UTC time for expiry evaluation; and
obtain explicit visibility audiences for the bounded view entries being filtered.
Provide one deterministic in-process adapter/composition for the controlled fixture. It may use preconfigured process-local identities, assignment, grants, and visibility metadata. It must not issue credentials or claim durable permission state.
Neutral permission inspection and evaluation must not mutate assignments, grants, files, journals, projections, or runtime state.
If bounded grant/revoke mutation is added, it must:
be authorized only for the resolved DM identity;
be exact, deterministic, and process-local;
keep Speak-as and Act-as independent;
never dispatch a game command or create a game event;
expose no credentials or hidden payloads; and
make no persistence, reconnect, audit-durability, or multiplayer claim.
Do not add mutation merely to make the model look complete. Prefer immutable preconfigured fixture state if that satisfies the accepted M2 evidence.
Permissioned controlled-fixture integration
Compose a new permissioned façade/coordinator around ControlledFixtureFacade; do not duplicate or bypass its authority mappings.
For every entry point:
validate the M2 contract version and typed request;
resolve the session reference through the trusted identity port;
resolve assignments/grants through the permission authority;
evaluate the exact requested capability, speaker, actor, and viewing perspective;
deny with a sanitized typed result before M1 delegation when unauthorized;
delegate exactly once to M1 when authorized;
validate the returned M1 result; and
apply only explicit audience filtering to the client-facing view.
Cover at least:
permission-filtered inspection;
permission-filtered capability discovery;
Nekria selection by the assigned Player;
controlled-round resolution by the assigned Player;
DM speaker mode without treating it as arbitrary actor control;
OOC mode with no mechanical authority;
explicitly granted Speak-as without Act-as;
explicitly granted Act-as without Speak-as;
permissioned operation reconstruction; and
unknown/revoked/expired identity or grant denial.
The permissioned façade must not derive permission from the requested actor, existing selection, engine success, client label, AI output, or possession of a command/event identifier.
Visibility requirements
Filter only immutable entries with explicit audience metadata.
Preserve objective facts unchanged behind the filtering boundary.
Public entries are visible to every resolved participant.
Participant-set entries are visible only to listed participants.
DM-only entries are visible only to the resolved DM identity.
No-client-disclosure entries are omitted entirely.
Speaker changes never change the viewing perspective or visibility audience.
Do not emit placeholder cards, counts, identifiers, timing hints, or diagnostics for omitted entries.
Do not infer D&D roll visibility, Foundry visibility, knowledge, or secrecy from text or event type.
Explicit non-goals
Do not implement or finalize:
credential issuance or verification, pairing, login, cookies, passwords, tokens, or authentication transport;
HTTP, WebSocket, IPC, listeners, message schemas, routing, remote clients, multiplayer, admission, reconnect, disconnect, host transfer, leases, or fencing;
Foundry modules, hooks, users, chat intake, UI, feed rendering, world discovery, or D&D 5e translation;
durable users, permissions, assignments, grants, preferences, audit, or reconnect state;
general campaign discovery, arbitrary action execution, general NPC control, or new game mechanics;
D&D-specific roll-visibility classification;
saves, checkpoints, branches, snapshots, restoration, migrations, reconciliation, or offline-change capture;
provider/tool authorization, ToolAgent integration, provider retries, narration persistence, or AI permission interpretation;
exact UI controls or styling; or
changes to the accepted 42 interface acceptance criteria.
If implementation requires D1–D5 or D7–D9, stop and report the smallest blocking decision instead of selecting it.
Deterministic verification
Add focused tests using the existing repository approach. Cover at least:
immutability, validation, defensive copying, equality, and deterministic serialization for every externally visible M2 contract;
distinct session, participant, role, speaker, actor, assignment, grant, perspective, and audience identities;
unknown and malformed values failing closed;
forged client roles, speaker labels, actor labels, and presentation data never creating authority;
exact Player, DM, OOC, assigned-character, Speak-as, and Act-as behavior;
grant scoping, independent revocation, expiry boundaries, and injected-clock determinism;
AI-default versus active direct actor control;
public, participant-set, DM-only, and no-disclosure filtering;
speaker changes never widening visibility;
zero M1 calls and zero authoritative/presentation side effects on every denied path;
one authorized manual and one authorized automatic controlled-fixture journey with exact existing authoritative ordering;
permissioned reconstruction without rerolling, redispatch, append, provider, tool, repair, or unauthorized event disclosure;
M1 public compatibility;
dependency-direction enforcement; and
explicit evidence that no credential, transport, Foundry, multiplayer, persistence, save, snapshot, or reconciliation capability is claimed.
Inspect deterministic test configuration first. Run with bytecode generation and pytest caching disabled. Do not run the live Ollama validator, Foundry, browser automation, or network-dependent tests.
At minimum run:
focused M2 tests;
directly affected M1, command, policy, pipeline, projection, persistence, runtime, restart, narration, acceptance, and dependency tests;
the complete deterministic suite with dungeon_manager/ai/test_live_tool_loop_validation.py excluded; and
the five isolated smoke entry points.
Compare data/ and logs/ manifests before and after testing by path, type, size, UTC modification time, and SHA-256. Run git diff --check. Confirm that no pytest cache, bytecode, or unintended generated files remain.
Documentation
After successful implementation and verification, update only directly relevant canonical documentation:
ARCHITECTURE.md
PROJECT_PLAN.md
PROJECT_STATUS.md
any M2-specific technical document required by repository conventions
Record only implemented and verified behavior. Keep D1–D5 and D7–D9 open. Do not claim authentication, Foundry, transport, multiplayer, durable permissions, saves, snapshots, or reconciliation.
Final handoff
Report:
repository, path, branch, starting and ending HEAD, origin, upstream, divergence, and initial/final status;
applicable instructions and canonical sources inspected;
files changed;
exact M2 contracts, ports, evaluators, façades, and adapters added;
how trusted identity resolution avoids implementing authentication;
exact assignment, Speak-as, Act-as, OOC, DM, expiry, revocation, actor-control, and visibility behavior;
how every denial occurs before M1 delegation;
how authorized M1 mechanics and ordering remain unchanged;
dependency and ownership invariants;
every explicit non-goal preserved;
tests and exact results;
data/ and logs/ comparison;
documentation updated;
unresolved evidence or any needed roadmap revision; and
confirmation that nothing was committed, pushed, pulled, fetched, or changed on GitHub, ChatGPT Library, Foundry, or Ollama.
Stop after the M2 implementation handoff. Do not commit, push, or begin a later milestone.
