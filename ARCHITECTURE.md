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

