\# Dungeon Manager Project Plan



\## Current Milestone - Game Engine Foundation: Commands and Results



Status: Implemented and deterministically validated.



Scope:



\- Add immutable provider-independent game commands with stable IDs, deeply
immutable JSON-compatible payloads, provenance, and optional actor identity

\- Add immutable linked game results with explicit success, unknown-command,
invalid-command, invalid-handler-result, and controlled-failure statuses

\- Add exact synchronous handler registration and one-attempt dispatch without
retries, fallback handlers, approval decisions, or game rules

\- Preserve initiator provenance for a future optional capability-level
automation policy without treating command creation as authorization

\- Keep the existing ToolAgent, tools, managers, storage, Ollama validation, and
Foundry paths unchanged


Only test handlers exist in this milestone. No character, combat, dice,
campaign, approval, event, or Foundry command has been introduced.

Next milestone: **Automation Policy and Approval Decisions**. It has not
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

