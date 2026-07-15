\# Dungeon Manager Project Plan



\## Current Milestone - Local Ollama End-to-End Tool-Loop Validation



Status: Implemented and validated against the configured local Ollama model.



Scope:



\- Keep live validation deliberately opt-in and outside the deterministic suite

\- Use the configured Ollama provider and model through the real bounded
`ToolAgent` loop

\- Exercise ordinary response, character creation, existing-character load, and
missing-character load scenarios exactly once per live run

\- Inject temporary JSON storage and avoid normal project data and logs

\- Report initial/final model responses, classifications, execution results,
call counts, storage snapshots, and failure reasons as structured JSON


The first live run passed all four required scenarios using `qwen2.5:32b`
without a prompt correction or rerun.

Next milestone: **Game Engine Foundation: Commands and Results**. It has not
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

