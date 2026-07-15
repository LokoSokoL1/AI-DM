\# Dungeon Manager Project Plan



\## Current Milestone - World State Projection Recovery and Rebuild



Status: Implemented and deterministically validated.



Scope:



\- Add an explicit trusted/operator `recover_world_state()` API to the existing
`AuditedCommandPipeline` without creating another dispatch pipeline

\- Support typed `CATCH_UP` from the holder's committed state and typed
`FULL_REBUILD` from a caller-supplied immutable sequence-zero base state

\- Serialize recovery, command dispatch, publication, and projection through the
same synchronous non-reentrant coordination boundary

\- Capture one authoritative immutable event-journal snapshot, project with the
existing `WorldStateProjector`, verify its tail remains unchanged, and commit
state plus synchronization health only after complete success

\- Preserve the previous committed state and appropriate health on every failed
recovery, while allowing successful rebuild to replace stale derived state

\- Return typed `RECOVERED`, `NO_ACTION`, `INVALID_REQUEST`,
`PROJECTION_FAILURE`, `JOURNAL_CHANGED`, `UNAVAILABLE`, or
`COORDINATOR_FAILURE` metadata without exposing world-state or event data

\- Keep recovery deliberately requested and free of command dispatch, policy,
approval, replay, publication, command audit records, retries, and fallback


Only test reducers and synthetic events exist. Current tools, managers, AI
routing, rules, storage, UI, Foundry behavior, and unaudited command dispatch
remain unchanged. Audit, event, and state updates remain deliberately
non-transactional and process-local.

Next milestone: **Durable Event Journal Persistence Foundation**. It has not
started.



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

