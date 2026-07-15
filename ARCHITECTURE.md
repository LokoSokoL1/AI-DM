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


## Game Command and Dispatch Boundary

`dungeon_manager.engine` is the provider-independent entry boundary for future
game-engine actions. It uses only the Python standard library and has no direct
dependency on AI providers, tools, managers, storage, rules, Foundry, or the
current character-tool path.

`GameCommand` is an immutable intention. It carries a generated or explicitly
supplied stable command ID, an exact command type, a deeply immutable
JSON-compatible object payload, immutable provenance, and an optional actor ID.
It contains no business logic and cannot execute itself. Provenance records the
initiator source (`human`, `ai`, `system`, or `external`) and may identify the
specific initiator. The actor ID separately identifies who or what that
initiator is acting as; it does not define a role or grant permission. Commands
have no timestamp or correlation fields because the current architecture does
not yet require them. `to_dict()` returns an independent JSON-compatible copy
for future logging, transport, or persistence.

`GameResult` is immutable and linked to the originating command ID. Its current
statuses are:

- `SUCCESS`: one handler returned a structurally valid result. This describes
  handling, so output may still contain a normal domain-level negative outcome.
- `UNKNOWN_COMMAND`: no exact handler registration exists.
- `INVALID_COMMAND`: a command fails structural revalidation before handling.
- `INVALID_HANDLER_RESULT`: a handler returns the wrong type, an invalid result,
  or a result linked to a different command ID.
- `HANDLER_FAILURE`: the selected handler raises an exception, or a handler
  deliberately returns a safe controlled failure.

Successful results cannot carry errors. Every non-success result requires
non-empty safe caller-facing error text and cannot carry output. Nested output
is immutable. Successful results also contain an ordered immutable tuple of
zero or more `GameEvent` records, defaulting to empty. The tuple preserves the
handler's exact event objects and order; it does not generate, repair, replace,
reorder, deduplicate, publish, or persist them. Every event is structurally
revalidated, must link to the result command ID through
`originating_command_id`, and must have an event ID unique within that result.
Event provenance and actor identity remain independent from command provenance
and actor identity. Non-success results cannot contain events. `to_dict()`
returns independent JSON-compatible output and event data.

`GameEngine` registers one synchronous handler for each exact command type.
Registration rejects invalid types, non-callable or incorrectly shaped
handlers, and duplicates. Dispatch revalidates the command, looks up one exact
type, and invokes at most one handler exactly once. It does not retry or fall
through to another handler. Missing handlers and invalid handler results become
controlled results. Structurally invalid event collections, non-event values,
mismatched command linkage, duplicate event IDs, and corrupted events are
controlled `INVALID_HANDLER_RESULT` outcomes with no events. Raised exceptions
are logged with internal details and converted to safe caller-facing failures
without tracebacks, raw exception text, or event payloads. Only test handlers
exist in this milestone; current tools and managers do not dispatch through
this engine yet.


## Trust and Optional Automation Boundary

The current pre-dispatch automation flow is:

**GameCommand → AutomationPolicy → PolicyDecision → optional
HumanApprovalDecision → GateDisposition**

This remains a pure decision boundary. It does not call
`GameEngine.dispatch()`, a handler, a tool, a manager, storage, an AI provider,
a UI, or Foundry. A `READY` disposition means only that automation confirmation
is satisfied; it does not mean permissions, game rules, command validation,
dispatch, or execution have succeeded. The separate coordinator described
below composes this pure boundary with the existing engine dispatcher.

`AutomationPolicy` uses the trusted exact `GameCommand.command_type` as its
case-sensitive capability key. Policy configuration consists of explicitly
configured capabilities, optional per-capability default modes, exact
per-capability/per-initiator modes, and policy-wide initiator rules that apply
only to configured capabilities. Precedence is:

1. exact capability and initiator rule;
2. capability default;
3. policy-wide initiator rule for an explicitly configured capability;
4. denial.

Unknown capabilities are denied before policy-wide initiator rules are
considered. Configured capabilities without an applicable rule are also denied.
Payload fields are never consulted for automation mode, capability, approval,
authorization, roles, or permissions, so a command cannot grant itself
authority. Configuration is deeply immutable and has defensive
JSON-compatible serialization.

The four automation modes are `DENY`, `SUGGEST`, `REQUIRE_CONFIRMATION`, and
`AUTOMATIC`. `PolicyDecision` preserves the command ID, exact capability,
initiator kind and optional identity, actor ID, selected mode, stable reason
code, safe explanation, and whether human confirmation is required.

`HumanApprovalDecision` is an immutable matching-command record with an
explicit `APPROVED` or `DENIED` outcome, a non-empty human approver identity,
and an optional reason. Only records marked with human provenance are valid;
AI self-approval is rejected. The record does not mutate the command, dispatch
anything, establish DM/player authority, or persist approval state.

