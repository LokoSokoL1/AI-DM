\# Dungeon Manager Architecture



\## Overview


This structure represents the planned architecture.
Actual folders will be created as functionality is implemented.



Dungeon Manager is designed as a modular AI-powered tabletop RPG assistant.



The goal is to create a flexible system capable of supporting different tabletop games while keeping the AI, rules, campaign data, and virtual tabletop integration separated.



The initial development target is:



\- Dungeons \& Dragons 5e

\- Local AI operation

\- Ollama backend

\- Foundry VTT integration



Future systems should be possible by replacing or extending modules rather than rebuilding the entire application.



\---



\# Project Structure



```

Dungeon Manager



├── dungeon\_manager/

│   │

│   ├── core/

│   │   ├── campaign.py

│   │   ├── session.py

│   │   └── game\_state.py

│   │

│   ├── ai/

│   │   ├── provider.py

│   │   ├── ollama.py

│   │   ├── prompts.py

│   │   └── context.py

│   │

│   ├── data/

│   │   ├── characters.py

│   │   ├── items.py

│   │   ├── npcs.py

│   │   └── world.py

│   │

│   ├── rules/

│   │   ├── engine.py

│   │   └── dice.py

│   │

│   ├── foundry/

│   │   ├── connector.py

│   │   └── sync.py

│   │

│   └── main.py

│

├── data/

│   │

│   ├── campaigns/

│   ├── characters/

│   ├── items/

│   ├── npcs/

│   ├── worlds/

│   ├── adventures/

│   ├── rules/

│   └── memory/

│

├── foundry/

│   └── integration files

│

├── ui/

│   └── management interface

│

├── tools/

│   └── import/export utilities

│

├── tests/

│

└── docs/

```



\---



\# Core Components



\## Core Engine



Responsible for:



\- Campaign state

\- Session management

\- Game flow

\- Tracking changes



The core should not depend directly on any AI model.



\---



\# AI Layer



The AI layer handles communication with language models.



Initial implementation:



```

Dungeon Manager

&#x20;       |

&#x20;       |

&#x20;AI Provider Interface

&#x20;       |

&#x20;       |

&#x20;Ollama

&#x20;       |

&#x20;       |

&#x20;Qwen 2.5 32B

```



Future providers can be added:



\- Other local models

\- Cloud AI providers

\- Alternative AI systems



The rest of Dungeon Manager communicates through the provider interface instead of directly with a specific model.



\---



\# Data Layer



Structured information is managed by Dungeon Manager.



Examples:



\## Characters



\- Stats

\- Classes

\- Levels

\- Inventory

\- Background

\- Relationships



\## Items



\- Name

\- Description

\- Properties

\- Magical effects

\- Ownership

\- History



\## NPCs



\- Personality

\- Goals

\- Knowledge

\- Relationships

\- Current state



\## World



\- Locations

\- Factions

\- History

\- Events



The AI can use this information but should not be the only place where it exists.



\---



\# Rules System



The rules system handles deterministic game mechanics.



Examples:



\- Dice rolls

\- Character calculations

\- Conditions

\- Combat rules

\- Spell effects



The AI should interpret situations, but the rules engine should handle calculations.



\---



\# Foundry Integration



Foundry VTT acts as the visual tabletop interface.



Dungeon Manager remains the campaign intelligence layer.



The integration should eventually allow:



\- Token movement

\- Scene changes

\- Actor synchronization

\- Item assignment

\- Combat management

\- Map preparation



\---



\# Management Interface



A separate interface will exist for preparation and administration.



This prevents confusing gameplay communication with management commands.



Examples:



\- Add homebrew content

\- Import adventures

\- Edit NPCs

\- Manage rules

\- Change AI settings

\- Review campaign memory



\---



\# Design Principles



\## Modularity



Components should be replaceable without rebuilding the entire system.



\## Separation of Responsibilities



The AI creates and interprets.



The application stores and calculates.



\## Local First



The system should work locally before adding external services.



\## Expand Carefully



New features should support tabletop gameplay rather than adding unnecessary complexity.



## Current Runtime Flow

The current system architecture:

User
 |
 v
Dungeon Manager
 |
 v
AI Provider Layer
 |
 v
Tool Layer
 |
 +-- Character Manager
 |
 +-- Item Manager
 |
 +-- Campaign Manager
 |
 v
Models
 |
 v
JSON Storage


## AI Tool Philosophy

The AI model does not directly modify files.

All world changes must go through controlled managers.

This prevents:
- invalid data
- accidental overwrites
- inconsistent campaign state

The AI acts as a decision layer, while Dungeon Manager controls execution.


## Tool Call Parsing Boundary

The Tool Call Parser is a standalone part of the AI layer. It inspects one
complete AI response and classifies it as a valid tool request, an ordinary
response with no tool request, or a malformed tool request.

A structurally valid request contains a non-empty `tool` string and an
`arguments` object. Omitted arguments default to an empty object. The parser may
accept one clean JSON Markdown fence only when the fence contains the entire
response; it does not scan surrounding prose for embedded JSON.

Parsing does not look up the tool registry, execute a tool, modify game state, or
change `ToolAgent` behavior. Those responsibilities belong to later milestones.


## Tool Execution Boundary

The Tool Executor is a standalone, synchronous part of the AI layer. It accepts
an already validated `ToolCall`, resolves the named callable through the central
`ToolRegistry`, validates its arguments against that callable's signature, and
delegates one execution attempt back to the registry.

Execution returns a typed result that distinguishes success, an unknown tool,
invalid arguments, and a controlled tool failure. A normal tool return is
preserved unchanged as successful execution, including domain-level payloads
whose own `success` field is false. Raised exceptions are logged internally and
converted to safe error text without exposing tracebacks to callers.

The executor does not parse AI text, call an AI provider, retry tools, choose a
fallback tool, or access storage directly. State changes still flow through
registered tools and their managers. `ToolAgent` does not yet use the parser or
executor; that integration remains a later milestone.

