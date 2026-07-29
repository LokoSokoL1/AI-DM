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
implement the interface or Foundry integration. Its ten explicitly deferred
implementation decisions remain open. Future technical design and implementation
must conform to the baseline or record an explicit revision.

## Current boundary

All seven accepted slice milestones are complete. There is no unstarted
milestone in this frozen slice. The Phase 2 design baseline is accepted, but no
Phase 2 implementation milestone has been accepted or started. The next action
is a separate bounded Phase 2 technical-planning task that defines implementation
sequence and resolves deferred mechanisms only through explicit decisions. The
completed acceptance proof does not persist or replay narration or make audit
and replay safeguards durable.

General D&D rules, goblin tactics, movement, spellcasting, Foundry control, UI, voice, campaign discovery, editors, migrations, repair, background work, and cross-process coordination remain outside the completed slice scope unless explicitly scheduled.

## Later roadmap

With the frozen slice validated and the Phase 2 low-fidelity interface baseline
accepted, the next bounded technical-planning task may schedule conforming
Foundry VTT presentation and control, management interfaces, and supporting
systems. Broader rules coverage, richer campaign/world systems, additional local
providers, voice interaction, and advanced automation remain future directions,
not current implementation commitments.
