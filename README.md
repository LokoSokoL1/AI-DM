# Dungeon Manager

Dungeon Manager is a local-first tabletop RPG system for running persistent campaigns with a trustworthy AI Dungeon Master backed by a deterministic game engine.

The player chooses; the AI interprets and performs the Dungeon Master role; the engine validates, resolves, and remembers authoritative game facts. Foundry VTT is the intended visual tabletop for maps, tokens, sheets, lighting, and effects. It is not the rules or campaign-state authority, and Foundry integration has not yet been implemented.

## Current stage

The accepted seven-milestone First Playable Vertical Slice is complete and deterministically verified. Its headless engine-level loop uses the controlled campaign fixture, manual or automatic dice, the Nekria-versus-goblin controlled round, one durable aggregate event and projection, verified transient AI DM narration, and fresh durable restart reconstruction.

The final acceptance journeys prove both staged manual input and injected automatic dice through the real public composition boundaries. The original runtime graph is discarded before fresh hydration from the fixture files and SQLite journal alone; restart neither rerolls, dispatches, appends, repairs, narrates, nor replays gameplay. Narration stays transient and never becomes authoritative state. UI, Foundry, and voice remain outside this slice. No unstarted milestone remains in the frozen slice; a separate planning decision is required for later development.

The [Phase 2 low-fidelity interface design baseline](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md)
was formally accepted on 2026-07-29 from the exact draft with SHA-256
`21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3`.
It approves product behavior and acceptance criteria, not implementation.
The described interface and Foundry integration remain unimplemented, and its
ten explicitly deferred implementation decisions remain open. The next step is
a separate bounded Phase 2 technical-planning task; later technical design and
implementation must conform to the accepted baseline or record an explicit
revision.

## Documentation

- [GDD.md](GDD.md) — master product vision and design philosophy.
- [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md) — frozen executable behavior and seven-milestone slice sequence.
- [LOW_FIDELITY_INTERFACE_SPEC_V1.md](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md) — formally accepted Phase 2 low-fidelity interface design baseline; not implemented.
- [ARCHITECTURE.md](ARCHITECTURE.md) — implemented technical boundaries, flows, ownership, and failure behavior.
- [PROJECT_PLAN.md](PROJECT_PLAN.md) — accepted milestone order and current next step.
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — verified implementation and test status.
- [DOCUMENTATION.md](DOCUMENTATION.md) — documentation inventory, authority, and navigation, including research-record status.

- [Research](docs/research/README.md) — evidence from tabletop play that informs, but does not itself change, design or implementation authority; see [RI-001](docs/research/RI-001.md).

## Local-first operation

Campaign records and configuration are locally controlled. The current durable event authority is a local SQLite journal; process-local projections are rebuilt from it. The optional Ollama validation harness is separate from deterministic verification and runs only with explicit opt-in.

## Development verification

Use the repository virtual environment:

    .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --ignore=dungeon_manager/ai/test_live_tool_loop_validation.py

The live validator, Ollama, Foundry, UI, and external AI providers are not required for the deterministic suite.
