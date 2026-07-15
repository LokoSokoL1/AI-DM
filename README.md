\# Dungeon Manager



Dungeon Manager is an AI-powered tabletop RPG assistant designed to act as a Game Master while integrating with virtual tabletops such as Foundry VTT.



The goal is to create a modular system that can:



\- Run tabletop campaigns locally

\- Use local AI models

\- Manage characters, NPCs, items, worlds, and adventures

\- Track campaign memory

\- Integrate with virtual tabletops

\- Support homebrew content

\- Eventually provide voice interaction and advanced automation



\---



\# Current Development Status



The project is currently in the foundation stage.



Completed:



\- Repository setup

\- Development branch setup

\- Initial architecture planning

\- Project structure creation



Current focus:



\- Creating the Python foundation

\- Connecting to local AI models

\- Building the Dungeon Manager core



\---



\# Design Philosophy



Dungeon Manager separates responsibilities:



The AI handles:



\- Storytelling

\- NPC dialogue

\- Creative generation

\- Interpretation



The application handles:



\- Rules

\- Data storage

\- Character management

\- Items

\- World state

\- Campaign memory



\---



\# Initial Technology



Current development target:



\- Python

\- Ollama

\- Qwen 2.5 32B

\- Foundry VTT integration

\- Local-first operation



\---



\# Long Term Goals



\- AI Game Master

\- Campaign management

\- Automated Foundry control

\- Map and scene assistance

\- Homebrew management

\- Voice-controlled gameplay


\---

\# Deliberate Local Ollama Validation

The live bounded-tool-loop validator is excluded from normal deterministic
testing and requires an explicit environment-variable opt-in. From the project
root in PowerShell:

```
$env:DUNGEON_MANAGER_RUN_LIVE_OLLAMA = "1"
try {
    & .\.venv\Scripts\python.exe -B -m dungeon_manager.ai.live_tool_loop_validation
} finally {
    Remove-Item Env:\DUNGEON_MANAGER_RUN_LIVE_OLLAMA -ErrorAction SilentlyContinue
}
```

The command uses only the configured loopback Ollama endpoint and installed
model, stores character data in a temporary directory, does not configure the
project file logger, performs no retries, prints one structured JSON report, and
deletes its temporary data when finished.

