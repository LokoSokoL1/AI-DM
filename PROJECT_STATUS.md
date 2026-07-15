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



Local Ollama End-to-End Tool-Loop Validation. It is implemented and validated
against the configured local provider and model.



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

\- No Ollama request was made while verifying the preceding deterministic Tool
Schema and Prompt Contract milestone.

\- The opt-in live validator passed its first clean run against Ollama `0.31.2`
at `http://localhost:11434` using the installed `qwen2.5:32b` model tag.

\- The live run passed ordinary response, create-character,
load-existing-character, and load-missing-character scenarios without manual
response repair, retries, parser bypasses, prompt changes, or a second run.

\- The four live scenarios made exactly seven provider calls, three executor
calls, three registry executions, and three underlying tool calls. The tool
calls were one `create_character` and two `load_character` invocations.

\- Character creation and both loads used one injected temporary JSON storage
root. The created character was present only there during validation, and the
temporary directory was removed after the run.

\- The reusable harness has two deterministic tests for its explicit opt-in
guard and its isolated real-component wiring. The complete deterministic suite
passes 74 tests.



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

\- A standalone live Ollama validator that performs a loopback/model preflight,
uses `AIManager` to construct the configured provider, instruments exact call
counts without changing behavior, injects temporary JSON storage through the
real managers/tools/registry, emits one structured JSON report, and never
retries

\- The legacy Ollama smoke-module command now delegates to the guarded live
validator and cannot use normal project storage as an alternate path



\## Partially Implemented Functionality



\- Ollama communication has one successful local live-validation result; live
model behavior remains nondeterministic and intentionally outside normal tests

\- The tool layer currently exposes only character create/load operations

\- Foundry configuration exists, but Foundry integration is not implemented



\## Planned Functionality



\- Any later multi-step agent loop

\- Prompt management and context handling beyond current prompt construction

\- Rules-system, Foundry VTT, management-interface, and advanced-feature roadmap
work described in `PROJECT_PLAN.md`



\## Next Milestone



**Game Engine Foundation: Commands and Results**. Define the provider-neutral
command and result boundary for deterministic game-engine work without starting
broader rules-system functionality.

