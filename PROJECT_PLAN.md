\# Dungeon Manager Project Plan



\## Current Milestone - World State Projection Pipeline Integration



Status: Implemented and deterministically validated.



Scope:



\- Add an explicit process-local `WorldStateHolder` for one immutable committed
snapshot plus payload-free synchronized/out-of-sync health

\- Require the current state sequence and injected event-journal tail to agree
at pipeline construction and before each dispatch, failing closed on mismatch

\- Extend `AuditedCommandPipeline` with explicit projector and state-holder
dependencies while leaving policy, replay, dispatch, publication, and reducer
rules authoritative in their existing components

\- After successful atomic publication, project exactly the immutable sequenced
journal entries returned by that publication and commit only a complete
successful projection

\- Serialize pipeline submissions through one synchronous non-reentrant
coordination boundary so concurrent calls preserve journal/projection order and
recursive calls fail before dispatch

\- Return typed `NOT_APPLICABLE`, `UNCHANGED`, `PROJECTED`, `FAILED`, or
`UNAVAILABLE` projection disposition with sequence-only, controlled status,
reason, and safe error metadata

\- Preserve published events and replay consumption on projection failure,
leave the previous state unchanged, mark projection out of sync, and block later
dispatch until a future explicit recovery boundary exists


Only test reducers and synthetic events exist. Current tools, managers, AI
routing, rules, storage, UI, Foundry behavior, and unaudited command dispatch
remain unchanged. Audit, event, and state updates remain deliberately
non-transactional and process-local.

Next milestone: **World State Projection Recovery and Rebuild**. It has not
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

