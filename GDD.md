# Dungeon Manager — Section 1: Core Vision & Design Philosophy

## Core Vision

Dungeon Manager is not an AI storyteller, nor a chatbot that happens to know tabletop rules.

It is a persistent AI Dungeon Master supported by a deterministic tabletop game engine.

Its purpose is to recreate the experience of sitting around a table with a skilled human Dungeon Master: one who understands the rules, remembers the world, portrays believable characters, rewards creativity fairly, and allows the players to shape the story through meaningful choices.

The AI should never feel like software attempting to entertain the player.

It should feel like a genuine Dungeon Master running a living world.

## Player-Facing Promise

Dungeon Manager should allow players to experience long-form tabletop RPG campaigns with an AI Dungeon Master they can trust.

Players should never feel that the AI is secretly steering them toward predetermined outcomes, inventing convenient answers, or ignoring previous events.

The world should respond naturally to their actions while remaining internally consistent.

> The players choose.
> The Dungeon Master interprets.
> The game engine resolves.
> The world remembers.

## The North Star

> Build a Dungeon Master that players trust enough to stop thinking about the software and start thinking only about the adventure.

Immersion is not the primary objective.

Trust is.

Immersion develops naturally when players trust that the rules, world, characters, and consequences remain consistent.

## Internal Design Mantra

> The player chooses.
> The AI understands and performs.
> The engine decides and remembers.
> Foundry shows.

This describes the intended division of responsibility:

- The player provides intent and makes meaningful decisions.
- The AI interprets that intent, portrays the world, and performs the role of the Dungeon Master.
- The deterministic engine validates actions, resolves mechanics, and preserves authoritative state.
- Foundry VTT presents the resulting world through maps, tokens, sheets, lighting, effects, and other visual tools.

The AI is therefore a controlled client of the game engine, not the authority over game state.

## Primary Success Metric: Trust

The primary measure of Dungeon Manager’s success is whether players trust the Dungeon Master and the world it operates.

This trust has five dimensions.

### Trust in the Rules

Players should trust that the same rules apply consistently.

Mechanical outcomes must be determined through the rules engine rather than changed by the AI to produce a more dramatic result.

The AI may interpret ambiguous situations, but it must not secretly manipulate established mechanics.

### Trust in the World

Players should trust that the campaign world continues to exist independently of them.

Locations, objects, factions, NPCs, relationships, resources, and ongoing events must persist beyond the immediate conversation.

The world should not be recreated differently whenever the players return to it.

### Trust in NPCs

Players should trust that NPCs have consistent knowledge, motivations, personalities, limitations, and relationships.

NPCs should know only what they have legitimately learned. They should not change their beliefs or behaviour merely to give the players a convenient answer.

### Trust in Consequences

Players should trust that their decisions matter and remain part of the campaign.

Promises, failures, injuries, discoveries, relationships, destroyed objects, spent resources, and changes to the world must continue to affect later events.

Consequences must not disappear when the immediate scene ends.

### Trust in Fairness

Players should trust that the AI is neither secretly helping nor unfairly opposing them.

Difficulty, uncertainty, and failure are legitimate parts of tabletop play. The AI must not force a preferred story by altering outcomes, concealing valid options, or protecting players from the consequences of their decisions.

## Supporting Design Pillars

### Player Agency

The player is always the primary decision-maker.

Dungeon Manager may:

- clarify the situation;
- portray the world;
- describe apparent options;
- interpret player intent;
- request necessary mechanical information;
- adjudicate the attempted action.

It should never make important decisions on behalf of the player.

The AI must not quietly choose the player’s goals, dialogue, emotional reactions, tactics, relationships, or moral position.

### NPC Independence

NPCs are not extensions of the player, the narrator, or the plot.

Each meaningful NPC may possess their own:

- goals;
- knowledge;
- fears;
- relationships;
- opinions;
- biases;
- limitations;
- ambitions.

NPCs may disagree with the players, refuse requests, misunderstand situations, make mistakes, pursue their own interests, and change over time.

Their behaviour should follow from who they are and what they know—not from what would be most convenient for the current scene.

### World Independence

The campaign world does not exist solely for the players.

Events may continue when the party is absent:

- villains continue planning;
- merchants continue trading;
- factions pursue their interests;
- NPCs travel and communicate;
- opportunities may appear or disappear;
- locations may change because of earlier events.

The world has momentum.

The players remain its most important participants, but they are not the only cause of change within it.

### Emergent Character Identity

Characters are not static collections of statistics and biography fields.

Identity should also emerge through play:

- recurring jokes;
- habits;
- traditions;
- favourite sayings;
- fears developed through experience;
- changing relationships;
- personal growth;
- repeated patterns of behaviour.

These developments should be remembered and allowed to influence later scenes.

This applies to player characters, companions, recurring NPCs, allies, and antagonists.

### Character-Centric Storytelling

The campaign should remain centred on characters rather than becoming a sequence of disconnected quests.

Meaningful characters should have histories, goals, conflicts, relationships, and aspirations that can develop throughout the campaign.

Events become meaningful because of how they affect people and relationships—not merely because they advance a predefined plot.

Character-centric storytelling does not mean that every event revolves around the player. It means that the story emerges from the interaction between people living within the world.

### Creative Problem Solving

Players must be free to attempt actions that were not anticipated by the adventure, interface, or developer.

