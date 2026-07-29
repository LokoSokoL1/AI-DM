# Dungeon Manager Low-Fidelity Interface Specification V1

Status: Formally accepted Phase 2 low-fidelity interface design baseline

Acceptance date: 2026-07-29

Accepted source SHA-256:
`21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3`

Maturity: Approved design, not implemented

Acceptance scope: The product behavior and acceptance criteria are approved.
The explicitly deferred implementation decisions in Section 16 remain open.

Hash note: The accepted source SHA-256 identifies the exact draft formally
accepted by the project owner. This administrative status update changes the
repository-tracked file's current SHA-256; it does not change the accepted
design.

## 1. Purpose and scope

This document specifies the approved low-fidelity product behavior for the first
Dungeon Manager interface. Normal Phase 2 play occurs inside Foundry through a
compact Dungeon Manager sidebar and an expanded in-Foundry Manager view. The
compact sidebar replaces or takes over Foundry's normal chat-sidebar experience
while Dungeon Manager is active. A separate companion window is not required
for normal play.

Foundry is the first supported client and tabletop renderer, not Dungeon
Manager's foundation or authority. The engine, deterministic mechanics, AI
orchestration, campaign state, saves, permissions, and authoritative history
remain client-independent and may run headlessly. Foundry communicates through
a documented, versioned client-neutral contract and purpose-built adapters so a
future web, desktop, or other client can be supported without relocating core
authority into Foundry.

This specification defines product behavior, presentation, interaction,
permissions, startup, persistence, restoration, multiplayer mediation, status,
and recovery. It deliberately does not select exact implementation APIs,
transport schemas, Foundry hooks, authentication mechanisms, adapter boundaries,
or a frontend framework. It does not claim that any interface, Foundry
connection, general intent interpreter, multiplayer system, save system, or
broader gameplay system is implemented.

The implemented slice remains the narrow headless loop described by the current
repository: load and hydrate the controlled campaign fixture, select Nekria,
compose the controlled goblin encounter, resolve one player attack with manual
or automatic dice, durably publish and project one aggregate event, request one
transient verified narration, and reconstruct the same authoritative state after
a fresh restart.

In this document:

- **Implemented** identifies behavior already established by current code and
  tests.
- **Required interface behavior** identifies a proposed requirement for this
  draft.
- **Approved product behavior** identifies a reviewed decision that this
  proposed interface and its future implementation must satisfy.
- **Open implementation decision** identifies a technical choice intentionally
  deferred without weakening approved product behavior.

### 1.1 Required first-interface behavior

The proposed first interface must:

1. open in a neutral launcher state and require explicit campaign, linked-world,
   and session/checkpoint choices before state mutation;
2. expose connection, compatibility, persistence, projection, and presentation
   health without granting those indicators authority;
3. provide one permission-filtered gameplay feed that classifies Foundry chat
   events, messages, narration, rolls, mechanics, actions, requests,
   resolutions, and important recovery notices;
4. provide an authenticated speaker/role selector while keeping speaker,
   controlled actor, viewing perspective, knowledge, and permission distinct;
5. present submitted intent, actionable interpretation, authoritative
   mechanics, and AI narration as separate layers;
6. support per-user or authorized-role dice preferences, separate roll
   visibility, secret-roll protection, and bounded visible-roll overrides;
7. persist every authoritative state change, create recovery checkpoints,
   support deliberate named saves, and represent restoration as a new branch;
8. preserve authoritative campaign state plus sufficient Foundry presentation
   state to reconstruct the tabletop without treating Foundry as authority;
9. support host-mediated multiplayer, filtered join/reconnection, distinct
   player-client, presentation-module, and host-authority disconnection
   behavior, and fail-closed host-authority loss;
10. replace or take over the normal Foundry chat-sidebar experience while
    Dungeon Manager is active;
11. open an expanded Manager view inside Foundry without requiring a separate
    companion window for normal play;
12. use a dedicated Dungeon Manager Foundry module and a dedicated D&D 5e
    adapter while keeping the core and client contract independent;
13. preserve external Dungeon Manager authority and durable state when the
    embedded Foundry surface is unavailable, and require explicit
    reconciliation before provisional offline Foundry changes can become
    authoritative;
14. keep native Foundry chat usable as a compatibility/troubleshooting fallback
    and keep non-authoritative native Foundry viewing, navigation, chat, and
    other permitted activity available where safe; and
15. keep hidden state, secret rolls, private knowledge, credentials, raw
    exceptions, prompts, and provider or storage internals out of unauthorized
    views.

### 1.2 Later design candidates

The following remain later candidates outside the minimum Phase 2 interface
even though this specification preserves compatible boundaries:

- broader campaigns, characters, encounters, actions, and D&D rules beyond the
  completed slice and the interface contracts defined here;
- voice interaction, a separate player-facing desktop application, and direct
  remote exposure of the Dungeon Manager service;
- world creation and general-purpose scene, NPC, or campaign editors;
- narration streaming or narration persistence;
- continuous general-world simulation, broad NPC cognition, location
  preparation, and ambient simulation; and
- a production spectator role, host transfer, and additional client types.

Research Iteration RI-001 may inform later evaluation of these candidates. It
does not make them accepted product requirements or implemented behavior.

### 1.3 Explicitly out of scope

This draft does not:

- select, launch, rebind, or modify an existing Foundry world during this
  documentation task;
- create a Dungeon Manager test world;
- place engine, persistence, or AI authority inside the Foundry process;
- require or use Integrate AI as a runtime dependency, adapter, compatibility
  layer, or architectural option;
- define a Foundry protocol, module, hook, database mapping, or synchronization
  implementation;
- commit to a frontend framework or Foundry API;
- use a separate companion window for normal play;
- extend the controlled encounter beyond Nekria, goblin-1, and Nekria's rapier;
- implement general intent interpretation or connect ToolAgent to combat;
- make narration authoritative, persistent, replayed, or self-validating;
- implement the approved campaign-save, branching, multiplayer, permission,
  adapter, pairing, migration, or restoration requirements;
- add durable audit history, restart-safe general replay protection,
  background work, or cross-process coordination in this task; or
- begin a broader Phase 2 plan.

### 1.4 Approved behavior versus open implementation

The product decisions in this specification are approved and must not be
reopened as alternatives. Exact sidebar controls and styling, chat-takeover
lifecycle and hooks, transport and message schemas, pairing/authentication
mechanisms, host-transfer protocol, adapter API boundaries, detailed
compatibility policy, reconciliation UI and provisional offline-change capture
mechanism, snapshot field partitioning, and implementation sequencing
remain open for the appropriate technical milestone.
Section 16 lists only those deliberately deferred implementation choices.

## 2. Verified environment and implementation inputs

The target Phase 2 compatibility baseline is a design input, not a new
implementation commitment:

- Foundry VTT generation 14, stable build 364;
- D&D 5e system version 5.3.3;
- Integrate AI disabled before Phase 2 implementation begins; and
- a dedicated Dungeon Manager Foundry module/adapter as the required integration
  direction.

The current observed local development state at the referenced checkpoint is:

- four discovered worlds: `bonkers`, `my-first-world`, `the-bs-world`, and
  `wacky-world-of-adventure`;
- no configured active or last-used world;
- `bonkers` uniquely identified as the intentionally empty local integration
  test world;
- `bonkers` contains no actors, scenes, items, journal entries/pages, combats,
  roll tables, playlists, cards, compendia, effects, fog, or ordinary scene or
  asset files;
- `bonkers` contains two AI-DM test macros plus routine settings, one user
  record, folders, and chat messages;
- Integrate AI enabled in `bonkers`, contrary to the target disabled-module
  baseline; and
- other discovered worlds contain prepared or imported content.

The `bonkers` designation is verified local development information, not a
general product requirement or permission to modify that world. Product
startup must still require explicit world selection. Disabling Integrate AI in
`bonkers` remains a pending local setup action before Phase 2 implementation.
Integrate AI is rejected as a runtime dependency or compatibility layer. This
documentation task does not modify Foundry. The two existing test macros may
remain temporarily as historical reference, but no new implementation may
depend on them or on Integrate AI.

## 3. Presentation-surface decision

| Arrangement | Decision and benefits | Drawbacks and risks |
|---|---|---|
| Expandable Foundry-embedded interface | **Approved product behavior.** Keeps tabletop and ordinary play in one application; replaces or takes over normal chat while active; opens an expanded in-Foundry Manager; requires no companion window for normal play. | Requires a purpose-built module, host-mediated service connection, synchronization, and careful permission filtering. |
| Standalone Dungeon Manager companion | Rejected as a normal-play requirement. A future diagnostic or administrative tool may use the client-neutral API if separately approved. | Would split ordinary play across surfaces and must not become required for Phase 2. |
| Separate-control hybrid | Rejected for normal play. | Conflicts with the approved embedded ordinary-play model. |

### 3.1 Approved direction

While Dungeon Manager is active, the compact Dungeon Manager sidebar replaces
or takes over the normal Foundry chat-sidebar experience. It is the ordinary
play interface and contains one unified, permission-filtered gameplay feed:

- player, DM, and OOC messages;
- AI narration;
- Foundry rolls and roll cards;
- visible damage, healing, conditions, effects, and other mechanical results;
- submitted and interpreted actions;
- pending actions and dice requests;
- verified resolutions;
- important synchronization, connection, and recoverable failure notices;
- player input and current speaker/role; and
- persistence and Foundry-synchronization status.

The dedicated Foundry adapter consumes and classifies Foundry chat events; it
does not visually copy the native chat interface. Routine system and module
chatter is filtered by default. Technical messages remain available through
feed filters, Diagnostics, or native Foundry chat. Native chat remains
accessible for compatibility and troubleshooting. Mirrored events require
stable source IDs or equivalent deduplication. Public, private, blind, and
hidden visibility is preserved end to end: an event never becomes visible
merely because it passed through Dungeon Manager.

The compact sidebar opens an expanded Manager view inside Foundry. The expanded
view is permission-aware and organized into:

- **Session:** campaign, linked world, saves, branches, sessions, players, and
  connection;
- **Character:** permitted sheet summary, inventory, abilities, resources, and
  conditions;
- **Journal:** Player Journal, objectives, known leads, notes, and permitted
  relationships;
- **World:** discovered locations, known factions, and permitted campaign
  information;
- **Settings:** dice preferences, model/provider configuration, rules, and
  automation, filtered by authority; and
- **Diagnostics:** synchronization, failures, recovery, compatibility, and
  technical messages.

Players receive only information they know or are permitted to access. The DM
receives additional management and hidden-state controls.

The external Dungeon Manager local service remains the authoritative reasoning
and orchestration service. The deterministic engine resolves mechanics;
persistence owns durable history; AI providers interpret or narrate without
deciding outcomes; and Foundry hosts the first client and tabletop presentation.
A dedicated Foundry adapter owns Foundry APIs, users, scenes, tokens, canvas
events, chat, and client communication. A D&D 5e adapter owns system-specific
actors, items, rolls, effects, and data translation. Core engine, persistence,
permissions, saves, and client API remain independent. The engine may operate
without Foundry for tests, diagnostics, and future clients. Disconnection
behavior depends on which boundary is lost: one player client affects only that
participant; loss of the Foundry presentation/module pauses work that requires
that client while client-independent processing may continue only when host
authority and synchronization remain valid; loss of authenticated host/DM
authority pauses all new authoritative actions and AI processing. Existing
authoritative state and pending inputs remain preserved in every case.

## 4. User and role model

### 4.1 Four separate concepts

