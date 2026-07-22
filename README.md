# Dungeon Manager

Dungeon Manager is a local-first tabletop RPG system for running persistent campaigns with a trustworthy AI Dungeon Master backed by a deterministic game engine.

The player chooses; the AI interprets and performs the Dungeon Master role; the engine validates, resolves, and remembers authoritative game facts. Foundry VTT is the intended visual tabletop for maps, tokens, sheets, lighting, and effects. It is not the rules or campaign-state authority, and Foundry integration has not yet been implemented.

## Current stage

The project is implementing the accepted seven-milestone First Playable Vertical Slice. Milestones 1–4 are complete and deterministically verified: the controlled campaign fixture, manual and automatic dice foundation, minimal Nekria-versus-goblin combat domain, and one durable player-attack round.

The exact next unstarted milestone is **Milestone 5 — Verified AI DM Narration Boundary**. No Milestone 5 implementation is included in this checkpoint.

## Documentation

- [GDD.md](GDD.md) — master product vision and design philosophy.
- [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md) — frozen executable behavior and seven-milestone slice sequence.
- [ARCHITECTURE.md](ARCHITECTURE.md) — implemented technical boundaries, flows, ownership, and failure behavior.
- [PROJECT_PLAN.md](PROJECT_PLAN.md) — accepted milestone order and current next step.
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — verified implementation and test status.
- [DOCUMENTATION.md](DOCUMENTATION.md) — documentation inventory, authority, and navigation, including research-record status.

## Local-first operation

Campaign records and configuration are locally controlled. The current durable event authority is a local SQLite journal; process-local projections are rebuilt from it. The optional Ollama validation harness is separate from deterministic verification and runs only with explicit opt-in.

## Development verification

Use the repository virtual environment:

    .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --ignore=dungeon_manager/ai/test_live_tool_loop_validation.py

The live validator, Ollama, Foundry, UI, and external AI providers are not required for the deterministic suite.
