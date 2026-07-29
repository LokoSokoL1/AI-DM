# Dungeon Manager Phase 2 M1 Implementation Task

We are continuing development of Dungeon Manager, a modular local AI-powered
tabletop RPG engine designed to work with Foundry VTT.

This task runs from the current local repository at `E:\Dungeon Manager`. The
repository is `LokoSokoL1/AI-DM`, and the local checkout is authoritative. Do
not use automatically attached files, historical snapshots, ChatGPT Library
copies, earlier prompts, or chat recollections to determine the current
implementation state.

Implement only **Phase 2 M1 — Client-Neutral Authority and Operation
Contracts**. Do not begin M2 or any later Phase 2 milestone.

## Accepted decisions and scope

The project owner accepted on 2026-07-29:

- **D6:** the ports-and-adapters ownership direction.
- **D10:** the contract-first bounded Phase 2 implementation sequence.

M1 must establish only the minimum client-neutral authority and operation
contracts needed to represent the existing controlled fixture and support the
next bounded milestones. It must not prematurely finalize detailed contracts or
behavior belonging to later permission, transport, Foundry, multiplayer, save,
branch, checkpoint, snapshot, restoration, synchronization, or reconciliation
milestones.

The remaining eight deferred implementation decisions are still open. Do not
silently select any of them. The later milestone sequence remains revisable
through an explicit accepted decision.

## Repository safety and preflight

Before editing:

1. Verify repository identity, local path, branch, HEAD, origin, upstream
   relationship, divergence, and Git status.
2. Confirm the branch is `develop` and the working tree is clean.
3. Read the root `AGENTS.md` and every applicable nested `AGENTS.md`.
4. Read the current repository versions of:
   - `README.md`
   - `ARCHITECTURE.md`
   - `DOCUMENTATION.md`
   - `GDD.md`
   - `FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md`
   - `PROJECT_PLAN.md`
   - `PROJECT_STATUS.md`
   - `docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md`
   - `docs/research/README.md`
   - `docs/research/RI-001.md`
5. Verify that the canonical documentation records D6 and D10 as accepted, M1
   as the next approved but unstarted milestone, the other eight decisions as
   open, and the explicit minimum-contract constraint above.
6. Inspect the complete current repository structure and all production code,
   tests, fixtures, persistence code, composition roots, dependency checks,
   public runtime paths, and AI/tool boundaries relevant to M1.
7. Distinguish general reusable mechanisms from behavior bounded to the
   controlled fixture.

If the repository identity, branch, working-tree state, applicable instructions,
canonical decision record, or expected project structure differs, stop and
report the discrepancy without editing.

Do not pull, fetch, switch branches, commit, push, create a pull request, modify
GitHub, modify ChatGPT Library, invoke Foundry, or invoke Ollama.

## Objective

Add the smallest coherent client-neutral contract and application boundary that
can:

1. represent the identities and authoritative operation progress already
   present in the controlled fixture;
2. expose the controlled fixture through one in-process headless client-neutral
   façade without changing its mechanical behavior or publication order;
3. distinguish authoritative mechanical outcomes from durable publication,
   process-local publication, projection, synchronization, and transient
   presentation;
4. carry stable operation correlation across a caller retry or reconstruction
   without claiming that durable cross-process idempotency is implemented;
5. report supported, unsupported, and unavailable capabilities explicitly and
   fail closed;
6. preserve the accepted ports-and-adapters dependency direction.

Every new public contract must be required by the controlled-fixture façade or
by a concrete M1 invariant. Do not introduce speculative DTO catalogs for later
milestones.

## Required ownership boundaries

Preserve these accepted ownership rules:

- The existing deterministic engine remains authoritative for validated
  mechanical actions and facts.
- Durable event history remains authoritative after confirmed commit.
- AI components remain non-authoritative clients.
- The M1 contract and application layers must be client-neutral and must not
  import Foundry, D&D 5e, provider, tool, UI, or transport implementations.
- Permission-filtered presentation must remain conceptually separate from
  objective world state, but M1 must not implement the permission model.
- Foundry and D&D 5e remain future dedicated edge adapters.
- Durable operation identity belongs at the application/persistence boundary,
  but M1 must not add a speculative general outcome ledger unless the bounded
  implementation evidence proves it is required for M1.
- The current `CampaignRuntime` and controlled-round runtime remain controlled
  fixture composition paths, not general campaign or D&D services.

## In-scope contracts

Design exact names and module placement according to current repository
conventions. Keep the contract surface no broader than needed for the
controlled fixture. At minimum, M1 needs:

- immutable, validated, client-neutral references for the existing campaign,
  scene, actor, command, event, and caller-operation identities that cross the
  new boundary;
- a stable caller-supplied operation identity or correlation value, kept
  distinct from authoritative command and event identity;
- an explicit capability descriptor that can state supported, unsupported, or
  currently unavailable without causing mutation;
- a typed operation result/view that cannot conflate:
  - accepted or rejected submission;
  - authoritative mechanical success or failure;
  - durable event commitment;
  - process-local event publication;
  - projection and synchronization state;
  - optional transient presentation;
- sanitized client-facing diagnostics that do not expose raw exceptions,
  tracebacks, credentials, prompts, hidden payloads, storage paths, or provider
  internals;