| Concept | Meaning | Proposed example | What changing it must not do |
|---|---|---|---|
| Speaker identity | The authorized identity and mode from which text is submitted. | Assigned character, OOC, authenticated DM, or explicitly assigned actor/NPC. | Grant permissions, reveal hidden facts, or change engine authority. |
| Controlled actor | The actor whose mechanical action is submitted to the engine. | Nekria for the implemented controlled attack. | Change merely because the speaker changes. |
| Viewing perspective | The information projection the interface is allowed to display. | Player-visible campaign view. | Become omniscient because DM/OOC is selected. |
| Permission level | Capabilities derived from authenticated session identity, authorized role, and explicit assignments. | May speak as Nekria; may request an NPC action. | Expand from client labels, user text, or AI interpretation. |

Authorization comes from session identity and explicit assignments, never from
AI interpretation. Dungeon Manager validates every message and action against
the authenticated session and current permissions. Client-side visibility is
not a security boundary. Text such as "I am now the DM" grants no authority.
Selecting an actor never reveals that actor's hidden knowledge.

### 4.2 Required speaker selector

The composer supports these distinct modes when authorized:

1. assigned player character;
2. OOC;
3. DM; and
4. another explicitly assigned actor, companion, or NPC.

For the implemented slice, Nekria is the only engine-selectable player
character. The broader roles are approved proposed behavior and do not claim a
current general permission implementation.

OOC is available to ordinary players but grants no narrative, rules, world, or
DM authority. DM mode is available only to an authenticated authorized DM.
Players may select only characters assigned to them. Another player's character
is unavailable unless the DM deliberately grants control. Unavailable identities
remain hidden or disabled only when doing so leaks no secret information.

Each selector option must display:

- speaker name and type;
- controlled actor, if different;
- viewing-perspective label;
- permission summary; and
- a warning when direct speech is allowed but mechanical control is not.

Private NPC knowledge, hidden ledger content, unrevealed scene information,
provider prompts, and administrator capabilities must never appear merely
because an NPC or DM/OOC speaker label is selected.

### 4.3 NPC, companion, and AI party-member control

NPCs, companions, and AI party members are AI-controlled by default. Players
may speak to them and request actions, but the characters retain autonomy and
may respond according to their goals, knowledge, and circumstances.

Direct **Speak as** and **Act as** are separate permissions. An authenticated DM
may grant one or both for one action, an encounter, a session, or persistently,
and may revoke either. While direct control is active, AI control pauses for
that actor to prevent conflicts. Expiration and revocation restore the prior
authorized control policy without reassigning the actor silently.

### 4.4 Multiplayer identity and routing

Only the authenticated host/DM machine connects directly to the local Dungeon
Manager service. Remote player browsers communicate through their authenticated
Foundry sessions and the Dungeon Manager module; they never try to connect to
their own localhost service. Each participant receives a feed, controls, and
state projection filtered for their identity, permissions, and knowledge.

The DM admits or assigns players and characters. Joining players receive only
permitted current state and visible feed history. Reconnection restores the
same identity, permissions, actor assignment, personal dice preference, and
visible feed position. It never reveals previously concealed rolls, private
journals, secret NPC knowledge, or hidden messages. A disconnected character is
not reassigned automatically; the DM may grant temporary control or allow AI
control. A separate read-only spectator role may be supported later.

Phase 2 may deliver local single-user play first, but its client, identity,
permission, feed, and service contracts must not assume that every participant
runs Dungeon Manager locally.

## 5. Screen and panel inventory

All states below are proposed UI states. They do not imply implemented screens
or asynchronous services.

