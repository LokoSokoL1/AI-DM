# Dungeon Manager Documentation Index

## Authority

### Evidence flow

> Research
> ↓
> Design discussion and acceptance
> ↓
> Game Design Document
> ↓
> Vertical Slice Specifications
> ↓
> Architecture
> ↓
> Project Plan
> ↓
> Project Status

### Documentation authority

- Research is the source of evidence.
- The accepted GDD is authoritative for product philosophy and decisions.
- Accepted vertical-slice specifications define bounded executable behaviour.
- Accepted phase design specifications define approved product behavior and
  acceptance criteria, not implemented functionality.
- Architecture describes implemented technical structure and explicitly labelled future candidates.
- Project Plan defines accepted sequence.
- Project Status reports verified state.
- Research never automatically changes any downstream authority.
- The current local working tree and verified tests remain authoritative for implementation facts.

For implementation facts, use this order:

1. Current local working tree and its verified implementation.
2. [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md).
3. Frozen Section 1 in [GDD.md](GDD.md).
4. Latest verified tests and completed-milestone handoffs available in the repository or current Codex thread.
5. GitHub develop.
6. Existing ChatGPT Library copies.

Old attachments, conversation recollections, prompt drafts, and pasted snapshots are not product authority.

## Canonical product and design documentation

- [GDD.md](GDD.md) — frozen core vision and general design philosophy. Together with the slice GDD, this is the complete current GDD.
- [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md) — frozen executable vertical-slice behavior and seven-milestone sequence.
- [LOW_FIDELITY_INTERFACE_SPEC_V1.md](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md)
  — formally accepted Phase 2 low-fidelity interface design baseline. The
  project owner accepted the exact draft with SHA-256
  `21A77F35DC5606B49306F85691F55F17FCABDB71E374BBBA63F869739A640AA3`
  on 2026-07-29. It approves product behavior and acceptance criteria, not
  implementation; the interface and Foundry integration remain unimplemented,
  and all ten explicitly deferred implementation decisions remain open. Future
  technical design and implementation must conform to the baseline or record an
  explicit revision.

## Canonical technical documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — implemented modules, dependency direction, command/event/projection flow, state ownership, restart, and failure behavior.
- [README.md](README.md) — concise project orientation and entry points.

## Planning and status documentation

- [PROJECT_PLAN.md](PROJECT_PLAN.md) — accepted milestone order, completion state, and exact next action.
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — verified behavior, coverage, tests, limitations, and checkpoint scope.

## Research documentation

Research is formal evidence from tabletop play. It informs design but is not implementation authority and does not automatically change the GDD, architecture, plan, status, or code.

- [Research overview](docs/research/README.md)
- [RI-001 — Trust Through Persistence, Perspective, and World Independence](docs/research/RI-001.md)

Research Iterations, including RI-001, remain formal research documents and retain a traceability chain:

> Observation
> ↓
> Design Principle
> ↓
> Requirement
> ↓
> Architecture
> ↓
> Feature
> ↓
> Validation

Research observations do not become implementation claims until separately accepted, scheduled, and implemented.

## Documentation navigation

- [GDD.md](GDD.md)
- [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md)
- [LOW_FIDELITY_INTERFACE_SPEC_V1.md](docs/design/LOW_FIDELITY_INTERFACE_SPEC_V1.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [PROJECT_PLAN.md](PROJECT_PLAN.md)
- [PROJECT_STATUS.md](PROJECT_STATUS.md)

## Operational and developer instructions

Repository-wide operational guidance, including the current-state authority safeguard, is defined in [AGENTS.md](AGENTS.md). Deterministic commands and live-validator boundaries are summarized in README.md and PROJECT_STATUS.md.

## Historical or obsolete material

- CHANGELOG.md — empty legacy placeholder; not canonical status.
- DESIGN.md — empty legacy placeholder; superseded by GDD.md and the slice GDD.
- IDEAS.md — empty legacy placeholder; not accepted design or plan.

These tracked placeholders are retained to preserve repository history. They must not override canonical documents.
