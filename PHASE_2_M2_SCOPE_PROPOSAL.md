Dungeon Manager Phase 2 M2 Scope Proposal
Status: Accepted by the project owner on 2026-07-29. Not implemented. The authoritative repository acceptance checkpoint is still pending.
Verified basis:
Repository: LokoSokoL1/AI-DM
Branch: develop
Verified M1 commit: f0ed2680af649b465f5249256896a7b8a64aabe3
Accepted decisions: D6 and D10
Remaining Section 16 decisions: D1–D5 and D7–D9 remain open
Approved but unstarted milestone: M2 — Identity, Permission, Assignment and Visibility Core
Accepted bounded direction
M2 is approved as a bounded, client-neutral authorization core over the existing M1 boundary. M2 must prove that a resolved participant identity, explicit actor assignment, separate Speak-as and Act-as grants, and explicit visibility audiences can gate the controlled fixture without changing engine mechanics or claiming that authentication, transport, Foundry, multiplayer, saves, or permission persistence exist.
M2 does not require accepting any of the eight remaining Section 16 decisions:
D4 pairing and authentication implementation remains open. M2 consumes a session reference resolved by an injected trusted identity authority; it does not issue, verify, store, or transport credentials.
D3 transport and message schemas remain open.
D9 client-specific snapshot partitioning remains open. M2 filters explicit client-neutral views and visibility envelopes; it does not define snapshots.
D1, D2, D5, D7, and D8 remain outside M2.
Binding M2 scope
M2-A — Trusted identity resolution
A client supplies only an opaque session reference. A client-neutral identity authority resolves that reference to an immutable participant identity and authorized base role. A client-supplied participant name, role, speaker label, actor label, or presentation field is never proof of authority.
Unknown, expired, revoked, malformed, or unresolved session references fail closed before inspection, projection, command submission, dice use, durable append, local publication, provider/tool invocation, or presentation.
The initial bounded role set is Player and DM. OOC is a speaker mode, not a role. No production spectator or administrator role is introduced.
M2-B — Separate identity and authority concepts
M2 keeps these concepts distinct:
session reference;
participant identity;
base role;
selected speaker mode;
controlled mechanical actor;
actor assignment;
scoped Speak-as grant;
scoped Act-as grant;
viewing perspective;
explicit visibility audience.
Changing speaker does not change the controlled actor, viewing perspective, knowledge, assignments, base role, or permissions.
M2-C — Assignment and grant rules
A player-character assignment authorizes that participant to speak and act as the assigned character within the assigned campaign scope.
OOC is available to a resolved participant but grants no mechanical, narrative-authority, DM, assignment-management, or hidden-information permission.
DM speaker mode is available only to the resolved DM identity.
Speaking as an unassigned actor and acting as an unassigned actor are separate permissions and require separate explicit grants.
Grants are participant-, campaign-, actor-, and capability-scoped.
Grants are revocable and may carry an optional UTC expiry evaluated by an injected clock at the trusted application boundary.
An Act-as grant places only that actor under direct control for the grant's active scope. NPCs, companions, and AI party members otherwise remain AI-controlled by default.
Granting or revoking permission does not itself perform a mechanical action.
M2 may implement deterministic process-local assignment/grant state for the controlled fixture. It must not claim durable permission persistence, reconnection restoration, multiplayer admission, or save integration.
M2-D — Fail-closed permission evaluation
Permission checks are exact, typed, deterministic, and side-effect-free. The result is an immutable allow/deny decision with a bounded public reason code. Unknown roles, capabilities, speaker modes, identity kinds, grant states, visibility states, or contract versions fail closed.
Every permissioned operation is checked before it reaches the M1 authority façade. A denial returns a sanitized client-facing result and proves that no authoritative or presentation side effect occurred.
M2-E — Visibility filtering
Objective world state remains separate from participant-visible projections. M2 filters immutable entries carrying an explicit audience policy supplied by an authoritative producer; it does not infer visibility from prose, actor name, speaker selection, UI state, or AI interpretation.
The bounded audience model must support:
public audience;
an explicit participant set;
DM-only audience; and
no client disclosure.
Filtering returns only authorized entries. It does not emit redacted placeholders for no-disclosure entries, and switching speaker cannot widen the audience. M2 does not yet define D&D-specific roll-visibility translation, Foundry chat visibility, client snapshots, feed storage, or timing behavior.
M2-F — Permissioned M1 integration
Add a client-neutral permissioned façade or coordinator around the existing M1 controlled-fixture façade. Preserve the M1 façade and adapter as the authority-facing mechanism; do not move mechanical truth into the permission layer.
The bounded integration must:
resolve session identity through the trusted identity port;
return a permission-filtered inspection view;
return permission-filtered capability availability;
authorize controlled character selection;
authorize controlled-round resolution for the assigned actor;
authorize operation reconstruction without leaking unauthorized event identity;
evaluate all denials before delegating to M1; and
preserve the exact existing authoritative ordering and outcome contracts when delegation is allowed.
M1's existing public composition remains behaviorally compatible, but it is a lower authority-facing boundary rather than evidence that an external client is authorized.
M2-G — Contract version and dependency direction
M2 contracts use an explicit M2 version and adapt to M1 rather than silently changing M1 V1 semantics. The permission domain and contracts depend only on client-neutral standard-library types.
Concrete in-process identity, assignment, and visibility adapters point inward to those contracts. The deterministic engine and M1 authority adapter do not import the permission application layer.
Explicit non-goals
M2 does not implement or finalize:
credential issuance, password/token verification, pairing, login, cookies, or authentication transport;
HTTP, WebSocket, IPC, listeners, routing, remote clients, multiplayer, admission, reconnection, disconnect handling, host transfer, leases, or fencing;
Foundry modules, hooks, users, chat intake, UI, feed rendering, world discovery, or D&D 5e translation;
persistent users, permissions, assignments, grants, audit, personal preferences, or reconnection state;
general campaign discovery, arbitrary action execution, general NPC control, or new game mechanics;
D&D-specific public/private/blind/hidden roll classification;
saves, checkpoints, branches, snapshots, restoration, migration, reconciliation, or offline-change capture;
provider/tool authorization, ToolAgent integration, narration replay, or AI permission interpretation;
exact UI controls or styling; or
changes to the accepted 42 interface acceptance criteria.
Minimum validation evidence
M2 is complete only when deterministic tests prove:
immutable, validated, equality-stable, deterministically serialized M2 contracts;
unresolved or forged identity data fails closed;
client role/speaker/actor labels never create authority;
Player, DM, OOC, assigned-character, Speak-as, and Act-as rules remain distinct;
grants are scoped, independently revocable, and expiry-aware;
NPC direct control applies only while an Act-as grant is active;
visibility filtering never widens an audience and no-disclosure entries leave no placeholder;
changing speaker never changes viewing perspective or reveals hidden data;
every denied operation causes zero M1 delegation and zero files, commands, dice, events, provider/tool calls, or state mutation;
authorized selection and controlled-round journeys preserve M1 mechanics, durable-before-local publication, projection, synchronization, narration eligibility, and restart behavior;
permissioned reconstruction does not reveal unauthorized event references;
dependency guards preserve ports-and-adapters direction; and
all existing deterministic and isolated smoke suites remain green with data/ and logs/ unchanged.
Accepted project-owner decision
I approve Phase 2 M2 — Identity, Permission, Assignment and Visibility Core — with the bounded scope in PHASE_2_M2_SCOPE_PROPOSAL.md. M2 will add a client-neutral, fail-closed authorization core around the existing M1 controlled-fixture boundary. It will keep session identity, participant role, speaker mode, controlled actor, assignment, Speak-as and Act-as grants, viewing perspective, and visibility audience distinct. Client-supplied labels will never prove authority. Authentication, pairing, transport, Foundry, multiplayer, durable permission persistence, saves, snapshots, and reconciliation remain unimplemented and undecided where previously open. D1–D5 and D7–D9 remain open, and M2 must stop if implementation requires one of those decisions.
