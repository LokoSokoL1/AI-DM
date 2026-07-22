# First Playable Vertical Slice GDD V1.0

Status: accepted product authority. This is the smallest complete playable loop,
implemented in seven deliberately bounded milestones.

Implementation status: Milestone 1, Campaign Runtime and Controlled Fixture
Foundation; Milestone 2, Deterministic Dice Foundation; Milestone 3, Minimal
Combat Domain; and Milestone 4, Player Attack Resolution are implemented and
verified. The dice primitive remains independently reusable, while Milestone 4
composes it into the one controlled durable sequence described below.

The completed loop is: load an existing campaign, hydrate durable history,
select Nekria, enter one controlled hostile-goblin scene, establish initiative,
choose manual or automatic dice, resolve one verified player attack, narrate
only that verified result, persist it, and restart into the identical state.

The player chooses a character and dice mode. The deterministic engine owns
identity validation, initiative, rolls, attack resolution, state changes, and
durable events. The AI DM may interpret and narrate only verified engine output;
it does not invent rules, outcomes, identities, or persistent state.

Manual dice must accept and validate an explicit player result; automatic dice
must be deterministic and recorded. Durable restart must hydrate the exact
event order without generating, repeating, rewriting, or silently repairing
events. Missing, corrupt, mismatched, or incomplete campaign/journal input fails
predictably before a dispatchable runtime is exposed.

For V1.0, one combat round means: establish initiative, reach Nekria's turn,
resolve one complete player attack, advance to the next turn, persist, and stop.
The controlled fixture may place Nekria first. Goblin tactical decisions are not
part of the slice.

### Milestone 4 controlled-round clarification

Milestone 4 resolves exactly four possible dice stages in this fixed order:
Nekria initiative (1d20+3), goblin-1 initiative (1d20+2), Nekria's rapier
attack (1d20+5), and rapier damage (1d8+3) only on a hit. Caller-supplied stable
roll IDs identify every stage. Manual play requests the next missing natural
face in that order; automatic play consumes injected faces in that same order.
All completed rolls preserve their mode and provenance.

Initiative sorts by descending total, then descending modifier, then ascending
stable participant ID. No tie is rerolled or decided interactively. If goblin-1
is first, round 1 begins on goblin-1 and records the controlled no-action
advance `controlled_slice_no_goblin_behavior`, with no goblin dice or combat
effect, before reaching Nekria. If Nekria is first, round 1 begins directly on
Nekria's turn.

After Nekria's one permitted rapier attack, a surviving goblin-1 is the active
participant: in round 1 for order `[nekria, goblin-1]`, or in round 2 after a
wrap for order `[goblin-1, nekria]`. A defeating attack completes the encounter,
leaves no active participant, and retains round 1. The successful complete
sequence is submitted as one `combat.resolve_controlled_round` command and
publishes exactly one aggregate `combat.controlled_round_resolved` event. The
complete event is appended atomically and projected as one complete state
transition. Manual input requirements and every failed stage are non-durable:
they publish no partial event and expose no partial initiative, turn, HP, or
completion state. Hydration reconstructs the full recorded sequence from the
event without rerolling, requesting input, inference, or appending events.

Implementation sequence:

1. Campaign Runtime and Controlled Fixture Foundation — implemented and verified.
2. Deterministic Dice Foundation — implemented after verification.
3. Minimal Combat Domain — implemented after verification.
4. Player Attack Resolution — implemented after verification.
5. Verified AI DM Narration Boundary — next, unstarted.
6. Durable Complete-Round Restart Proof.
7. End-to-End First Playable Validation.

Excluded until explicitly scheduled: general D&D rules, initiative beyond the
controlled encounter, random generation, damage/HP/conditions, goblin tactics,
spellcasting, movement, AI intent interpretation, ToolAgent work, Ollama,
Foundry, UI, voice, campaign discovery, scene/NPC editors, save-slot browsing,
general content systems, audit persistence, replay persistence, snapshots,
migrations, repair, retries, polling, background workers, and cross-process
coordination.
