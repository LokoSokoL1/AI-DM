\# Dungeon Manager Project Status



\## Current Phase

Game Engine Foundation



\## Verified Project Setup



\- Git repository created

\- Develop branch created

\- Initial folder structure created

\- GitHub connection established

\- Initial documentation created

\- Gitignore configured



\## Current Milestone



Durable Event Journal Persistence Foundation. `EventJournalStore` is an
explicit path-bound SQLite boundary for immutable sequenced
`GameEventJournalEntry` batches. It stores journal identity, format, and schema
metadata; uses WAL plus full synchronous SQLite transactions; rejects stale
tails and duplicate IDs; and exposes complete immutable snapshots only after
strict canonical event, sequence, identity, and digest validation. It remains
standalone: it neither replaces JSON entity storage nor integrates with the
pipeline, startup hydration, audit persistence, or world-state persistence.



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

\- The Game Engine Foundation started from a clean 74-test deterministic
baseline at the expected commit.

\- The focused engine suite passes 58 tests covering command construction and
IDs, all provenance sources, actor separation, nested immutability, defensive
serialization, invalid structures, result invariants, successful and unknown
dispatch, exact handler resolution, registration validation, single invocation,
no retry, exception conversion, invalid or mismatched handler results, immutable
registration snapshots, and dependency isolation.

\- The complete deterministic pytest suite passes 132 tests after the engine
foundation was added.

\- The five isolated legacy smoke modules still pass through direct `python -m`
execution using only temporary storage.

\- Before/after paths, sizes, modification times, and SHA-256 hashes confirm
that the milestone's focused tests, complete deterministic suite, and legacy
smoke modules leave normal `data/` and `logs/` unchanged.

\- The focused automation policy and approval module passes 43 tests covering
all modes and initiators, exact precedence, safe default and unknown-capability
denial, case sensitivity, payload self-authorization resistance, immutable
configuration, stable decisions, approval validation, every gate disposition,
invalid and mismatched approvals, determinism, and non-dispatch behavior.

\- The complete focused engine suite passes 102 tests, including a dependency
test that limits the automation module to the command and immutable-JSON
boundaries inside the standard-library-only engine package.

\- The complete deterministic pytest suite passes 176 tests after the
automation policy and approval boundary was added.

\- The five isolated legacy smoke modules still pass through direct `python -m`
execution using only temporary storage.

\- Before/after paths, sizes, modification times, and SHA-256 hashes confirm
that policy tests, the complete deterministic suite, and legacy smoke modules
leave normal `data/` and `logs/` unchanged.

\- The focused policy-gated dispatcher and dependency suite passes 36 tests
covering every dispatch/no-dispatch outcome, internal policy evaluation,
approval rejection, caller non-injection, preserved engine statuses, domain-
negative output, replay and re-entry protection, immutable snapshots,
controlled exceptions, serialization, result invariants, and dependency
isolation.

\- The complete focused engine suite passes 136 tests after the coordinator and
combined result were added.

\- The complete deterministic pytest suite passes 210 tests after the
Policy-Gated Command Dispatch milestone was added.

\- The focused game-event, command-audit, journal, and dependency suite passes
61 tests covering generated and explicit IDs, deterministic UTC time,
structural validation, deep immutability, defensive serialization, typed audit
stages, sequencing, insertion order, duplicate rollback, immutable snapshots,
exact filtering, wrong-type rejection, distinct journals, and dependency
isolation.

\- The complete focused engine suite passes 194 tests after the game-event and
command-audit foundations were added.

\- The complete deterministic pytest suite passes 268 tests after the Game
Event Foundation and Audit Records milestone was added.

\- The focused audited-pipeline module passes 23 tests covering automatic and
approved dispatch, awaiting approval, suggestions, denials, unknown
capabilities, invalid and mismatched approvals, duplicate attempts, controlled
engine results, domain-negative output, sanitized details, deterministic IDs
and UTC times, pre- and post-dispatch append failures, partial history, replay
consumption, no retries, immutable results, no game events, and unaudited
compatibility.