`resolve_automation_gate()` returns an immutable disposition: `READY`,
`AWAITING_APPROVAL`, `SUGGEST_ONLY`, `DENIED`, or a fail-closed `INVALID`
state. Mismatched, malformed, or unnecessary approvals never make a command
ready. The resolver contains no executable behavior.

Automation remains optional and authoritative per capability. Future global
trust levels will be UI/configuration presets that generate capability rules,
not authority that overrides them. A preset may therefore produce automatic
initiative, confirmed dice rolls, suggested token movement, and denied
automatic damage in the same configuration. Roles, DM/player permission
authority, persistence, events, and gameplay rules remain future boundaries.


## Policy-Gated Command Dispatch Boundary

The controlled command flow is now:

**GameCommand → AutomationPolicy → PolicyDecision → optional
HumanApprovalDecision → GateDisposition → optional GameEngine.dispatch() →
PolicyGatedDispatchResult**

`PolicyGatedCommandDispatcher` is a small synchronous coordinator configured
with one immutable `AutomationPolicy` and one `GameEngine`. Its public dispatch
entry accepts only a `GameCommand` and optional `HumanApprovalDecision`.
Callers cannot provide a policy decision, automation mode, capability, or gate
disposition. The coordinator delegates policy precedence to
`AutomationPolicy.evaluate()`, approval validation and gate resolution to
`resolve_automation_gate()`, and exact handler selection and invocation to
`GameEngine.dispatch()`; it never calls a handler directly.

`PolicyGatedDispatchResult` is immutable and distinguishes `DISPATCHED`,
`AWAITING_APPROVAL`, `SUGGESTION_ONLY`, `DENIED`, `INVALID`, `DUPLICATE`, and
`COORDINATOR_FAILURE`. It preserves the command ID, every successfully produced
policy decision, the gate disposition, a valid supplied approval for future
audit provenance, the exact `GameResult` when dispatch returned normally, and
a safe caller-facing explanation. Only `DISPATCHED` contains a `GameResult`,
and it means dispatch was attempted rather than that handling succeeded.
`UNKNOWN_COMMAND`, `INVALID_COMMAND`, `INVALID_HANDLER_RESULT`, and
`HANDLER_FAILURE` therefore remain unchanged engine outcomes inside a dispatched
aggregate. A normal domain-negative output remains a successful engine result.

Each coordinator instance has process-local command-ID replay protection. A
ready command ID is recorded atomically before `GameEngine.dispatch()` is
called, which blocks repeated and re-entrant dispatch attempts. Awaiting,
suggested, denied, and invalid submissions do not consume the ID; in particular,
a human denial can later be replaced by an approval for the same command. A
sorted immutable snapshot is available for diagnostics, with no API for
removing IDs. This state is neither shared between coordinator instances nor
durable across process restarts. Restart-safe idempotency requires future event
or journal persistence.

Unexpected policy, gate, or coordinator failures are logged internally and
fail closed with safe aggregate results. An unexpected exception after the
engine call begins consumes replay protection and is not retried. Normal
controlled `GameResult` failures are not reinterpreted as coordinator failures,
and policy evaluation, gate resolution, dispatch, and handlers are each
attempted at most once per submission.


## Game Event and Command Audit Foundation

The engine boundary now distinguishes five related concepts:

- A `GameCommand` is an intention.
- A policy or approval decision determines whether that intention may proceed.
- A `GameResult` describes command validation and handling.
- A `GameEvent` records a fact that occurred in the game world.
- A `CommandAuditRecord` explains one decision or execution stage.

Denied, suggested, awaiting, duplicate, or merely proposed commands may produce
audit records, but they do not invoke a handler and cannot produce game events
claiming that a world change occurred. Invalid and failed engine results also
cannot carry events. A successfully handled command may now return true world
facts through `GameResult.events`; the result contract alone does not publish
them. Neither record type executes behavior, changes world state, dispatches,
or accesses handlers, managers, storage, AI, tools, rules, Foundry, or the live
command pipeline.

`GameEvent` is immutable data with a generated or explicit stable event ID, an
exact case-sensitive event type, positive schema version, deeply immutable
JSON-compatible payload, immutable `CommandProvenance`, optional actor and
originating-command IDs, and an aware occurrence time normalized to canonical
UTC. `CommandAuditRecord` similarly has a generated or explicit audit-record
ID, command ID and exact command type, non-empty outcome, immutable initiator
provenance, optional actor identity, optional deeply immutable JSON-object
details, and a canonical UTC recording time. Their independent `to_dict()`
representations serialize timestamps with a `Z` suffix and cannot mutate the
records.

