\# Dungeon Manager Project Plan



\## Current Milestone - Game Event Foundation and Audit Records



Status: Implemented and deterministically validated.



Scope:



\- Add immutable, data-only `GameEvent` facts with stable IDs, schema versions,
exact event types, command/provenance linkage, and canonical UTC occurrence
times

\- Add immutable `CommandAuditRecord` traces with typed lifecycle stages, safe
structured details, initiator provenance, actor identity, and canonical UTC
recording times

\- Add separate in-memory append-only game-event and command-audit journals with
atomic sequence assignment, duplicate rejection, immutable snapshots, exact
filtering, and defensive serialization

\- Preserve the boundary between command intention, policy or approval,
handling result, world fact, and lifecycle audit trace

\- Keep `PolicyGatedCommandDispatcher`, `GameEngine.dispatch()`, handlers,
ToolAgent, tools, managers, storage, Ollama, Foundry, and gameplay behavior
unchanged


Current journals are process-local and in-memory. They are not durable,
tamper-evident, restart-replay storage, or integrated with dispatch or world
state projection.

Next milestone: **Audited Command Pipeline Integration**. It has not started.



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

