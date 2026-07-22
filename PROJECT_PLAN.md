# Dungeon Manager Project Plan

## Planning authority

The accepted product sequence is defined by [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md). This plan reports progress against that sequence; it does not redefine product behavior.

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

7. **End-to-End First Playable Validation — next, unstarted.**

## Current boundary

The exact next milestone is **Milestone 7 — End-to-End First Playable Validation**. It has not started. Milestone 6 does not persist narration, replay it on restart, make audit or replay safeguards durable, or begin Milestone 7.

General D&D rules, goblin tactics, movement, spellcasting, Foundry control, UI, voice, campaign discovery, editors, migrations, repair, background work, and cross-process coordination remain outside the completed slice scope unless explicitly scheduled.

## Later roadmap

After the frozen slice is validated end to end, later planning may address broader rules coverage, richer campaign/world systems, Foundry VTT presentation and control, management interfaces, additional local providers, voice interaction, and advanced automation. Those items are future directions, not current implementation commitments.
