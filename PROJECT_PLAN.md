\# Dungeon Manager Project Plan



\## Current Milestone - World State Projection Foundation



Status: Implemented and deterministically validated.



Scope:



\- Add immutable `WorldState` data with deeply frozen JSON-object content,
defensive serialization, and the last successfully applied journal sequence

\- Register synchronous reducers by exact case-sensitive event type and exact
positive schema version, with strict callable-shape validation and immutable
sorted registration snapshots

\- Materialize and completely validate ordered `GameEventJournalEntry`
snapshots, including contiguous incremental sequence rules and duplicate event
IDs, before invoking any reducer

\- Resolve every reducer before applying events once in journal order, with no
fallback, retry, skip, migration, or partial-state exposure

\- Return typed immutable results for success, invalid input, unknown event
type, unsupported schema version, invalid reducer data, and reducer failure
using safe payload-free diagnostics

\- Keep projection pure, in-memory, and separate from event publication and the
`AuditedCommandPipeline`


Only test reducers exist. Current tools, managers, AI routing, rules, storage,
UI, Foundry behavior, event publication, and command dispatch remain unchanged.

Next milestone: **World State Projection Pipeline Integration**. It has not
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

