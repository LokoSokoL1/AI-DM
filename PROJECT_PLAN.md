\# Dungeon Manager Project Plan



\## Current Milestone - Event-Producing Command Handler Contract



Status: Implemented and deterministically validated.



Scope:



\- Extend the existing immutable `GameResult` with an ordered immutable tuple
of zero or more `GameEvent` records that defaults to empty

\- Validate every produced event without repairing command linkage, replacing
objects, reordering events, or removing duplicate IDs

\- Convert invalid event collections, non-event values, mismatched originating
command IDs, duplicate event IDs, and corrupted events into the existing safe
`INVALID_HANDLER_RESULT`

\- Preserve valid event tuples unchanged through `GameEngine`, policy-gated
dispatch, audited dispatch, post-dispatch audit failure, and defensive
serialization

\- Keep blocked paths event-free and leave `GameEventJournal` append,
publication, persistence, projection, transactions, and subscribers outside
this milestone


Only test handlers produce events. Current tools, managers, AI routing, rules,
storage, UI, and Foundry behavior remain unchanged.

Next milestone: **Event Journal Publication Integration**. It has not started.



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

