\# Dungeon Manager Project Plan



\## Current Milestone - Durable Event Journal Pipeline Integration and Startup Hydration



Status: Implemented and deterministically validated.



Scope:



\- Add exact immutable sequenced-batch preparation and exact atomic local append
without regenerating event identity, timestamps, payloads, or sequences

\- Integrate a validated typed durable binding into the audited pipeline so one
SQLite append succeeds and is verified before the same entries become visible
in the process-local journal and projection

\- Fail closed on stale external writers, journal mismatch, unavailable or
uncertain storage, and confirmed durable commit followed by local synchronization
failure; require fresh explicit startup hydration for durable divergence

\- Preserve the existing explicit projection-recovery path only for projection
failure after durable and local publication, with no durable append during
recovery

\- Add explicit all-or-nothing startup hydration from an existing store and
caller-supplied sequence-zero base into fresh journal and world-state views

\- Return immutable typed hydration, durable-publication, and durable-health
metadata with defensive payload-free durable serialization


Only test reducers and synthetic events exist. Current tools, managers, AI
routing, rules, entity JSON storage, UI, Foundry behavior, and unaudited command
dispatch remain unchanged. SQLite event history is durable; command audit,
replay protection, and world-state projection remain process-local.

Next milestone: **First Playable Vertical Slice GDD Specification**. It has not
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

