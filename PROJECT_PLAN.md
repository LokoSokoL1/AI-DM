\# Dungeon Manager Project Plan



\## Current Milestone - Durable Event Journal Persistence Foundation



Status: Implemented and deterministically validated.



Scope:



\- Add an explicitly initialized, path-bound SQLite store for immutable
sequenced `GameEventJournalEntry` batches without replacing entity JSON storage

\- Persist journal and storage-format identity plus an integer schema version,
with deterministic test IDs or generated UUID IDs, no implicit empty storage,
no automatic migration, and safe reinitialization rejection

\- Use one SQLite transaction per complete append with full synchronous commits,
stale-tail checking, contiguous caller-provided sequences, duplicate-ID
rejection, rollback, and no retries or replacement APIs

\- Store compact canonical `GameEvent` JSON plus sequence/event identity digest,
strictly decode through model constructors, and fail closed on corruption with
no partial snapshot, repair, or rewrite

\- Keep the SQLite boundary standalone: no pipeline integration, automatic
publication persistence, startup hydration, audit durability, or world-state
persistence

\- Return immutable typed `SUCCESS`, `NOT_FOUND`, `ALREADY_EXISTS`,
`INVALID_INPUT`, `STALE_TAIL`, `CORRUPT`, `UNSUPPORTED_VERSION`, and
`STORAGE_FAILURE` results with only safe metadata

\- Keep store operations deliberately free of command dispatch, policy,
approval, audit records, projection, automatic retries, and fallback


Only test reducers and synthetic events exist. Current tools, managers, AI
routing, rules, entity JSON storage, UI, Foundry behavior, and unaudited command
dispatch remain unchanged. The current in-memory journal, audit journal, and
world-state path remain process-local.

Next milestone: **Durable Event Journal Pipeline Integration and Startup
Hydration**. It has not started.



\## Phase 1 - Foundation



Goal:

Create the basic application structure.



Tasks:



\- Python project setup

\- Virtual environment

\- Configuration system

\- Basic logging

\- Initial testing framework



\---



\## Phase 2 - AI Core



Goal:

Create communication between Dungeon Manager and local AI models.



Tasks:



\- AI provider interface

\- Ollama integration

\- Prompt management

\- Context handling



Initial model:



\- Qwen 2.5 32B



\---



\## Phase 3 - Data Management



Goal:

Create structured management of tabletop information.



Tasks:



\- Character system

\- NPC system

\- Item system

\- World data

\- Campaign memory



\---



\## Phase 4 - Rules System



Goal:

Separate game mechanics from AI creativity.



Tasks:



\- Dice system

\- Rules handling

\- Conditions

\- Combat calculations



\---



\## Phase 5 - Foundry Integration



Goal:

Connect Dungeon Manager with Foundry VTT.



Tasks:



\- Actor synchronization

\- Token control

\- Scene management

\- Item handling



\---



\## Phase 6 - Management Interface



Goal:

Create tools for preparation and administration.



Tasks:



\- Content management

\- Homebrew management

\- Campaign tools

\- AI configuration



\---



\## Phase 7 - Advanced Features



Goal:

Add optional advanced functionality.



Tasks:



\- Voice input

\- Voice output

\- NPC voices

\- Advanced map automation

