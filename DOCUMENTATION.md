# Dungeon Manager Documentation Index

## Authority

When documents disagree, use this order:

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

## Canonical technical documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — implemented modules, dependency direction, command/event/projection flow, state ownership, restart, and failure behavior.
- [README.md](README.md) — concise project orientation and entry points.

## Planning and status documentation

- [PROJECT_PLAN.md](PROJECT_PLAN.md) — accepted milestone order, completion state, and exact next milestone.
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — verified behavior, coverage, tests, limitations, and checkpoint scope.

## Research documentation

No accepted Research Iteration document is present in the repository at this checkpoint. No research finding has been reconstructed from memory or from an external stale copy.

Any future accepted Research Iteration record should remain a formal research document and retain this chain:

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

Research observations do not become implementation claims until separately accepted and implemented.

## Operational and developer instructions

No repository AGENTS.md or separate operational handbook is present. Deterministic commands and live-validator boundaries are summarized in README.md and PROJECT_STATUS.md.

## Historical or obsolete material

- CHANGELOG.md — empty legacy placeholder; not canonical status.
- DESIGN.md — empty legacy placeholder; superseded by GDD.md and the slice GDD.
- IDEAS.md — empty legacy placeholder; not accepted design or plan.

These tracked placeholders are retained to preserve repository history. They must not override canonical documents.
