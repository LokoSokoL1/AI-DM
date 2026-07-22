# Dungeon Manager Project Status

## Checkpoint

- Branch: develop
- Checkpoint scope: the accumulated First Playable Vertical Slice implementation through Milestone 4, plus reconciled canonical documentation
- Completed slice milestone: **Milestone 4 — Player Attack Resolution**
- Exact next unstarted milestone: **Milestone 5 — Verified AI DM Narration Boundary**

No Milestone 5 implementation, AI combat narration, UI, or Foundry integration is part of this checkpoint.

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

### First Playable Vertical Slice Milestones 1–4

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

## Verified milestone coverage

Milestones 1–4 of the accepted seven-milestone slice are implemented and verified. The tests cover exact fixture identity and validation, selection durability, manual and automatic dice, immutable combat data, both initiative orders, tie-breaking, staged input requests, hit/miss/lethal outcomes, aggregate event publication, projection, failure atomicity, idempotency, and restart reconstruction.

## Verification

- Complete deterministic pytest suite: **588 passed**, with dungeon_manager/ai/test_live_tool_loop_validation.py explicitly excluded.
- Focused Milestones 1–4 slice suite: **81 passed**.
- Five isolated legacy smoke modules: **passed** for models, storage, managers, tools, and registry.
- Normal data/ and logs/ manifest: **unchanged** by path, type, size, UTC modification timestamp, and SHA-256.
- Live validator, Ollama, and all external AI providers: **not invoked**.

The two deterministic guard tests stored in dungeon_manager/ai/test_live_tool_loop_validation.py are excluded together with that file so the checkpoint command is visibly incapable of entering the live validator path.

## Known limitations

- Milestone 5 narration is unstarted; ToolAgent and provider components are not connected to the controlled combat result.
- Milestones 6–7 are unstarted.
- The slice is one fixed campaign, one selectable player character, one hostile goblin, one permitted rapier attack, and one aggregate controlled-round event.
- Goblin tactical behavior is deliberately absent; the goblin-first path records only the accepted no-action advancement.
- Foundry VTT integration, UI, voice, general D&D rules, movement, spells, campaign discovery, editors, and broader content systems are not implemented.
- Event history is durable. Command-audit history, replay protection, and world-state snapshots remain process-local.
- Recovery, migration, repair, retries, polling, background workers, and cross-process coordination are not general product features.
- Ollama behavior has prior opt-in validation but remains nondeterministic and outside this checkpoint's pass/fail evidence.

## Next milestone

**Milestone 5 — Verified AI DM Narration Boundary** is the exact next unstarted GDD milestone. Do not begin it without a separate implementation request.
