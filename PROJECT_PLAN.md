\# Dungeon Manager Project Plan



\## Current Milestone - ToolAgent Parser/Executor Integration



Status: Implemented and deterministically tested.



Scope:



\- Make one provider request through the existing provider abstraction

\- Parse the complete provider response with the existing Tool Call Parser

\- Return typed ordinary-response, malformed-request, or tool-execution results

\- Execute one valid call through the existing Tool Executor and shared registry

\- Preserve the raw response, parsed call, and unchanged executor observation

\- Avoid follow-up provider calls, retries, loops, and direct storage access



Next milestone: **Single-Tool Observation/Response Loop**. Send one completed
tool observation back to the provider for one final assistant response. That loop
has not started.



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

