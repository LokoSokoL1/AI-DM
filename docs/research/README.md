# Dungeon Manager Research

## Purpose

Research observes competent human Dungeon Masters, AI Dungeon Masters, and players during real tabletop play and derives permanent design and architectural requirements for Dungeon Manager.

Research is evidence. It is not implementation planning. It is not bug tracking. It does not automatically change the GDD, architecture, plan, status, or implementation.

## Core question

Research asks:

> Why did this behaviour create or reduce player trust?

It does not ask:

> How do we make ChatGPT imitate it?

The objective is to identify permanent systems, boundaries, and design principles.

## Feature Justification Chain

> Observation
> ↓
> Analysis
> ↓
> Design Principle
> ↓
> Requirement
> ↓
> Architecture
> ↓
> Implementation
> ↓
> Validation

An observation is not complete until it supports either a design principle or a justified architectural requirement. Implementation still requires separate acceptance and scheduling.

## Three project layers

1. **Campaign** — the actual tabletop game.
2. **Research** — evidence derived from play.
3. **Architecture** — permanent systems accepted for implementation.

For example:

> Campaign: Toblen knew Brom's name without learning it.
> Research: Perspective leakage reduces player trust.
> Architecture candidate: perspective-isolated NPC knowledge with acquisition history and source provenance.

The architecture candidate remains a proposal until accepted through the GDD/design and planning process.

## Workflow during play

- Gameplay remains the visible priority.
- Research observation occurs silently and should not interrupt ordinary play.
- Analysis normally happens at the end of an adventuring day, a significant milestone, or when explicitly requested.
- Record positive behaviour worth preserving as well as failures.

Each Research Iteration contains:

1. Campaign Scope
2. Campaign State Snapshot
3. Observations
4. Analysis
5. Design Principles
6. Requirements
7. Architectural Impact
8. Validation
9. Trust Assessment
10. Newly Discovered Design Principles
11. Outstanding Research Questions
12. Traceability

## Confidence levels

- **Very High** — repeated independent observations or a conclusion supported by several distinct findings.
- **High** — repeated or strongly demonstrated, but still needs broader campaign validation.
- **Medium** — credible and useful, but based on limited situations or requiring validation across other campaigns, settlements, or NPC types.
- **Low** — preliminary or isolated; do not make a major architectural commitment from it alone.

Confidence may increase or decrease as later Research Iterations add evidence.

## Maturity levels

1. **Observation** — seen once; more evidence needed.
2. **Pattern** — repeated and likely genuine.
3. **Principle** — generalizes across situations and may enter the GDD.
4. **Architectural Requirement** — justifies a permanent system.
5. **Core Philosophy** — foundational enough that many systems derive from it.

Level 5 candidates already accepted in the GDD include Perspective Integrity, Trust as the North Star, World Independence, and Simulation Before Narration.

## Human DM cognitive order

1. **Current World State** — what objectively exists?
2. **Perspective** — what does each participant know, believe, remember, or misunderstand?
3. **Intent** — what is each participant trying to accomplish?
4. **Capability** — what can each participant actually do under the rules and circumstances?
5. **Resolution** — what happens?
6. **Narration** — describe the outcome from the players' perspective.

The shorter scene model is:

> State → Intent → Resolution → Narration

Research explicitly rejects:

> Narration → Justification

## Scope

Research may include tabletop play; AI and human Dungeon Masters; player and NPC behaviour; interface observations; trust analysis; bookkeeping and persistence; rules adjudication; and future usability studies.

## Accepted iterations

- [RI-001 — Trust Through Persistence, Perspective, and World Independence](RI-001.md)

## Related authorities

- [GDD](../../GDD.md) — accepted product philosophy and design decisions.
- [First Playable Vertical Slice GDD](../../FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md) — frozen executable slice specification.
- [Architecture](../../ARCHITECTURE.md) — implemented technical structure and explicitly labelled future candidates.