- narrow application ports and one in-process headless façade sufficient to
  inspect the controlled fixture and represent its existing selection and
  controlled-round outcomes through the new contracts.

Use existing immutable engine types and results where they already satisfy the
boundary. Add adapters or mappings instead of duplicating domain authority.
Do not change existing authoritative ordering merely to simplify presentation.

## Side-effect and compatibility requirements

- Neutral inspection and capability discovery must be side-effect-free.
- Merely constructing a client request or contract must not authorize or
  execute a command.
- Unknown contract versions, identity kinds, capability keys, or operation
  states must fail closed.
- The façade must preserve existing fixture validation, command gating,
  durable-before-local publication, projection, synchronization, dice,
  narration eligibility, and restart behavior.
- Existing public composition paths must remain behaviorally compatible unless
  a narrowly justified additive adaptation is required.
- A client-provided role, label, actor name, or presentation field must never
  become proof of authority.
- M1 may describe an unavailable future capability, but it must not claim that
  the capability is implemented.

## Explicit non-goals

Do not implement or finalize:

- participant authentication, roles, permissions, actor assignment, speaker
  grants, visibility filtering, or preference ownership;
- HTTP, WebSocket, IPC, listeners, schemas for a selected transport, pairing,
  credentials, remote routing, multiplayer, host transfer, leases, or fencing;
- Foundry modules, hooks, chat intake, sidebar replacement, Manager UI, world
  discovery, synchronization, or D&D 5e document translation;
- general campaign discovery, campaign browsing, arbitrary actors, general
  D&D actions, or new mechanical behavior;
- named saves, checkpoints, branches, snapshots, restoration, reconstruction,
  migrations, or reconciliation;
- provisional offline-change capture;
- durable general request/outcome deduplication, unless a minimal persistence
  abstraction is unavoidable for M1 and can be added without choosing D3, D4,
  D5, D8, or D9;
- ToolAgent-to-engine integration, AI permission interpretation, provider
  retries, narration persistence, or narration replay;
- UI styling, streaming, background workers, or network dependencies;
- changes to the accepted 42 interface acceptance criteria.

If implementation reveals that M1 requires one of these decisions, stop and
report the smallest blocking decision instead of selecting it.

## Deterministic verification

Add focused tests using the current repository’s existing approach. Cover at
least:

- immutability, validation, defensive copying, equality, and deterministic
  serialization for every externally visible M1 contract;
- stable separation of caller operation identity, command identity, and event
  identity;
- capability inspection with no files, events, commands, dice, provider calls,
  or state mutation;
- explicit supported, unsupported, unavailable, and unknown-capability
  behavior;
- mapping of successful, rejected, input-required, failed, durable-only,
  locally published, projected, synchronized, and presentation-failed paths
  without status conflation;
- sanitized diagnostics under representative failures;
- one controlled-fixture manual journey and one automatic journey represented
  through the new façade with the exact existing authoritative ordering;
- restart or reconstruction of the client-neutral view from current durable
  facts without rerolling, redispatch, append, tool execution, provider
  execution, or repair;
- dependency-direction enforcement preventing imports of Foundry, D&D 5e, UI,
  transport, provider implementations, ToolAgent, tool registry/executor,
  legacy managers, or Integrate AI into the new contract/domain layer;
- continued compatibility of the existing public controlled-fixture
  composition and acceptance journeys.

Inspect the deterministic test configuration first. Run tests with bytecode and
pytest-cache creation disabled. Do not run the live Ollama validator, Foundry,
browser automation, or any network-dependent test.

At minimum run:

1. the new focused M1 tests;
2. directly affected command, pipeline, projection, persistence, runtime,
   restart, narration, and dependency tests;
3. the complete deterministic suite with
   `dungeon_manager/ai/test_live_tool_loop_validation.py` excluded;
4. the five existing isolated smoke entry points.

Compare `data/` and `logs/` manifests before and after testing. Run
`git diff --check`. Confirm no unintended files or caches were created.

## Documentation

After implementation and successful verification, update only directly relevant
canonical documentation:

- `ARCHITECTURE.md`
- `PROJECT_PLAN.md`
- `PROJECT_STATUS.md`
- any M1-specific technical documentation that the repository’s conventions
  require

Record only implemented and verified behavior. Keep the other eight decisions
open, preserve the minimum-contract constraint, and name M2 only as the
provisional following milestone. Do not claim that any Foundry, permission,
transport, save, multiplayer, snapshot, or reconciliation capability exists.

## Final handoff

Report:

1. repository, path, branch, starting and ending HEAD, origin, upstream
   relationship, divergence, and initial/final Git status;
2. applicable `AGENTS.md` files and canonical documents inspected;
3. files changed;
4. the exact client-neutral contracts and ports added;
5. how the controlled fixture is exposed without changing authority or
   mechanics;
6. dependency and ownership invariants preserved;
7. every explicit non-goal preserved;
8. tests run and exact results;
9. `data/` and `logs/` comparison;
10. documentation updated;
11. any unresolved issue or evidence that should revise later milestones;
12. the provisional next milestone, **M2 — Identity, Permission, Assignment and
    Visibility Core**, without starting it;
13. final confirmation that nothing was committed, pushed, pulled, fetched, or
    changed on GitHub, ChatGPT Library, Foundry, or Ollama.

Stop after the M1 implementation handoff. Do not begin M2.
