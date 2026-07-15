\# Dungeon Manager Project Plan



\## Current Milestone - Event Journal Publication Integration



Status: Implemented and deterministically validated.



Scope:



\- Add an atomic `GameEventJournal.append_batch()` operation that validates and
materializes the complete ordered batch before one copy-on-write mutation

\- Preserve the existing single-event append API while rejecting invalid event
values, duplicate IDs within a batch, and IDs already present in the journal
without partial mutation or sequence gaps

\- Inject `GameEventJournal` explicitly into the existing
`AuditedCommandPipeline` and publish only the exact event tuple on a preserved
`DISPATCHED` result

\- Distinguish publication as `NOT_APPLICABLE`, `NO_EVENTS`, `PUBLISHED`, or
`FAILED`, preserving immutable appended-entry snapshots and safe errors

\- Preserve dispatcher authority, completed dispatch results, consumed replay
state, and exactly-once handler behavior across publication and post-dispatch
audit failures

\- Keep event and audit journals independently successful after dispatch; do
not add transactions, retries, persistence, queues, subscribers, or projection


Only test handlers produce events. Current tools, managers, AI routing, rules,
storage, UI, and Foundry behavior remain unchanged.

Next milestone: **World State Projection Foundation**. It has not started.



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