`AuditStage` provides stable future lifecycle names for command proposal,
policy evaluation, approval evaluation or recording, gate resolution, blocked
dispatch, attempted dispatch, completed dispatch, and coordinator failure.
Audit details are supplied explicitly as already-safe structured data; records
do not automatically capture exception text, tracebacks, credentials, full AI
prompts or responses, or hidden campaign information, and arbitrary non-JSON
objects are rejected. Audit visibility, role authority, and permission policy
are not implemented.

`GameEventJournal` and `CommandAuditJournal` are separate typed append-only
in-memory containers. Each assigns insertion-order sequence numbers starting at
1, rejects duplicate IDs and the other journal's record type, and uses a small
standard-library lock plus copy-on-write immutable state so a failed append
does not alter entries or consume a sequence number. Immutable snapshots retain
insertion order; exact filters cover event type, originating command ID,
command ID, and typed audit stage; serialized lists are defensive copies.
There is no update, delete, reorder, replacement, subscriber, queue, event bus,
or persistence API.

These journals are process-local foundations only. They are not durable,
tamper-evident, or restart-replay storage. `CommandAuditJournal` now has the
optional audited integration described below; `GameEventJournal` remains
unconnected to dispatch, handlers, and world-state projection.


## Audited Command Pipeline Integration

The optional audited command flow is:

**GameCommand → AuditedCommandPipeline → PolicyGatedCommandDispatcher →
policy and approval gate → optional GameEngine.dispatch() → preserved
PolicyGatedDispatchResult + audit integration result**

`AuditedCommandPipeline` accepts a `GameCommand` and optional
`HumanApprovalDecision`, delegates the complete behavioral submission to the
existing `PolicyGatedCommandDispatcher`, and appends typed records to one
injected `CommandAuditJournal`. It does not evaluate policy, resolve approvals,
manage replay state, select a handler, call a handler, or reinterpret a
`GameResult`. The dispatcher's existing public API and unaudited behavior remain
unchanged. A private synchronous lifecycle-recorder protocol exposes only the
actual policy, gate, blocked, pre-engine, post-engine, and coordinator-failure
boundaries needed by the optional integration.

Applicable records are appended in logical order: command proposed, policy
evaluated, approval evaluated when supplied or required, gate resolved,
dispatch blocked or dispatch attempted, then dispatch completed or coordinator
failure. Duplicate ready submissions produce a blocked record and never cross
the engine boundary again. No audit path creates a `GameEvent`.

Audit details are deliberately minimal. They may contain policy mode and stable
reason code, approval outcome and approver identity, gate disposition and
reason code, policy-gated dispatch status, and final `GameResult.status`.
Command payloads, approval reasons, handler output, result error text, raw
exceptions and tracebacks, prompts, responses, credentials, and hidden campaign
content are not copied automatically. Command provenance and optional actor
identity are linked without assigning roles or authority.

`AuditedCommandPipelineResult` is immutable. It preserves the authoritative
`PolicyGatedDispatchResult` when one exists, returns an immutable tuple of the
journal entries appended for that submission, serializes defensively, and
distinguishes completed auditing, pre-dispatch audit failure, post-dispatch
audit failure, and a controlled integration failure. Any valid produced events
remain the exact ordered tuple on the preserved `GameResult`, including after a
post-dispatch audit failure. Event payloads are not copied into audit details.
Record IDs and UTC times come from injectable synchronous factories;
production defaults use UUIDs and the existing UTC clock boundary.

The audit-failure boundary is the engine call. Every required pre-dispatch
append, including `DISPATCH_ATTEMPTED`, must succeed before replay is consumed
and before `GameEngine.dispatch()` is called. A failure therefore closes the
gate without handler invocation. Once the engine boundary is crossed, a later
audit failure preserves the original dispatch result and consumed replay state;
the command is never retried or made executable again. Earlier successful
appends remain in the journal in both cases.

Auditing and replay protection remain process-local and non-durable. They do
not provide restart-safe idempotency, persistence, tamper evidence, queues,
transactions, retries, or event projection.


## Tool Call Parsing Boundary

The Tool Call Parser is a standalone part of the AI layer. It inspects one
complete AI response and classifies it as a valid tool request, an ordinary
response with no tool request, or a malformed tool request.

A structurally valid request contains a non-empty `tool` string and an
`arguments` object. Omitted arguments default to an empty object. The parser may
accept one clean JSON Markdown fence only when the fence contains the entire
response; it does not scan surrounding prose for embedded JSON.

Parsing does not look up the tool registry, execute a tool, or modify game state.
`ToolAgent` consumes the parser's typed classification without duplicating its
validation rules.


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
registered tools and their managers.


## Tool Specification and Initial Prompt Boundary