The AI should understand natural-language intent and translate it into appropriate game actions, rules questions, tool requests, or adjudication.

Players should not need to discover a hidden list of acceptable commands.

When an idea is plausible, Dungeon Manager should determine what would be required to attempt it rather than rejecting it simply because no predefined solution exists.

### Creativity Never Overrides Fairness

Creative ideas should be recognised and rewarded appropriately, but creativity does not guarantee success.

Every attempted solution remains subject to:

- the rules;
- established world state;
- character knowledge;
- physical possibility;
- character capability;
- risk;
- opposition;
- appropriate difficulty.

The system must not lower every difficulty or ignore established limitations merely because an idea is entertaining.

A creative plan may improve the circumstances, create a new possibility, reduce risk, or provide an advantage. It must still be adjudicated honestly.

### Perspective Integrity

Every participant has an individual perspective.

A character should possess only information that they have legitimately acquired through experience, observation, communication, or prior knowledge.

The system must distinguish between:

- what is true in the world;
- what the Dungeon Master knows;
- what each NPC knows;
- what each player character knows;
- what has been revealed to the player.

Narration, dialogue, and decision-making must not leak information across these boundaries.

### Social Realism

Social interaction should reflect believable human behaviour rather than operate like a dialogue-selection interface.

NPCs do not always need to be:

- helpful;
- efficient;
- friendly;
- honest;
- emotionally available;
- interested in the players;
- willing to explain themselves.

Conversations may be incomplete, awkward, misleading, inefficient, or unproductive when that behaviour fits the people and circumstances involved.

Persuasion is not mind control. Social outcomes must account for personality, motives, knowledge, relationships, status, mood, risk, and what is actually being requested.

### Living Environments

Locations should be more than backdrops for conversations and combat.

A believable environment contains objects, occupants, activities, exits, sounds, physical features, opportunities, and evidence of ongoing life.

Players should be able to inspect, manipulate, combine, damage, move, or otherwise interact with plausible elements of the environment.

Important locations should persist and evolve rather than being regenerated whenever the players enter them.

### Consistency Over Cleverness

A consistent answer is more valuable than a surprising answer.

The AI must preserve established:

- facts;
- rules;
- character behaviour;
- relationships;
- locations;
- resources;
- consequences;
- chronology.

It should not contradict previous events merely to produce a clever twist, dramatic reveal, or more convenient scene.

When novelty conflicts with continuity, continuity takes priority.

### Information Should Be Earned

Information should belong to sources within the world.

Players may learn things through:

- observation;
- conversation;
- research;
- documents;
- exploration;
- deduction;
- magic;
- prior experience.

The Dungeon Master should not provide convenient omniscient summaries simply because the information would help the players progress.

Some information may be incomplete, biased, outdated, mistaken, deliberately concealed, or unavailable.

Discovering information is part of play.

### Recovery Over Perfection

No AI system will behave perfectly at all times.

Dungeon Manager should therefore be designed to detect, contain, explain, and recover from mistakes without corrupting the campaign.

Established reality must not be silently rewritten to hide an error.

When correction is necessary, the system should preserve authoritative state, identify the inconsistency, and recover in the least disruptive way possible.

Reliable recovery is more important than pretending the system can never fail.

### Local Ownership

The campaign belongs to the user.

Campaign state, characters, world data, configuration, and long-term memory should remain locally controlled, inspectable, portable, and recoverable.

The system should avoid unnecessary dependence on external services.

Players and Dungeon Masters must retain control over their data, models, rules, and campaign history.

## Explicit Anti-Goals

Dungeon Manager is not intended to become:

- a chatbot with dice;
- an AI novelist;
- an autonomous game that plays itself;
- a quest dispenser;
- an omniscient narrator;
- a dialogue-tree generator;
- an AI that secretly solves problems for the players;
- an AI that manipulates outcomes to create a “better story.”

These approaches may produce entertaining moments, but they undermine the long-term trust required for a persistent tabletop campaign.

## Human DM Behaviour Test

When evaluating a proposed feature or behaviour, ask:

> Would a competent human Dungeon Master reasonably do this?

If the answer is “no,” the implementation should be questioned regardless of its technical sophistication.

This does not mean reproducing every limitation of a human Dungeon Master. It means that automation should strengthen the behaviours that make a human Dungeon Master trustworthy rather than replace them with behaviours that only make sense for software.

## Feature Justification Chain

Every significant feature should be traceable through the following chain:

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

A feature should not exist merely because it is technically interesting.

It should address an observed need, support an accepted design principle, produce a clear requirement, fit the architecture, and have a way to verify whether it improves the intended experience.

## Foundational Statement

> Dungeon Manager is not an AI that happens to run tabletop mechanics. It is a tabletop game engine designed to support the complete behaviour of a trustworthy AI Dungeon Master.
>
> The goal is not to imitate the words of a Dungeon Master. The goal is to faithfully reproduce the decisions, judgement, consistency, creativity, fairness, and humanity that make a great Dungeon Master memorable.

---

## Current executable design contract

Section 1 above is frozen product authority and must not be silently paraphrased or amended.

The current frozen implementation contract is [FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md](FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md). It defines the complete first playable behavior and the accepted seven-milestone sequence. The two files together form the current complete GDD:

- GDD.md: core vision and general design philosophy.
- FIRST_PLAYABLE_VERTICAL_SLICE_GDD_V1.md: executable vertical-slice behavior and milestone sequence.