\- The complete focused engine suite passes 218 tests after the audited command
pipeline and its dependency boundary were added.

\- The complete deterministic pytest suite passes 292 tests after the Audited
Command Pipeline Integration milestone was added.

\- The focused event-producing handler module passes 26 tests covering legacy
empty results, one and multiple ordered events, immutability, defensive
serialization, invalid collections and event values, linkage and duplicate-ID
validation, engine failure isolation, policy-blocked paths, automatic and
approved preservation, duplicate suppression, audited preservation,
post-dispatch audit failure, sanitized audit details, and confirmation that no
event-journal append occurs.

\- The complete focused engine suite passes 245 tests after the event-producing
handler result contract was added.

\- The complete deterministic pytest suite passes 319 tests after the
Event-Producing Command Handler Contract milestone was added.

\- Atomic event-journal batch coverage verifies one and multiple ordered
events, contiguous sequences, empty batches, invalid values, duplicate IDs
within and against the journal, failure rollback without sequence gaps,
non-interleaving concurrent batches, immutable snapshots, and backward-
compatible single append.

\- Event-publication integration coverage verifies automatic and approved
dispatch, eventless and controlled engine results, every blocked status,
duplicate suppression, explicit journal injection, publication failure with
preserved dispatch and replay state, post-dispatch audit independence,
sanitized failure audit details, immutable result snapshots, defensive JSON
serialization, and no execution or publication retry.

\- The focused journal, audited-pipeline, event-producing handler, publication,
and dependency suite passes 101 tests.

\- The complete focused engine suite passes 275 tests after Event Journal
Publication Integration was added.

\- The complete deterministic pytest suite passes 349 tests after Event Journal
Publication Integration was added.

\- The focused world-state projection and dependency suite passes 65 tests
covering immutable and defensive state, full replay, incremental projection,
strict reducer registration, exact event/schema resolution, complete sequence
and duplicate validation, ordered single invocation, atomic controlled
failures, sanitized diagnostics, publication separation, and dependency
isolation.

\- The complete focused engine suite passes 334 tests after the World State
Projection Foundation was added.

\- The complete deterministic pytest suite passes 408 tests after the World
State Projection Foundation was added.

\- The focused world-state projection-pipeline and dependency suite passes 30
tests covering explicit synchronized and mismatched starts, eventless results,
one and multiple ordered entries, incremental commands, blocked and duplicate
submissions, publication and reducer failures, unknown event/schema handling,
state preservation, replay consumption, out-of-sync blocking, later audit
failure, immutable snapshots, defensive serialization, sanitization,
concurrency, re-entrancy, no retry, no rebuild, and strict dependencies.

\- The complete focused engine suite passes 357 tests after World State
Projection Pipeline Integration was added.

\- The complete deterministic pytest suite passes 431 tests after World State
Projection Pipeline Integration was added.

\- The five isolated legacy smoke modules still pass through direct `python -m`
execution using only temporary storage.

\- Exact before/after paths, sizes, modification times, and SHA-256 hashes
confirm that baseline and final verification leave normal `data/` and `logs/`
unchanged.

\- The focused world-state recovery and dependency suite passes 32 tests
covering synchronized no-op, catch-up, full rebuild, explicit bases, stale and
out-of-sync replacement, projector failures, atomic state/health preservation,
exact journal-tail completion, reducer ordering, journal-change detection,
dispatch restoration, incremental continuation, concurrency, re-entry,
sanitization, serialization, authoritative-snapshot input, and strict
dependencies.

\- The complete focused engine suite passes 381 tests after World State
Projection Recovery and Rebuild was added.

\- The complete deterministic pytest suite passes 455 tests after World State
Projection Recovery and Rebuild was added.



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

\- A standard-library-only `dungeon_manager.engine` package with immutable
`GameCommand`, `CommandProvenance`, `CommandSource`, `GameResult`, and
`GameResultStatus` representations

\- Deeply immutable JSON-compatible command payloads and result output with
independent transport/logging dictionaries

\- A synchronous `GameEngine` that validates exact handler registrations,
exposes an immutable sorted command-type snapshot, dispatches one handler once,
and converts unknown commands, invalid handler results, and raised exceptions
to controlled linked results

