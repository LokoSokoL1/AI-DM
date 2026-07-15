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



Tool Schema and Prompt Contract. It is implemented and deterministically
tested.



\## Tested Functionality



\- The Tool Call Parser has assertion-based tests for valid calls, omitted
arguments, ordinary responses, malformed JSON, invalid fields, whole-response
JSON fences, non-object JSON, and refusal to search prose for embedded JSON.

\- The Tool Executor has deterministic tests for argument forwarding, empty
arguments, unknown tools, invalid arguments, controlled exceptions, output
preservation, and confirmation that failures do not retry or invoke another tool.

\- Eighteen focused specification tests cover accurate character-tool schemas,
required and optional arguments, immutable defensive catalogs, deterministic
ordering, malformed and duplicate rejection, callable-signature consistency,
future-tool registration, group-name mismatches, and unsupported callables.

\- An isolated integration test covers `ToolCall` through `ToolRegistry`,
`CharacterTools`, `CharacterManager`, and temporary JSON storage without touching
normal project data.

\- The ToolAgent integration has 22 deterministic tests covering ordinary text,
malformed requests, valid calls with and without arguments, stable observation
JSON, unknown tools, invalid arguments, controlled tool failures, domain-level
failure output, provider call limits, single parsing and execution, final text
preservation, post-execution provider failure, unsafe output, prompt/tool
discovery, deterministic catalog prompts, automatic future-tool exposure, and
the real registry with temporary storage.

\- A valid tool-call attempt produces exactly one delimited, versioned JSON
observation and one final provider request. JSON-looking final text is not parsed
or executed.

\- Post-execution observation serialization and provider failures preserve the
completed `ToolExecutionResult`, return controlled typed failures, and never
retry or execute the tool again.

\- The complete deterministic pytest suite passes 72 tests.

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

\- Immutable provider-neutral `ToolSpec` metadata for every registered character
tool, including strict object schemas, described properties, explicit required
arguments, examples, and rejection of additional properties

\- Registry-time validation that specification names, schema properties,
required arguments, and callable defaults remain consistent, with immutable
sorted specification access and defensive JSON catalog copies

\- Backward-compatible dependency injection for campaign and character storage,
character tools, and the tool registry while preserving production defaults

\- Intrinsically isolated assertion-based legacy smoke modules that clean their
own temporary storage

\- AI provider interface, Ollama provider, and AI manager

\- A typed, standalone Tool Call Parser that validates structure without registry
lookup, tool execution, or game-state changes

\- A typed, standalone Tool Executor that resolves through the central registry,
validates callable arguments, executes once, and preserves normal tool output

\- A typed, bounded `ToolAgent` integration that preserves one-provider behavior
for ordinary or malformed responses and performs one parse, one execution, one
structured observation, and one final provider request for a valid call

\- A deterministic initial prompt contract with a parseable JSON tool catalog,
delimited user request, generated canonical tool-call example, and explicit
single-call and ordinary-response rules

\- `ToolAgentResult`, which preserves the raw initial response, parsed call,
unchanged executor result, and final response, with distinct controlled outcomes
for unsafe observation serialization and post-execution provider failure



\## Partially Implemented Functionality



\- Ollama communication is implemented but is not covered by deterministic tests

\- The tool layer currently exposes only character create/load operations

\- Foundry configuration exists, but Foundry integration is not implemented



\## Planned Functionality



\- Local Ollama end-to-end validation of the existing single-tool loop

\- Any later multi-step agent loop

\- Prompt management and context handling beyond current prompt construction

\- Rules-system, Foundry VTT, management-interface, and advanced-feature roadmap
work described in `PROJECT_PLAN.md`



\## Next Milestone



**Local Ollama End-to-End Tool-Loop Validation**. Validate the existing bounded
tool loop against the configured local provider without expanding autonomy.

