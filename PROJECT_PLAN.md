\# Dungeon Manager Project Plan



\## Current Milestone - Audited Command Pipeline Integration



Status: Implemented and deterministically validated.



Scope:



\- Add an optional synchronous `AuditedCommandPipeline` around the existing
policy-gated dispatcher without duplicating policy, approval, gate, replay, or
engine-dispatch behavior

\- Append safe typed audit records for proposal, policy, applicable approval,
gate, blocked or attempted dispatch, completion, and coordinator failure

\- Add an immutable audited result that preserves the authoritative
`PolicyGatedDispatchResult`, immutable journal-entry references, audit status,
and safe failure text

\- Fail closed before the engine boundary when a required audit append fails;
after the boundary, preserve the result and replay consumption without retry

\- Keep unaudited coordinator behavior backward compatible and produce no
`GameEvent` records


Audit and replay state remain process-local and in-memory. They are not durable,
tamper-evident, restart-safe, transactional, or integrated with world-state
projection.

Next milestone: **Event-Producing Command Handler Contract**. It has not
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