\- An implemented trust boundary in which per-capability optional automation
evaluates provenance before dispatch; future global trust levels are presets
only, command creation is not authorization, and AI must earn trust

\- Immutable `AutomationMode`, per-capability rules, and `AutomationPolicy`
configuration with exact capability/initiator precedence, broader configured-
capability defaults, case-sensitive matching, safe denial, and defensive JSON
serialization

\- Immutable linked `PolicyDecision` and `HumanApprovalDecision` records with
stable reason codes, human-only approval provenance, and no roles, permission
authority, persistence, or executable behavior

\- A pure `resolve_automation_gate()` boundary returning `READY`,
`AWAITING_APPROVAL`, `SUGGEST_ONLY`, `DENIED`, or fail-closed `INVALID` without
calling the dispatcher or any handler

\- A synchronous `PolicyGatedCommandDispatcher` that internally evaluates its
configured immutable policy, resolves optional human approval, calls only
`GameEngine.dispatch()` for a `READY` disposition, and never accepts a caller-
supplied policy decision, automation mode, capability, or gate disposition

\- An immutable `PolicyGatedDispatchResult` that distinguishes dispatched,
awaiting, suggestion-only, denied, invalid, duplicate, and controlled
coordinator-failure outcomes while preserving the exact controlled
`GameResult` for attempted dispatch

\- Process-local per-coordinator replay protection that records a ready command
ID before engine dispatch, blocks repeated and re-entrant attempts, exposes only
an immutable snapshot, and deliberately provides no restart durability

\- Immutable `GameEvent` world facts with generated or explicit IDs, exact
case-sensitive event types, positive schema versions, immutable payload and
provenance, optional actor and originating-command linkage, and canonical UTC
occurrence times

\- Immutable `CommandAuditRecord` lifecycle traces with generated or explicit
IDs, command linkage, typed `AuditStage`, non-empty outcomes, immutable
initiator provenance and optional actor identity, optional safe structured
details, and canonical UTC recording times

\- Separate typed `GameEventJournal` and `CommandAuditJournal` in-memory
append-only containers with atomic sequence assignment from 1, duplicate-ID
rejection without sequence gaps, insertion-ordered immutable snapshots, exact
filters, and defensive serialized copies

\- An optional synchronous `AuditedCommandPipeline` that delegates all behavior
to `PolicyGatedCommandDispatcher` and records ordered proposal, policy,
applicable approval, gate, blocked or attempted dispatch, completion, and
coordinator-failure stages

\- An immutable `AuditedCommandPipelineResult` that preserves the authoritative
policy-gated result when available, returns immutable appended-entry snapshots,
serializes defensively, and distinguishes completed, pre-dispatch failure,
post-dispatch failure, and controlled integration outcomes

\- Fail-closed pre-dispatch auditing before replay consumption and the engine
boundary, plus post-dispatch result/replay preservation with no retry; both
audit journals and replay state remain in-memory and non-durable

\- An additive `GameResult.events` contract that defaults to an empty tuple,
preserves valid `GameEvent` objects in handler order, validates exact
originating-command linkage and unique per-result event IDs, serializes
defensively, and keeps all controlled engine failures event-free

\- Unchanged preservation of valid handler-produced events through the game
engine, automatic or approved policy-gated dispatch, audited dispatch, and
post-dispatch audit failure

\- Atomic ordered `GameEventJournal.append_batch()` publication with complete
pre-mutation validation, within-batch and existing-ID rejection, contiguous
sequence assignment, empty no-op behavior, non-interleaving concurrent batches,
and the preserved single-event append API

\- Explicit `GameEventJournal` injection into the existing audited pipeline,
with publication limited to preserved `DISPATCHED` result events and typed
`NOT_APPLICABLE`, `NO_EVENTS`, `PUBLISHED`, or `FAILED` disposition

\- Immutable successful publication-entry snapshots, safe publication errors,
defensive serialization, independently successful post-dispatch audit and event
journal appends, and replay-preserving no-retry publication failure

