\# Dungeon Manager Project Status



\## Current Phase

AI Core



\## Verified Project Setup



\- Git repository created

\- Develop branch created

\- Initial folder structure created

\- GitHub connection established

\- Initial documentation created

\- Gitignore configured



\## Current Milestone



Legacy Test Data Isolation. It is implemented and deterministically
tested.



\## Tested Functionality



\- The Tool Call Parser has assertion-based tests for valid calls, omitted
arguments, ordinary responses, malformed JSON, invalid fields, whole-response
JSON fences, non-object JSON, and refusal to search prose for embedded JSON.

\- The Tool Executor has deterministic tests for argument forwarding, empty
arguments, unknown tools, invalid arguments, controlled exceptions, output
preservation, and confirmation that failures do not retry or invoke another tool.

\- An isolated integration test covers `ToolCall` through `ToolRegistry`,
`CharacterTools`, `CharacterManager`, and temporary JSON storage without touching
normal project data.

\- The ToolAgent integration has 15 deterministic tests covering ordinary text,
valid calls with and without arguments, malformed JSON, unknown tools, invalid
arguments, tool exceptions, unchanged successful output, provider call counts,
prompt/tool discovery, provider-error propagation, and the real registry with
temporary storage.

\- The complete deterministic pytest suite passes 47 tests: the previous 42
tests plus five legacy-isolation regression tests.

\- The five legacy modules now provide assertion-based pytest coverage for model
serialization, JSON storage, the campaign manager, character tools, and the tool
registry using temporary directories.

\- Direct `python -m` execution of each legacy module creates and cleans its own
temporary storage without an external wrapper.

\- Before/after file lists, content hashes, and modification times confirm that
direct smoke execution and deterministic pytest leave normal `data/` and `logs/`
unchanged.

\- The Ollama smoke script requires a running external service and is not part of
deterministic automated testing.

\- No Ollama request was made while verifying this milestone.



\## Implemented Functionality



\- Project configuration loading and logging setup

\- Character, Item, and Campaign data models

\- JSON file storage

\- Character, Item, and Campaign managers

\- Character create/load tools and a central tool registry

\- Backward-compatible dependency injection for campaign and character storage,
character tools, and the tool registry while preserving production defaults

\- Intrinsically isolated assertion-based legacy smoke modules that clean their
own temporary storage

\- AI provider interface, Ollama provider, and AI manager

\- A typed, standalone Tool Call Parser that validates structure without registry
lookup, tool execution, or game-state changes

\- A typed, standalone Tool Executor that resolves through the central registry,
validates callable arguments, executes once, and preserves normal tool output

\- A typed, single-pass `ToolAgent` integration that makes one provider request,
parses the complete response, avoids execution for ordinary or malformed
responses, and invokes the existing executor once for a valid call

\- `ToolAgentResult`, which preserves the raw response and distinguishes an
ordinary assistant response, a malformed tool request, and a completed tool
execution attempt with its parsed call and unchanged executor observation



\## Partially Implemented Functionality



\- `ToolAgent` returns a structured observation but does not yet send that
observation back to the model for a final assistant response

\- Ollama communication is implemented but is not covered by deterministic tests

\- The tool layer currently exposes only character create/load operations

\- Foundry configuration exists, but Foundry integration is not implemented



\## Planned Functionality



\- A single-tool observation/response loop

\- Any later multi-step agent loop

\- Prompt management and context handling beyond current prompt construction

\- Rules-system, Foundry VTT, management-interface, and advanced-feature roadmap
work described in `PROJECT_PLAN.md`



\## Next Milestone



**Single-Tool Observation/Response Loop**. Send one completed tool observation
back to the provider for one final assistant response without adding multiple
tool calls, retries, recursive autonomy, permissions, or memory.

