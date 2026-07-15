\# Dungeon Manager Project Plan



\## Current Milestone - Policy-Gated Command Dispatch



Status: Implemented and deterministically validated.



Scope:



\- Compose the existing immutable automation policy, approval resolver, and
`GameEngine` through one synchronous coordinator

\- Expose one immutable combined result that preserves policy and gate
provenance plus the exact `GameResult` only when dispatch was attempted

\- Dispatch only a `READY` gate disposition while preserving awaiting,
suggestion, denial, invalid, duplicate, and controlled failure outcomes

\- Add per-coordinator process-local command-ID replay protection recorded
before engine dispatch, including repeated and re-entrant submission blocking

\- Keep policy precedence, approval validation, handler resolution,
`GameEngine.dispatch`, ToolAgent, tools, managers, storage, Ollama, Foundry, and
gameplay behavior unchanged


Replay state is memory-only, scoped to one coordinator instance, and is not
restart-safe or durable idempotency. Future event or journal persistence is
required before replay protection can survive process restarts.

Next milestone: **Game Event Foundation and Audit Records**. It has not started.



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