\- Immutable provider- and rules-neutral `WorldState` derived data with deeply
frozen JSON-object content, defensive serialization, and non-negative last
successfully applied journal sequence starting at zero

\- A synchronous `WorldStateProjector` with exact case-sensitive event-type and
schema-version reducer registration, strict two-parameter callable validation,
duplicate rejection, and immutable deterministically sorted snapshots

\- Atomic full replay and incremental projection that materialize and validate
the entire entry snapshot, require contiguous next sequences and unique batch
event IDs, resolve all reducers first, and apply each event once without retry,
skip, fallback, or partial-state exposure

\- Immutable typed projection results distinguishing success, invalid state or
journal input, unknown event type, unsupported schema version, invalid reducer
output, and reducer failure with safe payload-free diagnostics

\- Explicit separation from event publication and the audited command pipeline;
projection remains pure, process-local derived computation with only test
reducers and no automatic execution

\- An explicit process-local `WorldStateHolder` that accepts one initial
immutable state, exposes immutable snapshots and payload-free synchronization
health, commits only complete successful projections, and provides no public
mutation, rollback, recovery, or rebuild API

\- Construction-time and pre-dispatch journal-tail agreement checks that mark
projection out of sync and fail closed before handlers, replay consumption,
event publication, or reducers can run

\- Explicit projector and state-holder dependencies in `AuditedCommandPipeline`,
with projection limited to the authoritative immutable entries returned by one
successful event-journal batch publication

\- A typed `NOT_APPLICABLE`, `UNCHANGED`, `PROJECTED`, `FAILED`, or `UNAVAILABLE`
projection disposition with only controlled status/reason/error and sequence
metadata; complete world-state data remains available only from the holder

\- One synchronous outer coordination boundary that serializes complete
pipeline submissions, preserves journal/projection order without lost updates,
and rejects same-thread re-entrant invocation before dispatch without deadlock

\- Non-transactional failure ordering in which publication failure skips
projection, projection failure preserves events/replay and the previous state
while blocking later dispatch, and successful event/state updates survive a
later audit failure without rollback or retry

\- An explicit trusted/operator `AuditedCommandPipeline.recover_world_state()`
boundary with typed `CATCH_UP` and `FULL_REBUILD` strategies; catch-up uses only
entries after the current committed sequence, while full rebuild requires a
caller-supplied immutable sequence-zero base and replays the complete journal

\- Immutable recovery results distinguishing `RECOVERED`, `NO_ACTION`,
`INVALID_REQUEST`, `PROJECTION_FAILURE`, `JOURNAL_CHANGED`, `UNAVAILABLE`, and
`COORDINATOR_FAILURE` with sequence-only, controlled projector, and safe error
metadata

\- Recovery shares the pipeline's synchronous non-reentrant coordination lock,
captures one immutable authoritative journal snapshot, verifies its tail before
commit, and replaces state plus synchronization health once only after complete
projection success

\- Failed recovery preserves committed state and appropriate existing health;
successful recovery reaches the captured journal tail and clears out-of-sync
health without dispatch, policy, approval, replay use, publication, audit
records, retries, skips, or fallback



\## Partially Implemented Functionality



\- Ollama communication has one successful local live-validation result; live
model behavior remains nondeterministic and intentionally outside normal tests

\- The tool layer currently exposes only character create/load operations

\- Foundry configuration exists, but Foundry integration is not implemented



\## Planned Functionality



\- Durable Event Journal Pipeline Integration and Startup Hydration; the new
SQLite store remains standalone and current pipeline publication, in-memory
journal hydration, audit persistence, and world-state persistence remain out of
scope

\- Any later multi-step agent loop

\- Prompt management and context handling beyond current prompt construction

\- Rules-system, Foundry VTT, management-interface, and advanced-feature roadmap
work described in `PROJECT_PLAN.md`



\## Next Milestone



**Durable Event Journal Pipeline Integration and Startup Hydration**. It has
not started; it must integrate the existing durable store deliberately without
adding migrations, repair, retries, gameplay rules, UI, or Foundry integration.