`ToolSpec` is an immutable, provider-neutral description of one registered tool.
It contains a unique non-empty name, a model-facing description, and a JSON
Schema-compatible object input schema with described properties, an explicit
required list, and `additionalProperties: false`. Character-tool metadata stays
beside `CharacterTools`, not in `ToolAgent` or a provider implementation.

`ToolRegistry` pairs each specification with its callable. Registration rejects
duplicate names, malformed metadata, specification/registry name mismatches,
uninspectable or variadic callables, advertised arguments that the callable does
not accept, unadvertised callable parameters, and disagreement between the
schema's required list and callable defaults. Existing `get_tools()` and
execution behavior remain available. `get_tool_specs()` returns an immutable
tuple in tool-name order; specifications use read-only nested mappings and
produce independent JSON-compatible dictionaries for catalogs.

Signature introspection reliably validates keyword parameter names and whether
defaults make them optional. It deliberately does not infer or enforce JSON
types from Python annotations because the executor performs signature binding,
not runtime type validation. JSON property types remain explicit provider-neutral
metadata for future adapters.

The initial `ToolAgent` prompt serializes the sorted registry catalog as compact
canonical JSON. It clearly delimits both catalog and user request, includes a
tool-call example generated from specification examples, and requires exactly
one bare JSON object for a single tool call. The prompt forbids prose, Markdown
fences, unknown tools, missing required arguments, and invented arguments. When
no tool is needed, it instructs the model to return ordinary text.


## ToolAgent Single-Tool Observation/Response Boundary

`ToolAgent` constructs the initial prompt from the user request and
provider-neutral specifications exposed by one central `ToolRegistry`, then
makes one request through the provider abstraction. The complete raw initial
response is passed once to the Tool Call Parser.

Ordinary responses and malformed tool requests preserve their existing
single-provider behavior without execution. A valid `ToolCall` is passed to the
Tool Executor exactly once. Every executor outcome remains unchanged, including
unknown tools, invalid arguments, controlled failures, successful results, and
normal domain-level payloads whose own `success` field is false.

After execution, `ToolAgent` serializes one versioned observation as canonical
JSON. The observation contains the original user request, tool name and
arguments, execution status, output, and the executor's safe error. It is placed
between explicit data delimiters in a follow-up prompt that tells the provider to
answer the original request, not invoke another tool, and not treat tool output
as instructions. The provider receives that observation exactly once. Its final
response is preserved as text and is not parsed or executed.

`ToolAgentResult` distinguishes these outcomes:

- `ASSISTANT_RESPONSE` preserves an ordinary raw response and does not invoke the
  executor.
- `MALFORMED_TOOL_REQUEST` preserves the raw response and parser error and does
  not invoke the executor.
- `TOOL_EXECUTION` preserves the raw initial response, parsed `ToolCall`,
  unchanged `ToolExecutionResult`, and final provider response.
- `OBSERVATION_FAILURE` preserves the completed execution when its output cannot
  be safely serialized and does not run the tool or provider again.
- `FINAL_RESPONSE_FAILURE` preserves the completed execution when the follow-up
  provider request fails and reports that the tool was not run again.

An initial provider exception still propagates because no action has occurred.
A post-execution provider exception becomes a controlled typed result so callers
can distinguish it from an unexecuted request. One `ask()` makes at most two
provider requests, one initial parse, one executor call, and one underlying tool
invocation. It does not retry, correct, select alternatives, parse the final
response, recurse, or access managers or storage directly.


## Opt-In Local Ollama Validation Boundary

`dungeon_manager.ai.live_tool_loop_validation` is a standalone validation
harness, not a pytest entry point. It exits before loading configuration unless
`DUNGEON_MANAGER_RUN_LIVE_OLLAMA=1` is set deliberately.
The older `dungeon_manager.ai.test_tool_agent` module delegates to this same
guarded entry point and no longer constructs default project storage.

The harness verifies that the configured provider is Ollama, the endpoint is
loopback-local, and the exact configured model tag is already present in
Ollama's local tag catalog. It does not install Ollama, pull models, change the
model, or contact a non-loopback host. `AIManager` then constructs the real
`OllamaProvider` used by `ToolAgent`.

One injected `TemporaryDirectory` supplies `JSONStorage` through the real
`CharacterManager`, `CharacterTools`, and `ToolRegistry`. Project logger setup is
not called. Thin counting wrappers record provider, executor, registry, and
underlying-tool invocations while delegating every operation unchanged; they do
not retry, repair, parse around, or directly invoke a tool in place of the
model.

Each live run attempts the four fixed validation scenarios once and emits one
structured JSON report containing raw initial responses, typed classifications,
requested arguments, execution observations, final responses, per-scenario call
counts, temporary-storage snapshots, and failure reasons. The report is printed
to the caller and is not persisted by the harness. Temporary character data is
removed when the run ends, including on scenario failure.