| Screen or panel | Surface | Purpose and information displayed | Available actions | Information kept hidden | Applicable states |
|---|---|---|---|---|---|
| Connection and pairing | Compact badges; Session and Diagnostics | Show **Connected**, **Reconnecting**, **Incompatible**, or **Offline**; distinguish player-client, presentation/module, and host-authority availability; identify pairing state, versions, and capabilities. | Pair once when authorized; reconnect; open diagnostics. | Credentials, pairing secrets, tokens, cookies, raw transport details. | Neutral; pairing; connected; reconnecting; incompatible; offline. |
| Launcher and startup gate | Compact sidebar; Session | Show compatible campaigns linked to the open world and explicit **Resume**, **Start new session**, and **Load checkpoint** choices. | Select campaign/session/checkpoint; inspect compatibility; cancel. | Hidden campaign data and credentials. | Connecting; neutral; ready; incompatible; offline. |
| Compact Dungeon Manager sidebar | Foundry chat sidebar | Provide ordinary play and the unified classified feed while Dungeon Manager is active. | Compose; select authorized speaker; answer visible roll prompts; filter; expand result cards; open Manager or native chat. | Unauthorized feed entries, secret mechanics, prompts, raw engine payloads. | Inactive; launcher; ready; action pending; degraded; blocked. |
| Unified gameplay feed | Compact sidebar | Merge permitted messages, narration, Foundry rolls/cards, mechanics, actions, requests, verified results, and important notices with source IDs and distinct visual classes. | Scroll; filter; expand permitted result details; open native chat or Diagnostics. | Hidden/blind/private entries and routine technical chatter by default. | Empty; loading; current; filtered; incomplete; stale. |
| Expanded Manager shell | Expanded in-Foundry view | Provide permission-aware **Session**, **Character**, **Journal**, **World**, **Settings**, and **Diagnostics** sections. | Navigate; return to tabletop; perform authorized actions. | Knowledge and controls outside the current participant's permissions. | Loading; ready; warning; blocked section; failure. |
| Speaker or role selector | Sidebar; permission details | Show assigned character, OOC, authorized DM, and expressly assigned actors with separate **Speak as**/**Act as** permissions. | Select an authorized mode; inspect grant scope/expiry. | Unauthorized identities and hidden actor knowledge. | Loading; ready; temporary grant; speech-only; denied. |
| Player input composer | Compact sidebar | Capture intent or speech with speaker, actor, channel, and submission state. | Submit; edit; clear; cancel while genuinely pending. | Hidden reasoning, system prompts, and private context. | Ready; interpreting; confirmation required; pending; accepted; rejected. |
| Action interpretation and confirmation | Feed card | Briefly show submitted intent and actionable interpretation. Under the default policy, gate ambiguity, unusual consequence, known-state conflict, or overwrite/restore/reconcile/migrate/rebind risk; show any authorized stricter policy that adds gates. | Confirm; revise; cancel while pending; authorized DM/admin may manage stricter policy in Settings. | Chain-of-thought, hidden AI reasoning, and policy controls unavailable to ordinary players. | Interpreting; proceeds; confirmation required; cancelled; failed. |
| Dice controls | Prompt card; Settings | Separate personal/role roll mode from public/private/blind/hidden visibility; protect secret rolls. | Enter a visible manual result; use one-time override; optionally update own default. | Hidden-roll existence, secret DCs/modifiers, seeds. | No roll; visible prompt; automatic; verified; invalid; source failure. |
| Scene and encounter context | Tabletop and compact summary | Show permitted active scene, participants, turn/round, visible HP/resources/effects, and sync state. | Inspect/focus visible objects. | Unrevealed actors, statistics, fog, secrets, and private effects. | No scene; loading; ready; pending; stale; unavailable. |
| Verified mechanics | Feed result card | Show visible roll, modifier, target, result, damage/healing/effects, provenance, and persistence evidence separately from narration. | Expand permitted breakdown. | Hidden rolls, secret difficulty, private modifiers, inaccessible state. | Pending; verified; saved; desynchronized. |
| Interpretation and narration recovery | Feed; Diagnostics | Keep failed pre-dispatch interpretation pending separately from post-resolution narration; show stable request/event identity and retry eligibility without hidden reasoning. | Retry an eligible pre-action interpretation; DM retries narration, chooses another configured provider/model, or supplies narration manually. | Provider credentials, prompts, raw exceptions, and hidden reasoning. | Interpreting; pre-dispatch retry eligible; narration queued; final; delayed; failed; manually supplied. |
| Saves, branches, and restoration | Session | Show campaign, branch, session, checkpoint, save type, creation reason, compatibility, and restore preview. | Create named save; load with confirmation; create safety checkpoint; reconcile; delete branch separately. | Raw storage internals and unauthorized branch content. | Current; saving; safety checkpoint; preview; restoring; reconciling; verified; failed. |
| Character | Character | Show permitted sheet summary, inventory, abilities, resources, and conditions. | Inspect and perform only authorized actions. | Other players' or hidden actor data. | No assignment; loading; ready; stale; denied. |
| Journal | Journal | Show Player Journal, objectives, known leads, notes, and permitted relationships. | Browse/filter/edit personal notes when authorized. | Hidden ledger, secret objectives, NPC knowledge. | Empty; loading; ready; incomplete; denied. |
| World | World | Show discovered locations, known factions, and permitted campaign information. | Browse and inspect permitted provenance. | Undiscovered locations, hidden factions, future events. | Empty; loading; ready; stale; denied. |
| Settings | Settings | Separate DM/admin campaign settings from each player's personal settings. | Authorized changes only; campaign changes are validated and audited. | Credentials and hidden provider/configuration details from players. | Loading; ready; changed draft; applying; success; rejected. |
| Players and assignments | Session | Show joined/disconnected identities, actor assignments, scoped control grants, and optional spectator status. | DM admits/assigns/revokes; participant inspects own assignment. | Private data and permissions outside the viewer's role. | Joining; active; disconnected; temporary control; revoked. |
| Diagnostics and recovery | Diagnostics | Show synchronization, failures, compatibility, technical feed entries, sanitized IDs, distinct disconnection category, provisional-change status, and safe recovery controls. | Reconnect; recheck; rehydrate; reconcile captured provisional changes; export sanitized summary if approved. | Credentials, prompts, cookies, raw tracebacks, unrelated paths. | Collecting; ready; client unavailable; authority lost; reconciliation pending; recovered; blocked. |

DM/admin-controlled settings include model/provider, ruleset, campaign
automation, world binding, shared campaign defaults, credentials, and privileged
diagnostics. Player-controlled settings include that participant's dice
preference, interface preferences, accessibility, personal notifications, and
feed filters. Players may see relevant connection status but never credentials,
hidden configuration, or unauthorized provider diagnostics. Every
campaign-changing setting, including an authorized stricter confirmation
policy, is visible to authorized users, validated by Dungeon Manager, and
recorded in authoritative audit history. Ordinary players cannot enable,
disable, or bypass campaign confirmation policy through UI selection or prompt
text.

## 6. Information hierarchy

### 6.1 Continuously visible

The compact Dungeon Manager sidebar must continuously show:

- selected campaign and linked world, or neutral launcher state;
- active branch, session, and checkpoint;
- assigned player character;
- speaker identity, controlled actor, perspective, and permission summary;
- the current participant's default and current-action dice mode;
- host/service status as **Connected**, **Reconnecting**, **Incompatible**, or
  **Offline**;
- Foundry tabletop synchronization state;
- durable/local/projected synchronization state; and
- whether the workspace is ready, pending, degraded, or blocked.

The Foundry tabletop remains visible beside the compact sidebar. The expanded
Manager is reached from the sidebar and does not replace the tabletop for
ordinary play.

### 6.2 Secondary information

The expanded Manager may contain:

- **Session:** campaign, world binding, saves, branches, sessions, players, and
  connection;
- **Character:** permitted sheet, inventory, abilities, resources, and
  conditions;
- **Journal:** Player Journal, objectives, known leads, notes, and permitted
  relationships;
- **World:** discovered locations, known factions, and permitted campaign
  information;
- **Settings:** authority-filtered dice, interface, provider, rules, and
  automation controls;
- **Diagnostics:** synchronization, recovery, compatibility, and technical
  messages;
- compatibility details;
- event and command identifiers;
- safe persistence-tail and checkpoint details; and
- role and permission explanations.

### 6.3 Contextual information

The following should appear only when relevant:

- manual dice input;
- automatic dice progress;
- visible-roll waiting state; hidden rolls create no player-facing contextual
  state, notification, timing change, or reserved layout;
- action ambiguity, consequential-action confirmation, or invalid-input
  correction;
- persistence, restoration, reconciliation, migration, or synchronization
  recovery;
- narration generation; and
- provider failure controls available to the DM.

### 6.4 Required action hierarchy

Every action card must make these layers visually distinct:

1. **Participant submission** — exactly what the authorized speaker submitted.
2. **Actionable interpretation** — the sanitized proposed action, briefly
   visible and never presented as a fact or hidden reasoning.
3. **Input or confirmation required** — a permitted visible dice request or a
   confirmation required by a mandatory category or the active authorized
   stricter campaign/testing policy.
4. **Resolution state** — pending, failed without event, or verified.
5. **Authoritative change** — event type, source command, sequence, and
   player-visible before/after facts after durable commit and projection.
6. **Persistence state** — durable commit and synchronization result.
7. **Narration** — later presentation text with a visually separate
   non-authoritative label.
8. **Foundry presentation** — synchronized, pending, stale, unavailable, or not
   configured.

The interface must never use the same color, icon, heading, or card treatment
for generated narration and verified mechanics. Narration may describe a hit,
but only the verified mechanics card may assert that the hit occurred.
Technical execution details are collapsed by default and remain in Diagnostics.
Permitted users may expand a mechanics card for visible roll, modifier, target,
and result details. No expansion reveals secret difficulties, hidden rolls,
private modifiers, inaccessible state, or hidden reasoning.

### 6.5 Implemented ordering represented by the interface

For the controlled round, the implemented authority order is:

> complete engine result → durable event commit → process-local journal
> publication → projection → synchronized state → verified narration packet →
> transient narration

The interface may animate or summarize that order, but must not display later
stages as complete before their evidence exists. A durable commit followed by
local publication or projection failure is not a total failure: the durable
fact may already be authoritative, and the interface must enter a
desynchronized recovery state rather than invite resubmission.

## 7. World-selection flow

### 7.1 Initial state

When a Foundry world opens, the Dungeon Manager sidebar enters a neutral
launcher state and attempts to connect to the host's local service. It shows
compatible campaigns and sessions but does not automatically resume, load, or
mutate campaign state. The user explicitly chooses **Resume**, **Start new
session**, or **Load checkpoint**.

Even when a linked Foundry world is already open, opening it is not consent to
resume play. The interface must not infer a state-changing choice from
modification time, directory order, title, prior discovery order, or a blank
last-world configuration value. If the service is unavailable, native Foundry
chat remains usable.

### 7.2 Discovery list

The proposed discovery list may display:

| World ID | Title | Discovered system | Verified local evidence |
|---|---|---|---|
| `bonkers` | Bonkers | D&D 5e 5.3.3 | Local development target; Integrate AI must be disabled before implementation |
| `my-first-world` | Freaklands | D&D 5e 5.3.3 | Contains an actor, a scene, and imported compendium content |
| `the-bs-world` | The BS World. | D&D 5e 5.3.3 | Contains substantial actors, scenes, journals, items, tables, macros, and compendia |
| `wacky-world-of-adventure` | Wacky world of Adventure | D&D 5e 5.3.3 | Contains a scene, items, journal data, and macros |

Only `bonkers` may carry **Verified local development target**, and only in this
local setup. No row may carry **recommended** or **last used**. The local target
label must not become a product default or permit automatic selection.

Each row must show:

- world ID and title;
- system ID and recorded system version;
- Foundry/core compatibility metadata when safely available;
- whether the row is the verified local development target;
- compatible, warning, unsupported, or unavailable status; and
- safely verified module-baseline warnings, including legacy Integrate AI state.

### 7.3 Explicit selection and validation

1. The compact sidebar shows the currently open Foundry world as an unconfirmed
   candidate and offers the expanded Manager for discovery and selection.
2. The user selects one row. Selecting a different world must not silently
   switch, launch, or modify Foundry; the interface instead explains the
   separately required user action.
3. The interface repeats the exact world ID/title and requests confirmation.
4. Compatibility is evaluated against the first supported Phase 2 baseline:
   Foundry VTT v14 Build 364 and D&D 5e 5.3.3. Later support requires explicit
   compatibility-matrix evidence.
5. A mismatched system blocks the controlled D&D 5e presentation path. A version
   mismatch produces an explicit warning or block according to a future approved
   compatibility policy.
6. Selection does not create, initialize, modify, or activate anything in the
   Foundry world.
7. Selecting `bonkers` shows a local-setup warning while Integrate AI remains
   enabled. It must be disabled before Phase 2 implementation, but this draft
   authorizes no Foundry change.
8. Selection never requires or routes through Integrate AI.
9. Clearing the choice returns to **No Dungeon Manager world confirmed**.

A Dungeon Manager campaign is explicitly linked to one Foundry world. Multiple
sessions, checkpoints, and branches may belong to that campaign. The interface
must distinguish the Foundry world identity from client-neutral campaign
authority and must not silently copy, switch, or rebind state.

### 7.4 Verified local development target

`bonkers` is the unique genuinely empty integration-world candidate on the
current machine because it has:

- zero actors, scenes, items, journal entries/pages, combats, roll tables,
  playlists, cards, effects, fog, and compendium documents;
- zero ordinary scene or asset files;
- one routine user record, routine settings, folders, and chat messages; and
- two explicitly AI-DM test macros rather than prepared campaign content.

Its D&D 5e 5.3.3 system matches the desired baseline. Its module state does not:
Integrate AI is enabled. No unrelated module is enabled. Integrate AI's enabled
state is a pending local setup action, not a product feature, compatibility
layer, or open architectural choice. The two existing test macros may remain
temporarily as historical reference.

World creation remains outside this draft. A general future product may offer a
separately approved creation flow, but the current local setup does not need
another test world.

### 7.5 Campaign, world, and session binding

- Each campaign records one explicit linked Foundry world identity.
- Multiple sessions, saves, checkpoints, and timeline branches may belong to
  that campaign.
- Dungeon Manager never silently switches Foundry worlds.
- Rebinding is a deliberate DM/admin management action requiring identity and
  compatibility checks, a safety checkpoint, a visible impact preview, and
  confirmation.
- A natural-language request may open a named checkpoint flow, but replacement
  still requires authorized confirmation.
- If the open world does not match the campaign binding, state-changing actions
  remain blocked until the intended world is opened or an authorized rebind is
  completed.

### 7.6 Local connection and pairing

The privileged Dungeon Manager service accepts host-local/loopback access by
default, and the host/DM machine automatically attempts that local connection.
Under default configuration, the service does not listen for or accept remote
or network clients. Remote player browsers route through the authenticated
Foundry session and Dungeon Manager module; they never connect to their own
localhost service. Each relevant Foundry world/user relationship uses one-time
secure pairing, and later sessions reconnect automatically. Enabling any future
remote service exposure requires a deliberate authorized configuration action
and is not part of default startup.

The interface distinguishes **Connected**, **Reconnecting**, **Incompatible**,
and **Offline**, and always provides manual reconnect and Diagnostics access.
Exact transport, configuration format, message schemas, pairing,
authentication, and remote-exposure mechanisms remain open technical decisions.

## 8. Session flows

### 8.1 Flow-to-implementation map

| Flow | Proposed low-fidelity sequence | Current source boundary |
|---|---|---|
| First connection | Opening the world opens the neutral launcher, attempts host-local connection, negotiates versions/capabilities, and shows **Resume**, **Start new session**, and **Load checkpoint** without mutating campaign state. | The engine is headless and has no Foundry dependency. No embedded UI, pairing, transport, or connection lifecycle exists. |
| Select or verify a world | The Session view shows the current world, campaign link, compatibility, and explicit selection/rebinding controls. Dungeon Manager never switches Foundry worlds silently. | No Foundry discovery, chat takeover, world-switching, or world-binding API is implemented. |
| Start a new Dungeon Manager session | Confirm the linked world, choose **Start new session**, create a unique session on the active branch, and create the initial recovery checkpoint before unlocking play. | `initialize_controlled_fixture` creates only the known fixture and refuses existing or partial targets. General sessions/branches are proposed. |
| Resume a session | Choose **Resume**, validate campaign/world/branch/session identities and journal state, hydrate, synchronize Foundry presentation, and unlock only after verification. | `load_controlled_campaign_runtime` and startup hydration fail closed and expose no partial runtime. General save browsing is not implemented. |
| Load a checkpoint | Select a checkpoint, review branch and compatibility impact, create a safety checkpoint, confirm replacement, load on a new timeline branch, restore tabletop presentation idempotently, and verify synchronization. | General checkpoints, branches, tabletop snapshots, reconciliation, and restoration are not implemented. |
| Create a named save | Enter a deliberate name; capture current authoritative state and the applicable client-neutral/Foundry presentation snapshot without interrupting per-action persistence. | The current journal is durable, but named saves and presentation snapshots are not implemented. |
| Change settings | Validate whether the current identity owns a personal preference or DM/admin campaign setting; show the active confirmation policy to authorized users; let only an authenticated DM/admin add stricter confirmation gates; apply and audit campaign-changing settings; never let a player alter/bypass policy or expose credentials. | General settings authority, confirmation-policy enforcement, and durable audit are not implemented. |
| Select a character | Use the expanded Manager's character section to confirm Nekria; reflect the selection in the compact sidebar only after its durable result is synchronized. | `CampaignRuntime.select_player_character` currently accepts only Nekria in the fixture; invalid selection is eventless and repeat selection is idempotent/eventless. |
| Grant NPC/companion control | The DM grants **Speak as**, **Act as**, or both with visible scope/expiry; AI control pauses only for that actor while direct control is active; revocation restores the prior policy. | General actors, permissions, NPC autonomy, and control handoff are not implemented. |
| Submit an ordinary role-play message | Validate authenticated identity, selected speaker, assignments, and visibility; classify the message into the unified feed; show AI response separately; create no mechanics/history claim unless an authoritative path produces an event. | ToolAgent ordinary text is not connected to the engine, controlled combat, verified narration, or durable events. |
| Submit a clear ordinary action | Show intent and actionable interpretation briefly. Under the default policy, proceed without an extra confirmation; under an authorized stricter policy, require its added confirmation. Mandatory confirmation categories always remain gated, and an ordinary player cannot alter or bypass the active policy. | General action interpretation, confirmation policy, and durable campaign audit are not implemented. |
| Submit an action requiring a tool | In the compact sidebar, show the interpreted single tool request and status; execute at most one exact registered tool once; show observation/final text separately from authoritative engine events. | ToolAgent/parser/registry/executor implement one bounded character-tool turn. This path is not connected to controlled combat or engine authority. |
| Resolve one attack | Present the fixed action and all input/progress inside the compact sidebar; compose the controlled combat domain after Nekria selection; collect manual faces or use the injected automatic source; show no state change until complete. | `compose_controlled_combat_domain` and `ControlledRoundRuntime.resolve` implement the fixed Nekria-versus-goblin rapier sequence. |
| Persist the result | In the same sidebar action card, show durable commit pending; on success show event sequence, local publication, projection, and synchronized health; only then mark mechanics verified. Expanded details remain available. | The audited pipeline commits the complete event durably before local publication and projection. |
| Restart and reproduce saved state | Reopen the linked world, remain in the launcher, choose **Resume**, hydrate authoritative history, synchronize Foundry presentation, and display reconstructed mechanics without reroll or automatic narration replay. | Both acceptance journeys reconstruct identical authoritative facts without dice, dispatch, append, tools, provider calls, repair, or narration replay. |
| Player join or reconnect | The DM admits/assigns; the module restores only that participant's identity, assignments, dice preference, visible feed position, and permitted current/history projection. | Multiplayer identity, permissions, routing, and filtered history are not implemented. |
| Individual player client disconnects | Preserve that participant's identity, assignment, pending input, and visible feed position; stop accepting inputs from that client while host authority and other authorized play continue. Do not reassign the character automatically. | Per-client connection state and multiplayer identity are not implemented. |
| Foundry presentation/module connection unavailable while authority remains | Preserve authoritative state and pending inputs; pause actions that require that Foundry client. Permit genuinely client-independent processing only while authenticated host authority and synchronization remain valid. If Foundry itself remains open, non-authoritative native viewing, navigation, and chat may continue; if Foundry is absent, those surfaces are unavailable. Verify synchronization before resuming client-dependent actions. | Foundry is absent from engine dependencies. Embedded presentation, reconnection, and synchronization are unimplemented. |
| Authenticated host/DM authority lost | Pause all new authoritative actions and AI processing and preserve state/pending inputs. Permit non-authoritative native viewing, navigation, chat, and other safe activity. A native state-changing action may proceed only if the adapter can capture it as an ordered, identified provisional change; otherwise prevent or clearly refuse it. Reconnect, reconcile captured provisional changes, synchronize, and only then resume. Never grant simultaneous authority. | Cross-process host authority, provisional capture, reconciliation, and coordination are not implemented. |
| Recover from pre-action interpretation failure | Retry only the same immutable submitted input under its stable request identity while it remains pre-dispatch and diagnostics prove no tool, command, event, or authoritative persistence occurred. A successful retry returns to normal confirmation/execution and can produce at most one authoritative action. | ToolAgent retries and a general interpretation-recovery coordinator are not implemented. |
| Recover narration after verified mechanics | Keep the durable verified event unchanged; let the DM reconstruct/reuse its eligible narration packet, retry with another configured provider/model, or narrate manually. Recovery may alter wording but cannot invoke tools or repeat mechanics, commands, or persistence. | Narration failure cannot change the committed event. A general provider-recovery coordinator is not implemented. |

### 8.2 Manual acceptance journey mapping

The proposed UI must reflect the manual acceptance journey as follows:

1. initialize/load the controlled fixture;
2. select Nekria and confirm durable selection sequence 1;
3. compose the controlled encounter;
4. request Nekria initiative, goblin initiative, attack, and conditional damage
   in that fixed order;
5. retain entered faces only as UI-local pending input while each incomplete
   request remains eventless;
6. submit the complete face set through one controlled-round resolution;
7. show one aggregate sequence-2 event only after durable commit, publication,
   and projection;
8. request narration only from the exact verified event/projection; and
9. resume into the same authoritative facts without reroll or narration replay.

### 8.3 Automatic acceptance journey mapping

The proposed UI must reflect the automatic acceptance journey as follows:

1. use automatic mode for the complete action;
2. show the four possible stages in order without exposing source internals;
3. show whether damage was skipped on a miss;
4. show provenance as engine automatic;
5. commit and project exactly one aggregate event;
6. present verified narration afterward; and
7. resume from durable facts without calling the automatic source again.

### 8.4 Persistence, checkpoints, and branching

Dungeon Manager persists after every authoritative action or state change and
creates periodic recovery checkpoints during play. Users may also create
deliberate manual named saves. Before load, reconciliation, migration, rebind,
or a similarly disruptive operation, the system creates a safety checkpoint.

Restoring older state always requires explicit confirmation and starts a new
timeline branch. Later progress on the original branch remains recoverable, and
new actions affect only the active branch. The sidebar and Session view clearly
identify the active campaign, branch, session, and checkpoint. Deleting a branch
is a separate deliberate operation and is never implied by loading or starting
a branch.

### 8.5 Complete campaign and tabletop save content

A save preserves client-neutral authoritative campaign state and enough
Foundry-specific presentation state to reconstruct the tabletop. The two forms
remain distinguishable even when captured together.

Where applicable, a save includes:

- active and prepared scenes, plus the current active scene;
- token identity and actor links;
- token coordinates, elevation, rotation, size, visibility, disposition, and
  relevant control state;
- HP, resources, conditions, effects, and actor/token state;
- combatants, initiative, round, and active turn;
- doors, lights, templates, fog/exploration, and gameplay-relevant scene
  changes;
- journals, inventory, relationships, objectives, known leads, world state,
  clocks, events, and authoritative history; and
- direct Foundry changes that were validly synchronized into authoritative
  state.

The exact boundary between client-neutral state and client-specific snapshot
fields remains open, but no boundary may omit data required for safe,
trustworthy tabletop reconstruction.
Captured provisional offline changes are not authoritative save content unless
and until explicit reconciliation accepts them into authoritative history.

### 8.6 Explicit load and restoration flow

Loading must:

1. confirm the correct linked world;
2. create a safety checkpoint and load the selected authoritative checkpoint
   onto a new branch;
3. recreate or select necessary scenes;
4. restore tokens and relevant scene state;
5. restore an active encounter when applicable; and
6. verify synchronization before declaring success.

The flow never silently overwrites an incompatible current scene. Missing,
deleted, or conflicting content enters reconciliation rather than guessing.
Retrying a partial restoration is idempotent and must not duplicate tokens,
encounters, or effects. A natural-language request such as "load the save before
the ambush" may open this flow, but authorized confirmation remains mandatory.

### 8.7 Multiplayer join, reconnection, and disconnection boundaries

The host/DM is the only direct local-service client. Remote participants use the
authenticated Foundry session and module. The DM admits players and assigns
characters; each participant receives only permitted state and visible feed
history.

Reconnection restores identity, permissions, assignment, personal dice
preference, and visible feed position. It never backfills concealed rolls,
private journals, secret NPC knowledge, or hidden messages. Disconnection does
not reassign a character automatically.

The interface and recovery contract distinguish three disconnection categories:

1. **Individual player client disconnected while host authority remains.** Stop
   inputs and presentation updates for that participant, preserve that
   participant's pending inputs and reconnectable state, and continue authorized
   play for the host and other connected participants. Do not reassign the
   disconnected character automatically.
2. **Foundry presentation/module connection unavailable while Dungeon Manager
   authority remains.** Pause actions that require that Foundry client. Permit
   genuinely client-independent processing only while authenticated host
   authority and synchronization remain valid. Preserve authoritative state and
   pending inputs. If Foundry itself remains open, native viewing, navigation,
   chat, and other non-authoritative activity may continue; if Foundry itself is
   absent, those surfaces are unavailable. Client-dependent actions resume only
   after reconnection and synchronization succeed.
3. **Authenticated host/DM authority or its Dungeon Manager connection lost.**
   Pause all new authoritative actions and AI processing, preserve authoritative
   state and pending inputs, do not promote another participant, and prevent a
   second Dungeon Manager instance from acquiring simultaneous authority over
   the active campaign. Native Foundry viewing, navigation, chat, and other
   non-authoritative activity may remain available.

During host-authority loss, a native Foundry change that would affect
authoritative campaign state must never silently become authoritative. Such an
action may proceed only if the adapter can capture it as a provisional offline
change with sufficient authenticated source identity, target identity,
causality/ordering information, and original payload for deterministic review;
otherwise the adapter must prevent or clearly refuse it. Captured provisional
changes enter explicit reconciliation after the authenticated host reconnects.
No new authoritative action or AI processing resumes until host authentication,
synchronization, and any required reconciliation all succeed.

Future host transfer requires deliberate authorization and secure re-pairing.
The exact reconciliation UI, provisional-capture mechanism, transport, and
host-transfer protocol remain open.

## 9. Manual and automatic dice behavior

Roll mode and roll visibility are separate concepts. Mode controls who supplies
the roll; visibility controls who may know that it exists and what they may see.
Visibility may be public, private, blind, or fully hidden according to ruleset
and permissions.

Each player controls manual or automatic mode only for their own assigned
character. The authenticated DM has an independent preference for DM-controlled
creatures and rolls. Preferences are stored per user or authorized role, never
as an unrestricted global player setting. A participant may change their own
preference at will and cannot change another participant's preference.

### 9.1 Manual mode

For each pending stage, the interface displays:

- stage name and stable roll ID;
- dice expression and visible modifier;
- valid natural-face range;
- the instruction to enter the natural face, not the modified total;
- already supplied stage faces; and
- the statement **No authoritative state changes until the complete controlled
  round resolves**.

Manual prompts are shown only when the request and its existence are visible to
that participant. A manual preference never creates a prompt for a hidden roll.

Submitting an out-of-range value, a non-integer, the wrong number of faces, or a
value for the wrong stage shows an inline error and creates no event. The user
may correct the input and submit again with a new safe command attempt.

### 9.2 Automatic mode

Automatic mode displays stage progress such as **Generating Nekria initiative**
without displaying random-source internals or implying that Foundry or the
provider determines the roll. A complete roll shows natural face, modifier,
total, and `engine_automatic` provenance.

An automatic-source failure exposes no partial roll or event. The interface
returns to a safe unresolved state and lets the user choose an explicitly safe
new attempt.

For the Phase 2 player-facing workflow, hidden or secret rolls are automatic.
They produce no player prompt, notification, timing change, reserved layout, or
other disclosure that the roll occurred. A player's manual preference cannot
alter this behavior. The authoritative result is recorded while every
participant receives only the information permitted by visibility and knowledge
rules. Any future DM-only hidden-adjudication mechanism is outside the Phase 2
baseline and must preserve zero player disclosure.

### 9.3 Pending, submission, and verification

The visible progression is:

> requested → awaiting input or automatic source → complete roll set →
> resolving → durable commit → local publication → projected/verified mechanics
> → transient narration → Foundry presentation status

**Submitted** does not mean **verified**. A roll becomes part of authoritative
state only inside the one complete aggregate event after successful durable
publication and projection.

### 9.4 Cancellation

The current engine has no cancellation command. Incomplete manual stages are
eventless, so the proposed interface may allow the user to close or cancel the
UI-local pending entry before successful resolution. Cancellation discards only
the UI draft and accumulated uncommitted faces. It must not claim to reverse a
dispatch, durable commit, or verified event.

If dispatch outcome is unknown, **Cancel** becomes unavailable and the
interface must verify persistence/hydration state before allowing another
attempt.

### 9.5 Duplicate submission

The interface must:

- disable the submit control while an attempt is unresolved;
- retain one caller-generated command ID for the attempt;
- classify timeout/connection loss as **outcome unknown** until authoritative
  state is checked;
- never generate a fresh command ID merely to bypass an uncertain result; and
- render `already_resolved` as an idempotent no-change outcome.

Process-local command replay protection exists, and the controlled fixture also
rejects a second completed round after restart. General restart-safe duplicate
protection is not implemented, so the UI must not claim broader guarantees.

### 9.6 Mode changes and overrides

Changing a personal or authorized-role default affects unresolved eligible
requests and future rolls only. It never changes, rerolls, or reclassifies a
completed result. It also does not override visibility or reveal hidden
requests.

A visible roll prompt may offer a one-time manual/automatic override and an
option to update the participant's saved default. The override applies only to
the identified eligible request and preserves actual provenance. It must not
mix provenance inside the current one-mode controlled round unless a future
engine contract explicitly permits it.

### 9.7 Provider and Foundry failures during rolling

The AI provider and Foundry are not dice authorities. Their failure must not
alter, supply, reroll, or reinterpret a face.

- Before engine submission, retain or discard only the safe UI-local draft.
- During an unknown submission outcome, check durable state before retry.
- After verified resolution, keep the result and show provider or Foundry
  failure as a separate presentation problem.

### 9.8 Action confirmation and cancellation

Under the default campaign policy, clear ordinary actions proceed without an
extra confirmation after the unified feed briefly shows submitted intent and
actionable interpretation. Ambiguous, unusually consequential, conflicting,
restorative, reconciliatory, migratory, rebinding, or other state-replacing
operations always require confirmation.

An authenticated, authorized DM/admin may enable a stricter campaign or testing
policy that requires confirmation for additional action categories. A stricter
policy may add requirements but cannot remove mandatory confirmation or any
permission boundary. Authorized users can see the active policy. Dungeon
Manager validates and records every campaign-level policy change in
authoritative audit history. An ordinary player cannot enable, disable, alter,
or bypass the policy through UI selection or prompt text.

A participant may cancel while an action is genuinely pending. Once the result
is verified, an unfavorable outcome is not undone merely because the
participant cancels or dislikes it. The interface shows actionable
interpretation, never hidden AI reasoning.

## 10. Transient narration

### 10.1 Pending and streaming presentation

The implemented narration provider returns one final typed result; streaming is
not implemented. The first interface should therefore show a pending indicator
without fabricated partial text.

If streaming is later accepted, partial text must be labelled **Draft narration
— non-canonical**, remain visually temporary, and never enter an authoritative
event, projection, journal fact, or player-known fact solely because it was
displayed.

### 10.2 Final narration

Final narration appears only after:

1. one successful controlled-round result;
2. confirmed durable commit;
3. local publication;
4. synchronized projection at the exact event sequence; and
5. construction of the immutable verified narration packet.

The narration card displays **AI narration — non-authoritative presentation**
and the source event reference. Verified mechanics remain visible beside it.

### 10.3 Narration failure after successful resolution

The interface must retain the verified mechanics and persistence success, then
show:

> The action succeeded and is saved. Narration was unavailable.

It must not roll again, redispatch combat, append another event, revert state,
or make the action appear failed.

The failed narration remains visibly pending or failed where appropriate.
Players receive a concise delay or error message; technical details remain in
DM Diagnostics.

### 10.4 Pre-action interpretation retry

A failed interpretation may use the pre-action retry path only while the request
remains pre-dispatch. The retry retains one stable request identity and exactly
the same immutable submitted input, authenticated session identity, actor
assignment, and relevant context reference. Before enabling retry, Dungeon
Manager must prove that:

- no tool was invoked;
- no authoritative command was dispatched;
- no authoritative event was created; and
- no authoritative state change was persisted.

Interpretation-attempt diagnostics may be recorded, but those diagnostic records
must neither constitute nor trigger an authoritative game-state event. If any
authoritative work may already have occurred, the request is ineligible for this
path and enters outcome-unknown verification/recovery instead.

After a successful interpretation retry, the unchanged request proceeds through
the active confirmation policy and normal execution exactly once. The stable
request identity and dispatch guard must ensure that all interpretation attempts
can result in at most one authoritative action.

### 10.5 Post-resolution narration retry

After a verified durable mechanical event exists, the approved interface lets
the authenticated DM retry narration, select another configured provider/model,
or supply narration manually. Each retry reconstructs or reuses the same
eligible immutable narration packet from that same durable event and
synchronized projection, preserving source event ID, sequence, and idempotency
identity.

Post-resolution recovery may change presentation wording only. It must not
invoke tools, repeat commands, reroll, reapply damage, movement, effects,
persistence events, or cause any other authoritative state change. Regenerated
or manually supplied narration remains non-authoritative. The implemented
`VerifiedNarrationBoundary` is still one-shot and does not yet provide this
coordinator, so these controls remain proposed, not implemented.

### 10.6 Reconstruction after restart

Restart currently reconstructs authoritative event and projection facts but
does not automatically replay narration. The UI may show **Narration not
retained** beside the reconstructed mechanics. Reconstructing or regenerating
narration from a recorded event is permitted only through the explicit,
idempotent post-resolution recovery flow above; it is never automatic during
restart.

## 11. Authority and responsibility matrix

| Layer | Owns or may do | Must not do | Current status |
|---|---|---|---|
| Foundry interface | Host the compact sidebar, unified feed, expanded Manager, and native-chat fallback; submit authenticated participant intent; render only filtered presentation. | Decide mechanics, grant authority, expose hidden entries, or equate client display with persistence. | Approved proposed behavior; no UI is implemented. |
| Dedicated Foundry adapter/module | Own Foundry APIs, users, scenes, tokens, canvas events, chat classification/deduplication, client communication, synchronization, restoration, capability negotiation, and provisional offline-change capture or refusal. | Own campaign truth, silently promote provisional changes, omit source identity/ordering from captured changes, embed core concepts in Foundry objects, or depend on Integrate AI. | Required proposed architecture; not implemented. |
| D&D 5e adapter | Own system-specific actor, item, roll, effect, and data translation for the tested compatibility baseline. | Move general permissions, saves, persistence, or campaign authority into system paths. | Required proposed architecture; not implemented. |
| Client-neutral API | Version the contract for identity, permissions, campaigns, actions, feed projections, saves, synchronization, and diagnostics. | Embed Foundry tokens, canvas objects, hooks, chat cards, or D&D-specific paths in core concepts. | Required proposed boundary; exact API remains open. |
| Dungeon Manager application layer | Compose validated runtimes; coordinate permissions, AI, saves, adapters, disconnection policy, explicit reconciliation, and safe presentation models; enforce single host authority. | Override engine results, process new authoritative work or AI after host-authority loss, silently repair state, or trust client role labels. | Narrow runtime composition exists; general orchestration is not implemented. |
| Permission and identity authority | Validate authenticated session, DM/admin role, player assignments, speaker/actor grants, visibility, and knowledge projection on every submission. | Derive authority from client visibility, user prose, AI interpretation, or actor selection. | Approved proposed subsystem; not implemented. |
| Rules and domain engine | Validate commands, resolve mechanics, create results/events, and project authoritative facts independently of clients. | Depend on AI, Foundry, UI, tools, or presentation text; retry silently. | Implemented only for the bounded slice. |
| Persistence and save authority | Persist every authoritative change; own history, checkpoints, branches, migrations, and client-neutral save state; coordinate presentation snapshots and accepted reconciliation outcomes. | Accept narration or unreconciled provisional changes as fact, destructively replace a branch, guess through conflicts, or duplicate partial restores. | Durable event journal is implemented narrowly; general saves/branches are not. |
| AI orchestration/provider | Interpret intent before dispatch and narrate verified state under permission-filtered context; preserve stable pre-action request identity and event-bound post-resolution recovery. | Decide mechanics, grant permissions, reveal hidden knowledge, retry pre-action work after possible dispatch, or repeat authoritative work during narration retry. | Provider interfaces exist; general orchestration/recovery is not implemented. |
| Foundry client | Render maps, tokens, sheets, lighting, effects, and permitted feed/interface state. | Own rules, campaign facts, or the service connection for remote players. | First supported client; integration is not implemented. |
| Authenticated host/DM | Own the direct localhost service relationship; administer campaign settings, confirmation policy, world binding, assignments, providers, reconciliation, and recovery. | Expose credentials to players, promote another host automatically, accept provisional changes without reconciliation, or permit competing authority instances. | Approved proposed authority model; not implemented. |
| Participant | Control assigned character, OOC mode, own dice/interface/accessibility/filter settings, and explicitly granted actor capabilities. | Change another user's preference, select DM without authorization, control autonomous NPCs by default, or access hidden state. | Approved proposed authority model; not implemented. |
| Integrate AI | Legacy local module only; two macros may remain temporarily as historical reference. | Serve as dependency, runtime adapter, compatibility layer, or basis for new implementation. | Rejected; still pending disablement in `bonkers` outside this task. |

Exact adapter method boundaries, transport, pairing, and authentication remain
open. The ownership and security responsibilities above do not.

### 11.1 Compatibility and maintainability requirements

The target first supported Phase 2 baseline is Foundry VTT v14 Build 364 with
D&D 5e 5.3.3 and Integrate AI disabled before implementation begins. Connection
detects exact versions and capabilities before state-changing operations. The
project maintains an
explicit tested compatibility matrix and adapter contract tests so Foundry or
D&D updates fail visibly rather than leaking into the core.

When save schemas change, explicit save-data migrations preserve client-neutral
authority and applicable presentation snapshots. Unsupported or unknown
versions fail safely: where permission and schema safety permit, the interface
offers read-only inspection while refusing unsafe mutations. Fine-grained
support policy and release procedure remain open, but silent best-effort
mutation is not permitted.

## 12. Failure and recovery states

| Failure state | What the user sees | Did authoritative state change? | Safe actions and retry rule | Duplicate prevention and safe diagnostics |
|---|---|---|---|---|
| Foundry not running | The embedded sidebar/Manager and native Foundry surfaces are unavailable, but the client-independent engine remains available for tests and diagnostics. | No, solely from Foundry absence. | Start Foundry, open the explicitly intended linked world, reconnect, and synchronize. No companion window is provided or necessary. | No action replay; show safe component/version/time evidence after reconnect. |
| Individual player client connection lost while host authority remains | Only that player's view becomes stale; their character, permissions, pending input, and reconnectable feed position remain assigned while authorized host/other-player activity continues. | Unknown only for that player's in-flight input. | Reconnect the same identity and restore permitted state/feed position. | Verify the participant's in-flight outcome before retry; never reassign the character automatically or disclose hidden backlog. |
| Foundry presentation/module connection unavailable while authority remains | The affected embedded surfaces show **Reconnecting** or become unavailable; authoritative state and pending inputs remain preserved. Native Foundry viewing, navigation, and chat may remain available if Foundry itself is open. | No solely from presentation loss; an in-flight client-dependent outcome may require verification. | Pause actions requiring that client. Continue genuinely client-independent processing only while authenticated host authority and synchronization remain valid. Reconnect and synchronize before client-dependent input resumes. | Preserve request/event IDs; do not infer presentation success from engine success or bypass a required client. |
| Authenticated host/DM authority or service connection lost | All Dungeon Manager clients show **Host disconnected**; all new authoritative actions and AI processing pause. Native viewing, navigation, chat, and other non-authoritative Foundry activity may remain available. | Existing committed state is preserved; in-flight outcomes require verification. Native state-changing actions are not authoritative. | Reconnect the authenticated host, reconcile any captured provisional changes, and synchronize before resuming. No automatic promotion. | Preserve IDs/pending inputs; capture a state-changing native action with authenticated source, target, ordering, and payload for reconciliation or prevent/clearly refuse it; reject competing authority and blind retry. |
| Provisional offline Foundry change captured during host-authority loss | Authorized users see **Reconciliation required** with sanitized source, target, order, and scope. | Not yet; provisional capture is not authoritative history. | After authenticated host reconnection, explicitly accept, reject, or otherwise reconcile it according to the future reconciliation interface; resume authoritative processing only after all required reconciliation and synchronization succeed. | Stable provisional identity and ordering prevent silent promotion or duplicate application; exact capture and reconciliation mechanisms remain open. |
| Unsupported Foundry or D&D version | **Incompatible** with observed and supported versions; prefer permission-safe read-only inspection when safe, while refusing state changes. | No. | Open a supported world/version or update through a separately tested compatibility release. | Capability negotiation runs before mutation; show version metadata only. |
| No world selected | The compact sidebar remains startup-gated with **No Dungeon Manager world confirmed**; the expanded Manager shows discovery and selection. | No. | Explicitly confirm the current world or select another discovered world and perform any required Foundry world change manually. | No implicit binding; show no guessed world. |
| Open world does not match campaign link | **Wrong linked world — state-changing actions blocked** with expected/observed identities. | No. | Open the correct world manually or begin an authorized rebind with compatibility checks, safety checkpoint, and confirmation. | Never switch or rebind silently. |
| Selected world unavailable | The compact sidebar remains locked; the expanded Manager retains the selected ID/title with **Unavailable**. | No Dungeon Manager fact changes solely from absence. | Clear selection, retry discovery, or select another world explicitly. | Do not fall back to another world or switch Foundry silently; show sanitized availability reason. |
| Integrate AI still enabled in local development world | Legacy local-setup warning in DM Diagnostics; Dungeon Manager does not route through it. | No. | Disable it before Phase 2 implementation in a separate authorized Foundry task. | Never depend on, enable, disable, or invoke it automatically. |
| Pairing invalid or expired | **Offline** or pairing-required status with no state-changing controls. | No solely from pairing failure. | Authenticated host performs deliberate one-time re-pairing. | No credentials in diagnostics; reject remote exposure by default. |
| Dungeon Manager service unavailable | Sidebar is **Offline** and Dungeon Manager controls become read-only; native Foundry viewing, navigation, and chat remain usable when Foundry is open. For an active campaign, this is host-authority loss. | Unknown for an in-flight request; existing state is preserved. | Apply the host-authority-loss rules above: reconnect, verify durable state, reconcile captured provisional changes, and synchronize before resubmission or authoritative processing. | Preserve command ID and pending inputs, lock duplicate submit, and reject competing authority. |
| AI provider/model unavailable before dispatch | The immutable request remains **Interpretation failed — no action dispatched** only if zero authoritative side effects are proven. | No tool, command, authoritative event, or authoritative persistence occurred. Diagnostic attempt records are non-authoritative. | Retry the same input and context under the stable request identity only while pre-dispatch; then apply normal confirmation and execute at most once. If any work may have occurred, use outcome-unknown recovery instead. | Verify all four zero-side-effect conditions; retain attempt diagnostics and stable request/dispatch identity. |
| AI provider/model unavailable after verified mechanics | Mechanics remain verified while narration is delayed/failed. | Yes, the same durable mechanical event already exists; narration failure changes no mechanics. | DM may reconstruct/reuse that event's eligible narration packet, retry with another configured provider/model, or narrate manually. | Wording may change; never invoke tools or rerun a command, roll, damage, movement, effect, persistence event, or any state change. |
| Invalid AI tool request | **Tool request malformed — nothing executed**. | No tool execution and no engine event. | Edit and submit a new user request, or retry the identical interpretation only through the proven pre-action retry path. | Parser accepts one whole response only; show parse category, not hidden prompt. |
| Unauthorized speaker, actor, setting, or feed request | Concise **Not permitted** notice; the requested identity/control/data is absent or disabled without leaking why when sensitive. | No. | Use an assigned identity or ask the DM for an explicit scoped grant. | Server validates session identity and current permissions; client visibility never authorizes. |
| Tool execution rejected | Unknown tool or invalid arguments are displayed as rejected; tool failure is displayed as outcome uncertain when side effects cannot be excluded. | No engine event; external tool side effects depend on the tool result. | Unknown/invalid arguments may be corrected; `tool_failure` must not be blindly retried. | Tool call executes at most once; show tool name, typed status, and sanitized error. |
| Rules resolution failure | **No authoritative event created** with safe reason. | No for controlled eventless failures. | Correct input or choose a declared-safe new attempt. | Keep attempt ID/history; do not reinterpret failure as a miss or other outcome. |
| Manual dice timeout or invalid submission | Pending prompt remains or expires as UI-local; invalid field is highlighted. | No while the controlled round remains incomplete. | Re-enter valid natural face; cancel UI-local pending input; start a safe new command attempt if needed. | Disable duplicate submit; show roll ID, expression, range, and safe validation reason. |
| Persistence failure | Distinguish **commit not confirmed** from **commit confirmed; local synchronization failed**. | No local/projected change when durable commit failed; yes when durable commit was confirmed. | For unconfirmed failure, inspect status before a new attempt. For confirmed commit, rehydrate/recover projection; do not repeat action. | Event/command IDs and tails prevent blind retry; never show raw SQLite errors. |
| State desynchronization | Prominent **Authoritative history and current view disagree — actions blocked**. | Durable state may already have changed. | Rehydrate or use separately implemented recovery; keep dispatch disabled. | Compare journal identity/tails; do not append, reroll, or narrate while unhealthy. |
| Restore conflicts with current scene | Restore preview reports incompatible, missing, deleted, or conflicting content and enters reconciliation. | Safety checkpoint may have been created; active state is not guessed or silently overwritten. | Authorized DM resolves conflicts, cancels, or retries restoration idempotently. | Stable source IDs prevent duplicate tokens, encounters, and effects. |
| Partial restoration | **Restoration incomplete — reconciliation required** with completed/pending components. | Some presentation changes may exist; authoritative branch/checkpoint remains identified. | Retry the same restoration identity after reconciliation. | Idempotency prevents duplicate tokens, encounters, effects, or repeated state replacement. |
| Narration failure after successful resolution | Verified mechanics and **Saved** remain; narration shows unavailable. | Yes: the action event remains authoritative. | DM reconstructs/reuses the same event-derived eligible packet, retries with another configured provider/model, supplies narration manually, or dismisses. | Preserve event ID/sequence and idempotency identity; never invoke tools or repeat commands, rolls, damage, movement, effects, persistence events, or other state changes. |
| Restart during a pending action | On resume, show either no event, a reconstructed committed event, or unresolved health—not an assumed outcome. | Depends on durable history. | Hydrate first. Re-request incomplete manual input only when no event exists; otherwise show the reconstructed result. | Use prior command/event IDs when available; never reroll or redispatch merely because UI state was lost. |
| Competing Dungeon Manager authority | **Campaign already controlled by another authenticated instance**; state changes blocked. | No new change from the rejected instance. | End or transfer authority deliberately with secure re-pairing. | Lease/fencing details remain open, but simultaneous authority is forbidden. |

Diagnostic presentation may include typed status, safe reason code, component,
world/session ID, command ID, event ID/sequence, journal identity/tails,
compatibility versions, and timestamps. It must omit credentials, authentication
material, cookies, raw exceptions or tracebacks, private prompts, hidden
payloads, storage internals, and unrelated paths.

## 13. Low-fidelity wireframes

These wireframes communicate hierarchy only. They do not prescribe a frontend
framework, window toolkit, Foundry API, or transport.

### 13.1 World and session selection

```text
+ Dungeon Manager launcher --------------------------------------------------+
| Service: Connected | Foundry 14.364 | dnd5e 5.3.3 | Host: authenticated  |
| Open world: Bonkers [bonkers] | Linked campaign: Goblin Road              |
| LOCAL DEVELOPMENT TARGET | Legacy warning: Integrate AI still enabled     |
+ Campaign / branch / session ----------------------------------------------+
| Campaign: Goblin Road      Branch: main      Last checkpoint: cp-0042     |
| No campaign state has been resumed or changed.                            |
|                                                                            |
| [Resume session 12] [Start new session] [Load checkpoint...]              |
| [Choose another explicit world/campaign binding] [Diagnostics]            |
| Dungeon Manager never switches Foundry worlds or resumes silently.        |
+----------------------------------------------------------------------------+
```

### 13.2 Compact sidebar and Foundry tabletop

```text
+ Foundry tabletop ----------------------+ Dungeon Manager unified feed ----+
| Map, tokens, sheets, lighting, effects | Campaign: Goblin Road            |
|                                        | Branch: main | Session: 12       |
| Foundry presents; it does not decide.  | Base/latest checkpoint: cp-0042  |
|                                        | World: <ID> | Connected | Sync   |
|                                        | [All] [Chat] [Rolls] [System]    |
|                                        +----------------------------------+
|                                        | PLAYER — Nekria                  |
|                                        | "I attack with my rapier."       |
|                                        | INTERPRETATION — pending, not fact|
|                                        | Nekria -> rapier -> goblin-1     |
|                                        |                                  |
|                                        | FOUNDRY ROLL — PUBLIC            |
|                                        | d20 10 + 5 = 15                  |
|                                        | VERIFIED MECHANICS — SAVED       |
|                                        | Hit; damage 5; HP 7 -> 2         |
|                                        |                                  |
|                                        | AI NARRATION — NON-AUTHORITATIVE |
|                                        | "Nekria's rapier..."             |
|                                        | SYNC NOTICE — tabletop current   |
|                                        +----------------------------------+
|                                        | Speak [Nekria v]  Act [Nekria]   |
|                                        | [Write what you do or say...]    |
|                                        | [Native chat] [Manager] [Submit] |
+----------------------------------------+----------------------------------+
```

### 13.3 Manual dice prompt

```text
+ Dungeon Manager sidebar — Manual roll ------------------------------------+
| Stage 3 of 4: Nekria rapier attack                                        |
| Roll: 1d20 + 5    Roll ID: attack-...                                     |
| Enter the natural d20 face (1-20), not the modified total.                |
| Visibility: Public | Your default: Manual                                 |
|                                                                           |
| Natural face: [    ]    Total preview: --                                 |
| [Submit face] [Roll automatically once] [Cancel pending input]            |
| [ ] Save the selected mode as my default                                  |
|                                                                           |
| No combat event or HP change exists until the complete round succeeds.    |
+---------------------------------------------------------------------------+
```

### 13.4 Automatic dice progress

```text
+ Dungeon Manager sidebar — Automatic resolution ---------------------------+
| [✓] Nekria initiative       3 + 3 = 6    engine automatic                |
| [✓] Goblin initiative      18 + 2 = 20   engine automatic                |
| [>] Rapier attack          processing...                                 |
| [ ] Damage                 waits for verified hit                        |
|                                                                           |
| Authoritative state: unchanged | Composer locked | Do not resubmit        |
+---------------------------------------------------------------------------+
```

For a hidden roll, the affected player's wireframe contains no roll card,
placeholder, progress indicator, notification, or changed layout that reveals
the request. An authorized DM view may show the automatic roll and result;
other participants receive only the permitted consequence or no entry.

### 13.5 Recoverable failure state

```text
+ Dungeon Manager sidebar — Recovery required ------------------------------+
| STATE DESYNCHRONIZED                                                      |
| Durable history may contain the action; the Foundry view did not sync.    |
| The action will not be repeated.                                          |
|                                                                           |
| Command: round-...   Event: ...   Durable: 2   Projected: 1               |
| Safe action: inspect and rehydrate from authoritative history.            |
|                                                                           |
| [Recheck] [Open expanded Manager diagnostics]                             |
| Input, dice, tools, and narration are disabled until synchronized.        |
+---------------------------------------------------------------------------+
```

### 13.6 Expanded Manager navigation

```text
+ Dungeon Manager — Expanded Manager ---------------------------------------+
| [Return to sidebar/tabletop]  Campaign: Goblin Road                        |
| World: <ID> | Branch: main | Session: 12                                   |
| Base/latest checkpoint: cp-0042                                            |
+ Navigation -------------------+ Selected section -------------------------+
| Session                       | Journal                                  |
| Character                     | Player Journal / objectives / leads      |
| Journal                       | notes / permitted relationships          |
| World                         | Only authorized player-visible entries   |
| Settings                      | with source and provenance when supported|
| Diagnostics                   |                                          |
|                               | Hidden campaign information is excluded. |
+-------------------------------+------------------------------------------+
```

### 13.7 Checkpoint load and branching

```text
+ Load checkpoint -----------------------------------------------------------+
| Campaign: Goblin Road | Branch: main | World: Bonkers [bonkers] LOCAL DEV|
| Selected: "Before the ambush" (cp-0017)                                   |
| Loading older state creates a NEW BRANCH. main remains recoverable.        |
| Safety checkpoint to create: safety-before-load-...                        |
| Scene impact: active scene differs — reconciliation may be required.       |
|                                                                            |
| [Cancel] [Review restoration details] [Confirm load on new branch]         |
+----------------------------------------------------------------------------+
```

### 13.8 Host disconnection

```text
+ Dungeon Manager unified feed ---------------------------------------------+
| HOST DISCONNECTED | Reconnecting                                          |
| New authoritative actions and AI processing are paused.                    |
| Current state and pending inputs are preserved.                            |
| Native viewing/navigation/chat may continue; it is non-authoritative.       |
| Native state change: capture provisionally for reconciliation or refuse.    |
| No participant will be promoted automatically.                             |
| Reconnect -> reconcile -> synchronize before authority resumes.             |
|                                                                            |
| [Manual reconnect] [Diagnostics] [Open native chat]                        |
+----------------------------------------------------------------------------+
```

An individual player-client disconnection instead makes only that
participant's input/presentation stale while authenticated host authority and
other authorized play continue. A presentation/module disconnection while host
authority remains pauses actions that need that client; genuinely
client-independent processing may continue only while authority and
synchronization remain valid.

### 13.9 Speaker and actor permissions

```text
+ Composer identity ---------------------------------------------------------+
| Authenticated user: Player 1                                               |
| Speak as: [Nekria v]  Available: Nekria, OOC, Pip (speech-only grant)      |
| Act as:   [Nekria v]  Pip: unavailable for actions                         |
| DM: unavailable — authenticated DM role required                           |
| Selecting Pip does not reveal Pip's private knowledge.                     |
|                                                                            |
| [Write what you do or say...]                                  [Submit]    |
+----------------------------------------------------------------------------+
```

### 13.10 Settings authority

```text
+ Settings ------------------------------------------------------------------+
| Personal (Player 1)                 Campaign (DM/admin only)                |
| Dice default: [Manual v]            Provider/model: [hidden / unavailable] |
| Interface / accessibility           Ruleset: [view only]                   |
| Notifications / feed filters        World binding: [view only]             |
| Confirmation policy: [view only]    DM/admin may enable stricter policy    |
|                                                                            |
| Campaign changes are validated and recorded in authoritative audit history.|
+----------------------------------------------------------------------------+
```

## 14. Acceptance criteria

These are testable criteria for a future implementation of this draft. They do
not claim the interface currently exists.

1. **UI-AC-01 — Neutral startup:** opening a linked Foundry world attempts
   connection but does not resume or mutate campaign state; the launcher
   requires an explicit **Resume**, **Start new session**, or **Load
   checkpoint** choice. `bonkers` is labelled only as this machine's local
   development target.
2. **UI-AC-02 — Character selection:** the controlled session offers Nekria as
   the only implemented selectable player character and marks selection complete
   only after its durable event is synchronized.
3. **UI-AC-03 — Speaker-role authorization:** assigned character, OOC,
   authenticated DM, and expressly assigned actor/NPC modes are validated
   server-side on every submission. OOC grants no DM authority; players cannot
   select DM, another player's character, or an unassigned actor.
4. **UI-AC-04 — Ordinary conversation:** a no-tool provider response is shown
   as non-authoritative presentation and creates no combat or campaign event.
   The test notes that this bounded provider path is currently separate from the
   controlled engine.
5. **UI-AC-05 — Tool-requiring action:** one valid complete tool request invokes
   at most one registered tool once, displays typed execution status, and does
   not masquerade as an authoritative combat event.
6. **UI-AC-06 — Manual dice:** a participant may manually answer eligible
   visible requests only for their assigned actor/role; invalid or incomplete
   input creates no event, and one participant cannot change another's mode.
7. **UI-AC-07 — Automatic and hidden dice:** automatic mode records provenance
   and produces no partial event on failure. In every Phase 2 player-facing
   workflow, a hidden or secret roll is automatic and produces no prompt,
   notification, timing change, reserved layout, or other disclosure that it
   occurred, regardless of the player's manual preference. Any later DM-only
   hidden-adjudication mechanism remains outside this baseline and must preserve
   zero player disclosure.
8. **UI-AC-08 — Verified hit and damage:** natural face, modifier, total, hit,
   conditional damage, HP transition, defeat state, final round, and active
   participant match the synchronized aggregate event and projection.
9. **UI-AC-09 — Narration ordering:** narration remains absent before durable
   commit and synchronized projection, then appears in a visually distinct
   non-authoritative card bound to the source event.
10. **UI-AC-10 — Persistence:** the UI distinguishes dispatch, durable commit,
    local publication, projection, and synchronization; it never labels an
    eventless or unconfirmed result as saved.
11. **UI-AC-11 — Restart reproduction:** after discarding the original runtime,
    resume reconstructs the identical authoritative event and state without
    rolling, dispatching, appending, executing a tool, invoking a provider,
    repairing, or replaying narration.
12. **UI-AC-12 — Separate provider-recovery classes:** a failed pre-action
    interpretation can be retried only under the same stable request identity,
    immutable input, authenticated identity, actor assignment, and context
    reference while pre-dispatch checks prove that no tool, authoritative
    command, authoritative event, or authoritative persistence occurred.
    Diagnostic interpretation-attempt records remain non-authoritative; all
    attempts can produce at most one eventual authoritative action through the
    normal confirmation/execution path. Separately, after verified mechanics,
    the DM may reconstruct or reuse the same eligible packet from the same
    durable event, retry narration with another configured provider/model, or
    narrate manually. That retry may change wording only and cannot invoke tools
    or repeat commands, rolls, damage, movement, effects, persistence events, or
    any authoritative change.
13. **UI-AC-13 — Failure recovery without duplicate change:** connection loss,
    timeout, persistence uncertainty, desynchronization, and restart lock
    resubmission until durable state is known; recovery never applies the
    controlled round twice.
14. **UI-AC-14 — Hidden-information separation:** player views contain only
    authorized player-visible context; switching speaker cannot reveal hidden
    facts, private NPC knowledge, secret diagnostics, prompts, or credentials.
15. **UI-AC-15 — Proposed versus implemented:** every unimplemented control,
    service, Foundry behavior, general actor, narration retry, and later
    candidate is labelled proposed or unavailable, while the embedded
    presentation direction is recorded consistently as approved for this draft.
16. **UI-AC-16 — Embedded ordinary-play surface:** while Dungeon Manager is
    active, the compact Dungeon Manager sidebar replaces or takes over normal
    Foundry chat with a unified permission-filtered gameplay feed, without
    requiring a separate companion window; native chat remains accessible as a
    fallback.
17. **UI-AC-17 — Expanded Manager:** the compact sidebar opens an expanded view
    inside Foundry with permission-aware **Session**, **Character**,
    **Journal**, **World**, **Settings**, and **Diagnostics** sections.
18. **UI-AC-18 — Client-independent core:** engine, AI orchestration, campaign
    state, saves, permissions, and history run without Foundry; Foundry-specific
    objects remain in the dedicated Foundry and D&D 5e adapters; Integrate AI is
    never invoked.
19. **UI-AC-19 — Unified feed classification:** permitted player/DM/OOC
    messages, AI narration, Foundry rolls/cards, mechanics, actions, requests,
    resolutions, and important notices appear in one deduplicated feed with
    stable source identity; routine chatter is filtered by default.
20. **UI-AC-20 — Visibility integrity:** public, private, blind, and fully
    hidden events retain their visibility. Passing through Dungeon Manager never
    increases an event's audience, and mechanics remain visually distinct from
    AI narration.
21. **UI-AC-21 — Dice preference scope:** each player controls only their own
    assigned-character mode; the DM has an independent DM-controlled-roll
    preference; changes affect unresolved eligible/future rolls only and never
    reroll a completed result.
22. **UI-AC-22 — Visible roll override:** a visible prompt may apply a one-time
    manual/automatic override and optionally save that participant's default
    without changing visibility or another participant's preference.
23. **UI-AC-23 — NPC autonomy and grants:** NPCs, companions, and AI party
    members remain AI-controlled by default. **Speak as** and **Act as** grants
    are separate, scoped, revocable, and pause AI control only for the granted
    actor and duration.
24. **UI-AC-24 — Campaign/world binding:** one campaign links explicitly to one
    Foundry world and may contain multiple sessions/saves. Opening or selecting
    a world never silently resumes, switches, or rebinds it.
25. **UI-AC-25 — Complete save content and reconstruction comparison:** for
    every applicable field in §8.5, a save captures authoritative campaign state
    and separately identifiable Foundry presentation state without prescribing
    a snapshot schema. Test fixtures cover active and prepared scenes and the
    current active scene; token identity and actor links; token coordinates,
    elevation, rotation, size, visibility, disposition, and relevant control
    state; HP, resources, conditions, effects, and actor/token state;
    combatants, initiative, round, and active turn; doors, lights, templates,
    fog/exploration, and gameplay-relevant scene changes; journals, inventory,
    relationships, objectives, known leads, world state, clocks, events, and
    authoritative history; and direct Foundry changes validly synchronized into
    authoritative state. After restoration and synchronization, a comparison
    against the saved applicable state confirms that the reconstructed Foundry
    tabletop matches every captured field.
26. **UI-AC-26 — Explicit restoration:** load confirms the linked world, creates
    a safety checkpoint, loads the checkpoint on a new branch, restores scenes,
    tokens, and encounters, and declares success only after synchronization.
27. **UI-AC-27 — Reconciliation and idempotency:** incompatible current scenes
    and missing/deleted/conflicting content enter reconciliation; retrying a
    partial restore never duplicates tokens, encounters, or effects.
28. **UI-AC-28 — Persistence cadence:** every authoritative state change is
    persisted, periodic recovery checkpoints are created, and deliberate manual
    named saves remain available.
29. **UI-AC-29 — Non-destructive branching:** loading older state requires
    confirmation and begins a new timeline branch; original later progress
    remains recoverable, new actions affect only the active branch, and branch
    deletion is a separate deliberate operation.
30. **UI-AC-30 — Active identity:** the compact sidebar header and expanded
    Manager header clearly show the active campaign, linked world, branch,
    session, and active base/latest checkpoint identifier without prescribing
    exact styling or controls.
31. **UI-AC-31 — Compatibility safety:** connection detects versions and
    capabilities against an explicit tested matrix; unknown/unsupported
    versions refuse unsafe mutations and permit read-only inspection when safe.
    Adapter contract tests and save-data migrations are required release
    evidence.
32. **UI-AC-32 — Dedicated module:** the Dungeon Manager Foundry module owns
    sidebar, feed, permissions mediation, connection, synchronization,
    restoration, and capability negotiation; no new code depends on Integrate
    AI or its two legacy macros.
33. **UI-AC-33 — Pairing, status, and default exposure:** after one-time secure
    world/user pairing, the host reconnects automatically through host-local/
    loopback access. Under untouched default configuration, listener/boundary
    inspection and a remote-client connection attempt confirm that the
    privileged service accepts loopback clients but neither listens for nor
    accepts remote/network clients. Enabling any future remote exposure requires
    a deliberate authorized configuration action and does not occur during
    default startup. The UI distinguishes **Connected**, **Reconnecting**,
    **Incompatible**, and **Offline** and provides reconnect/Diagnostics; exact
    transport, configuration format, and authentication remain deferred.
34. **UI-AC-34 — Multiplayer routing:** only the host/DM machine connects
    directly to the service. Remote browsers use authenticated Foundry/module
    routing and never connect to their own localhost.
35. **UI-AC-35 — Settings authority:** DM/admin-only campaign/provider/rules/
    binding/credential controls and player-only personal dice/interface/
    accessibility/filter controls are enforced server-side; campaign-changing
    settings are validated and audited.
36. **UI-AC-36 — Default and stricter confirmation policies:** under the default
    policy, a clear ordinary action proceeds after briefly displaying actionable
    interpretation, while ambiguity, unusual consequence, conflict, overwrite,
    restore, reconcile, migrate, rebind, or other state replacement always
    requires confirmation. When an authenticated DM/admin enables a stricter
    campaign/testing policy, the same ordinary-action category can be
    confirmation-gated. The stricter policy can add but never remove mandatory
    gates or permissions; its active state is visible to authorized users, and
    changes are validated and recorded in authoritative audit history. An
    ordinary player cannot alter or bypass either policy through UI selection or
    prompt text. Hidden reasoning is never shown.
37. **UI-AC-37 — Join and reconnect filtering:** joining/reconnecting restores
    identity, assignment, personal dice mode, permissions, and visible feed
    position without disclosing prior concealed rolls, private journals, hidden
    messages, or secret NPC knowledge.
38. **UI-AC-38 — Individual player-client loss:** with authenticated host
    authority and synchronization healthy, disconnecting one player client stops
    only that participant's inputs/presentation, preserves their pending input,
    identity, assignment, settings, and feed position, and does not halt other
    authorized play or reassign the character.
39. **UI-AC-39 — Presentation/module loss with authority retained:** making the
    Foundry presentation/module connection unavailable preserves authoritative
    state and pending inputs and pauses every action that requires that client.
    Genuinely client-independent processing continues only when authenticated
    host authority and synchronization remain valid. When Foundry itself remains
    open, non-authoritative native viewing, navigation, and chat continue;
    client-dependent input resumes only after successful reconnection and
    synchronization.
40. **UI-AC-40 — Host-authority loss and provisional changes:** losing the
    authenticated host/DM authority or its Dungeon Manager connection pauses all
    new authoritative actions and AI processing, preserves state/pending inputs,
    allows only non-authoritative native Foundry activity, and never promotes
    another participant. A native action that would change authoritative state
    is either clearly refused or captured with stable provisional identity,
    authenticated source/target, ordering, and original payload; it never
    silently becomes authoritative. Captured changes require explicit
    reconciliation after authenticated host reconnection, and authoritative
    processing resumes only after required reconciliation and synchronization
    succeed.
41. **UI-AC-41 — Single authority:** two Dungeon Manager instances cannot hold
    simultaneous authority over one active campaign; future transfer requires
    deliberate authorization and secure re-pairing.
42. **UI-AC-42 — No implementation claim:** every requirement added by this
    review remains labelled proposed/not implemented, and exact UI styling,
    hooks, transport, schemas, pairing, host transfer, adapter methods,
    reconciliation UI/provisional capture, compatibility release policy,
    snapshot partitioning, and sequencing remain open.

## 15. Traceability

### 15.1 Requirement traceability

| Required behavior or boundary | Current source | Traceability note |
|---|---|---|
| Player choice, engine authority, Foundry presentation | [GDD — Internal Design Mantra](../../GDD.md#internal-design-mantra), [Player Agency](../../GDD.md#player-agency) | Accepted product philosophy. The interface and Foundry integration remain proposed. |
| Embedded sidebar and expanded Manager | [GDD — Internal Design Mantra](../../GDD.md#internal-design-mantra), [Architecture — Status and scope](../../ARCHITECTURE.md#status-and-scope), [Project Status — Known limitations](../../PROJECT_STATUS.md#known-limitations) | The embedded presentation direction is approved for this draft. The sources establish Foundry as presentation and confirm that UI/integration are not implemented; they do not choose a Foundry API or transport. |
| Unified gameplay feed and visibility | [GDD — Perspective Integrity](../../GDD.md#perspective-integrity), [Information Should Be Earned](../../GDD.md#information-should-be-earned) | Approved feed behavior applies those principles to Foundry event classification; adapter/hooks remain unimplemented. |
| Speaker, identity, assignment, and NPC autonomy | [GDD — Player Agency](../../GDD.md#player-agency), [NPC Independence](../../GDD.md#npc-independence), [Perspective Integrity](../../GDD.md#perspective-integrity) | Reviewed permissions and control behavior are approved proposed requirements; general authorization is not implemented. |
| Local ownership, durable facts, and recovery | [GDD — Local Ownership](../../GDD.md#local-ownership), [Recovery Over Perfection](../../GDD.md#recovery-over-perfection), [Architecture — Durable event authority and restart](../../ARCHITECTURE.md#durable-event-authority-and-restart) | Product principles plus narrow implemented durable journal/hydration behavior. |
| Fixed playable loop and dice stages | [First Playable GDD](../../FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md), [Controlled round runtime](../../dungeon_manager/controlled_round_runtime.py), [Dice](../../dungeon_manager/engine/dice.py) | Implemented only for the controlled fixture and attack. The proposed Phase 2 player workflow makes hidden rolls automatic with zero prompt or indirect disclosure; any later DM-only hidden adjudication remains outside the baseline. |
| Explicit campaign and character identities | [Architecture — Campaign runtime and fixture](../../ARCHITECTURE.md#campaign-runtime-and-fixture), [Campaign runtime](../../dungeon_manager/campaign_runtime.py) | Nekria is the only currently selectable player character. General identity selection is proposed. |
| Durable-before-memory action presentation | [Architecture — Durable event authority and restart](../../ARCHITECTURE.md#durable-event-authority-and-restart), [First-playable acceptance tests](../../dungeon_manager/engine/test_first_playable_acceptance.py) | Implemented publication ordering informs the proposed status hierarchy. |
| Manual and automatic acceptance journeys | [First-playable acceptance tests](../../dungeon_manager/engine/test_first_playable_acceptance.py), [Controlled-round tests](../../dungeon_manager/engine/test_controlled_round.py) | Two implemented headless journeys; wireframes and controls are proposed. |
| Separate pre-action interpretation and post-resolution narration recovery | [Architecture — Provider and AI tool boundary](../../ARCHITECTURE.md#provider-and-ai-tool-boundary), [Architecture — Verified AI DM narration boundary](../../ARCHITECTURE.md#verified-ai-dm-narration-boundary), [Verified narration boundary](../../dungeon_manager/verified_narration.py), [Narration provider](../../dungeon_manager/ai/narration_provider.py) | Pre-action retry is permitted only for one stable immutable request with proven zero tool/command/event/persistence side effects and at most one eventual dispatch. Post-resolution retry remains bound to one existing durable event and cannot repeat mechanics. Both coordinators are proposed. |
| Ordinary response and one bounded tool call | [Architecture — Provider and AI tool boundary](../../ARCHITECTURE.md#provider-and-ai-tool-boundary), [ToolAgent](../../dungeon_manager/ai/tool_agent.py), [Tool parser](../../dungeon_manager/ai/tool_call_parser.py), [Tool executor](../../dungeon_manager/ai/tool_executor.py) | Implemented separate character-tool path; not connected to combat, verified narration, or authoritative engine state. |
| Completed slice and unimplemented UI/Foundry | [Project Plan — Current boundary](../../PROJECT_PLAN.md#current-boundary), [Project Status — Known limitations](../../PROJECT_STATUS.md#known-limitations) | Confirms this document is a proposed design, not status or Phase 2 implementation planning. |
| Verified local development world | This draft's local Foundry inspection input; [Architecture — State ownership](../../ARCHITECTURE.md#state-ownership) | `bonkers` is recorded only as the current machine's empty development target. Foundry has no implemented ownership or synchronization path, and the product still requires explicit world selection. |
| Player-visible journal and filtered state | [GDD — Perspective Integrity](../../GDD.md#perspective-integrity), [RI-001 — Player Journal](../research/RI-001.md#3--player-journal) | The Manager Journal is approved proposed behavior; provenance-aware projection implementation remains future work. |
| Simulation before narration | [GDD — Consistency Over Cleverness](../../GDD.md#consistency-over-cleverness), [RI-001 — Simulation Before Narration](../research/RI-001.md#15--simulation-before-narration), [Architecture — Verified AI DM narration boundary](../../ARCHITECTURE.md#verified-ai-dm-narration-boundary) | Narrow event-derived narration is implemented; general simulation and narration are not. |
| Campaign/world binding, startup, and explicit restore | [GDD — Local Ownership](../../GDD.md#local-ownership), [Recovery Over Perfection](../../GDD.md#recovery-over-perfection), [Architecture — State ownership](../../ARCHITECTURE.md#state-ownership) | Reviewed binding/startup behavior is approved; general binding and restoration are not implemented. |
| Complete saves, checkpoints, and branching | [GDD — Trust in the World](../../GDD.md#trust-in-the-world), [Trust in Consequences](../../GDD.md#trust-in-consequences), [Local Ownership](../../GDD.md#local-ownership), [Architecture — Durable event authority and restart](../../ARCHITECTURE.md#durable-event-authority-and-restart) | Current durable history proves a narrow foundation; complete applicable §8.5 tabletop reconstruction with field-by-field comparison, named saves, migrations, and branches are approved proposed requirements. Snapshot schema and partition remain open. |
| Dedicated adapters and client-independent core | [GDD — Internal Design Mantra](../../GDD.md#internal-design-mantra), [Architecture — Implemented dependency direction](../../ARCHITECTURE.md#implemented-dependency-direction), [Architecture — State ownership](../../ARCHITECTURE.md#state-ownership) | Preserves current engine independence while adding approved proposed Foundry/D&D adapter boundaries. |
| Local pairing, default exposure, and remote-player routing | [GDD — Local Ownership](../../GDD.md#local-ownership), [Architecture — State ownership](../../ARCHITECTURE.md#state-ownership) | Loopback-only privileged service access is the observable default; remote players route through authenticated Foundry/module sessions. Exact transport, pairing, authentication, configuration, and any future authorized remote exposure remain open. |
| Multiplayer filtering and three disconnection boundaries | [GDD — Perspective Integrity](../../GDD.md#perspective-integrity), [Local Ownership](../../GDD.md#local-ownership), [Recovery Over Perfection](../../GDD.md#recovery-over-perfection) | Individual client loss, presentation/module loss with authority retained, and host-authority loss have distinct approved behavior. Native state-changing actions during host loss are refused or provisional until explicit reconciliation; no automatic promotion and single authority remain fixed while capture/reconciliation/host-transfer mechanisms stay open. |
| Settings authority, confirmation policy, and audit | [GDD — Local Ownership](../../GDD.md#local-ownership), [Trust in the Rules](../../GDD.md#trust-in-the-rules), [Perspective Integrity](../../GDD.md#perspective-integrity) | DM/admin and personal-setting boundaries are approved. Default confirmation behavior, additive authorized stricter policies, visibility, validation, and audit are proposed; general durable audit is not implemented. |
| Compatibility detection and migrations | [GDD — Consistency Over Cleverness](../../GDD.md#consistency-over-cleverness), [Recovery Over Perfection](../../GDD.md#recovery-over-perfection) | Foundry 14 Build 364 and D&D 5e 5.3.3 are the first baseline; matrix, contract tests, safe refusal, and migrations are proposed requirements. |

### 15.2 Current public-composition sequence

The interface journey is traceable to these current public boundaries:

1. `initialize_controlled_fixture(...)` for a new empty controlled local target;
2. `load_controlled_campaign_runtime(...)` for validation and hydration;
3. `CampaignRuntime.select_player_character(...)` for durable Nekria selection;
4. `compose_controlled_combat_domain(...)` for exact controlled-domain
   validation;
5. `ControlledRoundRuntime.resolve(...)` for staged manual or injected automatic
   resolution;
6. durable journal publication and synchronized world-state projection through
   the composed pipeline;
7. `VerifiedNarrationBoundary.narrate(...)` for one eligible transient
   narration attempt; and
8. a fresh `load_controlled_campaign_runtime(...)` for restart reconstruction.

The current code does not expose public APIs for general Foundry binding, world
discovery, permissions, actor assignment, saves/branches, tabletop restoration,
multiplayer routing, provider recovery, or player-knowledge projection. This
specification approves their product behavior without inventing exact APIs.

## 16. Remaining open implementation decisions

The approved product behavior above is fixed for this draft. The following
technical details remain deliberately open for the appropriate milestone:

1. exact sidebar controls and visual styling;
2. exact chat-takeover activation/deactivation lifecycle and Foundry hook
   strategy;
3. transport protocol and message schemas;
4. pairing and authentication implementation;
5. deliberate host-transfer protocol;
6. exact boundaries and method contracts among the client API, Foundry adapter,
   D&D 5e adapter, core, permissions, saves, and synchronization;
7. fine-grained compatibility policy, tested-matrix maintenance, and release
   process;
8. exact reconciliation interface and provisional offline-change capture
   mechanism for missing, deleted, conflicting, incompatible, or disconnected
   Foundry content;
9. which presentation details belong in client-specific snapshots rather than
   client-neutral authoritative state; and
10. implementation sequencing beyond the approved product behavior in this
    draft.

These open details may refine implementation but may not reintroduce a companion
window requirement, split routine gameplay into separate feeds, weaken
permissions or visibility, make Foundry authoritative, route every player to
localhost, make Integrate AI a dependency, restore destructively, promote a host
automatically, silently treat provisional native changes as authoritative, or
repeat authoritative work during AI recovery.
