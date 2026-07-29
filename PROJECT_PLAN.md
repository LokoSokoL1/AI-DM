# Dungeon Manager Project Plan

## Planning authority

The accepted product sequence is defined by [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md). The accepted Phase 2 interface behavior is defined by [LOW_FIDELITY_INTERFACE_SPEC_V1.md](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md). This plan reports progress and next planning work; it does not redefine product behavior.

## First Playable Vertical Slice

1. **Campaign Runtime and Controlled Fixture Foundation — completed and verified.**
   One explicit local campaign fixture can be initialized, validated, loaded, selected, durably journaled, projected, and hydrated without campaign discovery or general content tooling.

2. **Deterministic Dice Foundation — completed and verified.**
   Manual natural faces and injected automatic faces resolve through one provider-neutral primitive with immutable results, provenance, bounded input, and no partial result on failure.

3. **Minimal Combat Domain — completed and verified.**
   The static Nekria-versus-goblin fixture defines combatants, initiative modifiers, armor class, hit points, and Nekria's rapier without introducing a general rules system.

4. **Player Attack Resolution — completed and verified.**
   One controlled command resolves the frozen initiative-to-post-attack sequence, publishes one aggregate durable event, projects it atomically, and reconstructs it on restart without rerolling or inference.

5. **Verified AI DM Narration Boundary — completed and verified.**
   One immutable packet is derived from the exact durably committed and synchronized controlled-round event. A dedicated tool-free provider may return transient presentation text once; it cannot dispatch commands, mutate state, append events, or become evidence of game facts.

6. **Durable Complete-Round Restart Proof — completed and verified.**
   One completed controlled round is hydrated twice through genuinely fresh runtime composition from existing fixture files and the SQLite journal only. Durable facts and projected state agree exactly; dice, dispatch, append, narration, tools, retries, and repair do not occur during hydration.

7. **End-to-End First Playable Validation — completed and verified.**
   Two headless public-composition journeys prove staged manual and injected
   automatic dice through selection, one durable controlled round, projection,
   verified transient narration, shutdown, and fresh durable hydration.

## Phase 2 interface design baseline

The Phase 2 low-fidelity interface design baseline was formally accepted on
2026-07-29 from the exact draft with SHA-256
`21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3`.
Acceptance approves its product behavior and 42 acceptance criteria; it does not
implement the interface or Foundry integration. On 2026-07-29, the project owner
accepted D6 and D10 from its ten explicitly deferred implementation decisions.
The remaining eight decisions remain open. Future technical design and
implementation must conform to the baseline and accepted decisions or record an
explicit revision.

## Accepted Phase 2 decisions and bounded sequence

- **D6 — Core/client API/adapter/permission/save/sync boundaries — accepted.**
  Phase 2 follows a ports-and-adapters ownership direction: the deterministic
  engine remains the authoritative domain core, a client-neutral application
  layer coordinates authority-facing operations, and Foundry and D&D 5e remain
  dedicated edge adapters.
- **D10 — Implementation sequencing — accepted.**
  Phase 2 proceeds contract-first through bounded milestones. Accepting D10 does
  not permanently freeze the later sequence; any revision requires an explicit
  accepted decision.
- **M1 — Client-Neutral Authority and Operation Contracts — completed and
  verified.**
  M1 establishes only the minimum client-neutral authority and operation
  contracts needed to represent the existing controlled fixture and support the
  next bounded milestones. It keeps submission, mechanics, durable commitment,
  local publication, projection, synchronization, and transient presentation
  distinct; carries caller operation correlation separately from command/event
  identity; and exposes the fixture through one in-process headless façade.
  It does not finalize detailed contracts or behavior belonging to later
  permission, transport, Foundry, multiplayer, save, branch, snapshot, or
  reconciliation milestones.
- **M2 — Identity, Permission, Assignment and Visibility Core — provisional
  following milestone only.**
  M2 is not approved for implementation by this checkpoint and may be revised
  through an explicit accepted decision.

The other eight deferred implementation decisions remain open.

## Current boundary

All seven accepted slice milestones are complete. There is no unstarted
milestone in this frozen slice. The Phase 2 design baseline, D6, and D10 are
accepted. M1 is completed and verified within its minimum-contract constraint.
M2 is only the provisional following milestone and has not started. The
completed slice and M1 do not persist or replay narration, make audit and replay
safeguards durable, or implement permissions, transport, Foundry, multiplayer,
saves, branches, snapshots, restoration, synchronization adapters, or
reconciliation.

General D&D rules, goblin tactics, movement, spellcasting, Foundry control, UI, voice, campaign discovery, editors, migrations, repair, background work, and cross-process coordination remain outside the completed slice scope unless explicitly scheduled.

## Later roadmap

With the frozen slice validated and the Phase 2 low-fidelity interface baseline
accepted, D6 and D10 define the accepted ownership direction and bounded
contract-first sequence. M1 is completed; M2 is only the provisional following
milestone and requires a separately accepted bounded implementation task before
it starts. Broader rules coverage, richer campaign/world systems, additional
local providers, voice interaction, and advanced automation remain future
directions, not current implementation commitments.
