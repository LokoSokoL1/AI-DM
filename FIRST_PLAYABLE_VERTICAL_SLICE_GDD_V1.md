# First Playable Vertical Slice GDD V1.0

Status: accepted product authority. This is the smallest complete playable loop,
implemented in seven deliberately bounded milestones.

Implementation status: Milestone 1, Campaign Runtime and Controlled Fixture
Foundation; Milestone 2, Deterministic Dice Foundation; Milestone 3, Minimal
Combat Domain; Milestone 4, Player Attack Resolution; Milestone 5, Verified AI
DM Narration Boundary; Milestone 6, Durable Complete-Round Restart Proof; and
Milestone 7, End-to-End First Playable Validation are implemented and verified.
The dice primitive remains independently
reusable, while Milestone 4 composes it into the one controlled durable sequence
described below.

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

### Milestone 5 verified-narration clarification

Narration is eligible only after the aggregate controlled-round event has been
durably committed, published to the process-local journal, projected, and
verified synchronized with that exact event. An immutable narration packet is
bound to the source event ID and durable sequence and contains only the recorded
initiative, controlled advancement, attack, damage, hit-point, defeat, and
final-turn facts required for narration. Missing, malformed, mismatched, failed,
or incomplete sources produce no provider call and no inferred replacement
facts.

A dedicated narration-only provider receives that packet without tools,
commands, storage, runtime objects, or mutation authority. One eligible result
is attempted at most once by its narration boundary, without retry, fallback,
combat replay, or another event append. Returned narration is transient
presentation text: it is not a game event, projected state, or evidence that an
action occurred. Provider failure leaves the already committed combat result
unchanged. Restart hydration does not automatically replay narration.

### Milestone 6 durable-restart clarification

The completed controlled round is restart-proven by discarding every original
process-local runtime object and constructing two independent fresh runtimes
from only the existing fixture files and SQLite event journal. Each hydration
reconstructs the exact durable event IDs, sequences, order, payloads, selected
character, projected combat result, and synchronized tails. It does not roll
dice, dispatch a command, resolve combat, append or republish an event, invoke
a provider, ToolAgent, parser, registry, executor, or tool, replay narration,
repair state, or infer missing facts.

The durable comparison establishes its baseline after the store has completed
its SQLite operation, then compares fixture files plus the SQLite database and
WAL when present. The SQLite `-shm` sidecar is process-local coordination
state and is not treated as durable campaign content. Command-audit history,
replay guards, narration/provider history, and Python object identity remain
process-local and are deliberately not claimed to survive restart.

### Milestone 7 end-to-end acceptance clarification

The completed headless engine-level loop is acceptance-validated only through
its public composition boundaries. A staged manual journey proves every missing
face is non-durable until the complete controlled round succeeds; an injected
automatic journey proves the fixed dice-consumption order without manual input.
Together they cover Nekria-first survival, goblin-first controlled no-action
advancement, terminal defeat, durable-before-local publication, synchronized
projection, and one verified transient narration attempt from the exact source
event.

Each acceptance journey discards the original runtime graph and constructs a
fresh runtime from only the fixture files and SQLite journal. Hydration restores
the same authoritative event and projected facts without dice, dispatch,
combat, append, provider, ToolAgent, tool, narration replay, inference, or
repair. This validates the frozen slice's headless engine loop; it does not add
UI, Foundry, voice, or broader gameplay.

Implementation sequence:

1. Campaign Runtime and Controlled Fixture Foundation — implemented and verified.
2. Deterministic Dice Foundation — implemented after verification.
3. Minimal Combat Domain — implemented after verification.
4. Player Attack Resolution — implemented after verification.
5. Verified AI DM Narration Boundary — implemented after verification.
6. Durable Complete-Round Restart Proof — implemented after verification.
7. End-to-End First Playable Validation — implemented and verified.

All seven frozen vertical-slice milestones are complete. No unstarted milestone
remains in this slice; later development requires separate planning.

Excluded until explicitly scheduled: general D&D rules, initiative beyond the
controlled encounter, random generation, damage/HP/conditions, goblin tactics,
spellcasting, movement, AI intent interpretation, ToolAgent work, Ollama,
Foundry, UI, voice, campaign discovery, scene/NPC editors, save-slot browsing,
general content systems, audit persistence, replay persistence, snapshots,
migrations, repair, retries, polling, background workers, and cross-process
coordination.
