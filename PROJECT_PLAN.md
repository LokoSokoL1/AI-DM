\# Dungeon Manager Project Plan



\## Current Milestone - Automation Policy and Approval Decisions



Status: Implemented and deterministically validated.



Scope:



\- Add immutable `DENY`, `SUGGEST`, `REQUIRE_CONFIRMATION`, and `AUTOMATIC`
automation modes

\- Add a deeply immutable, defensive, case-sensitive per-capability policy with
exact capability/initiator overrides and fail-closed defaults

\- Add immutable linked policy decisions, explicit human approval or denial
records, and pure gate dispositions

\- Preserve initiator and actor identity without inferring roles or permission
authority, and ignore command payload attempts to self-authorize

\- Keep `GameEngine.dispatch`, ToolAgent, tools, managers, storage, Ollama,
Foundry, and gameplay behavior unchanged


`READY` means only that automation confirmation is satisfied; dispatch has not
occurred. Global trust levels remain future UI/configuration presets that
generate per-capability rules rather than overriding capability policy.

Next milestone: **Policy-Gated Command Dispatch**. It has not started.



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

