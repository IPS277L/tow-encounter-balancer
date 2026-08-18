# TOWR Combat Simulator & Encounter Balancer

## 1. Goal

I want to build a scalable combat simulator and encounter-balancing tool for a tabletop RPG system called TOWR.

The current combat rules described below are only a subset of the final ruleset. In the future, the system may include:

- dynamic statuses modifying stats;
- abilities;
- melee and ranged combat;
- magic;
- temporary effects;
- different types of damage;
- equipment;
- terrain;
- cover;
- distance;
- movement;
- action economy;
- special reactions;
- area attacks;
- conditions;
- buffs/debuffs;
- AI behavior;
- possibly many other branching rules.

Therefore, the first prototype must NOT be written as a disposable monolithic simulator.

The architecture should be designed from the beginning to support gradual expansion of the rules without requiring a major rewrite.

Primary language: **Python 3.12+**.

Initially there is no need for a graphical interface.

Input can be JSON.

Output can be console text and/or JSON.

In the future I want to add a simple GUI for input and output, while the actual rules can remain stored/configured separately.

The combat engine must be completely independent from CLI, JSON files, and future GUI code.

---

# 2. Primary use cases

The application should support at least two major modes.

## 2.1 Simulate a predefined encounter

Example conceptual command:

```bash
python -m towr simulate encounter.json
```

The encounter JSON contains:

- players;
- monsters;
- their stats;
- attacks;
- combat behavior;
- simulation count.

The simulator runs many battles and returns statistics such as:

- player victory chance;
- monster victory chance;
- average combat duration;
- median combat duration;
- round distribution;
- survivors;
- wounds;
- other useful statistics.

---

## 2.2 Generate/balance an encounter

Example:

```bash
python -m towr generate input.json
```

Input specifies:

- players and their characteristics;
- desired difficulty;
- desired number of monsters;
- desired approximate number of rounds;
- optional restrictions on generated monsters.

The application automatically searches for monster configurations that produce the desired difficulty.

It should preferably return several good candidate encounters rather than only one.

---

# 3. Current combat rules

These rules define the first prototype.

They must be implemented cleanly as rules/components rather than deeply hardcoded assumptions, because they may change later.

---

# 4. Dice notation

Many characteristics are written as:

```text
X/Y
```

Where:

- `X` = number of d10 dice rolled;
- `Y` = success threshold.

Example:

```text
4/7
```

means:

```text
roll 4d10
```

Each individual die is a success if:

```text
die <= 7
```

Thus each die has a 70% success probability.

The total number of successes is counted.

---

# 5. Attack and defense stats

Attack and defense use different stats.

## WS

`WS` is used when the entity attacks.

Example:

```text
WS 4/7
```

means the attacker rolls 4d10 and each die succeeds on 1–7.

## DEF

`DEF` is used when the entity defends.

Example:

```text
DEF 4/4
```

means the defender rolls 4d10 and each die succeeds on 1–4.

A normal opposed attack therefore works as:

```text
Attacker rolls WS
Defender rolls DEF
```

---

# 6. Opposed roll resolution

Compare the number of successes.

If:

```text
attacker_successes > defender_successes
```

the attacker wins.

If:

```text
attacker_successes == defender_successes
```

the attacker also wins.

So ties favor the attacker.

Exception:

```text
0 successes vs 0 successes
```

has special behavior described below.

If:

```text
attacker_successes < defender_successes
```

the attacker fails.

---

# 7. RES

Entities have a Resilience stat:

```text
RES
```

Example:

```text
RES 5
```

RES determines whether a successful attack causes a wound or only stagger.

---

# 8. Weapon damage

Attacks have a static `WEAPON` damage value.

Example:

```text
WEAPON 4
```

When the attacker wins an opposed roll:

```text
damage =
attacker_successes
- defender_successes
+ WEAPON
```

Example:

```text
Attacker successes: 3
Defender successes: 1
Weapon: 4

Damage = 3 - 1 + 4 = 6
```

---

# 9. Wound vs stagger

Damage is compared to target RES.

If:

```text
damage > RES
```

the target receives:

```text
1 wound
```

If:

```text
damage <= RES
```

the target receives:

```text
1 stagger
```

Important:

Damage exactly equal to RES is still stagger.

Example:

```text
damage 5
RES 5

=> stagger
```

not wound.

---

# 10. Stagger

Stagger accumulates.

Normally:

```text
2 stagger = 1 wound
```

Stagger persists between attacks and rounds until a wound occurs.

When an entity receives a wound, accumulated stagger is reset.

So conceptually:

```text
entity receives wound
entity.stagger = 0
```

This also applies when two stagger points convert into a wound.

---

# 11. Failed attack

If the attacker gets fewer successes than the defender:

```text
attacker_successes < defender_successes
```

the attacker receives:

```text
1 stagger
```

The defender does not receive damage.

This means attacking can itself be dangerous.

---

# 12. Special 0 vs 0 case

If:

```text
attacker_successes == 0
defender_successes == 0
```

both sides receive:

```text
1 stagger
```

This overrides the normal "tie goes to attacker" behavior.

---

# 13. Wounds

Entities have a wound capacity:

```text
WOUNDS
```

Example player:

```text
WOUNDS 5
```

The entity is defeated when accumulated wounds reach its wound limit.

Current typical player value:

```text
5 wounds
```

Monsters may normally have approximately:

```text
1–6 wounds
```

depending on monster type.

This should NOT necessarily be hardcoded as a permanent system limitation.

It may initially be used as a balancing constraint.

---

# 14. Turn sequence

Combat proceeds in rounds.

Currently:

```text
PLAYER PHASE
then
MONSTER PHASE
then next round
```

Players act first.

During the player phase, all living players act.

During the monster phase, all living monsters act.

Then the next round begins.

Battle ends when one side has no living combatants.

---

# 15. Multiple players and monsters

The engine must support:

```text
1 vs 1
N players vs 1 monster
1 player vs N monsters
N players vs N monsters
```

Combatants can die during the battle and no longer act after being defeated.

---

# 16. Multiple monster attacks

A monster is NOT limited to one attack per turn.

A monster may have multiple attacks.

Example:

```text
Attack 1
WS 5/5
WEAPON 4
targets = 1

Attack 2
WS 4/6
WEAPON 3
targets = 1

Attack 3
WS 3/5
WEAPON 2
targets = 3
```

Every attack may have:

- its own attack dice/stat;
- its own static weapon damage;
- its own targeting behavior;
- its own number of targets.

Do not assume all attacks simply use the monster's base WS.

For the current system this can be modeled either as an attack containing its own roll profile or referencing a stat.

Design this so future attacks can use different stats such as magic or ranged stats.

---

# 17. Multi-target attacks

A single attack may hit several targets.

Example:

```text
targets = 3
```

or potentially:

```text
targets = all
```

Default resolution for a multi-target attack:

The attacker makes one attack roll.

Example:

```text
monster rolls 4/5
=> 3 successes
```

Each affected player independently rolls DEF.

Example:

```text
Player 1 DEF => 2 successes
Player 2 DEF => 4 successes
Player 3 DEF => 0 successes
```

The outcome is then resolved independently against every target using the same attacker result.

Thus:

```text
Monster result: 3 successes
```

can wound one target, stagger another, and fail against another.

The architecture should allow this behavior to later be replaced or configured if necessary.

---

# 18. Example current player

A current example used in previous calculations:

```text
WS      4/7
DEF     4/4
RES     5
WEAPON  4
WOUNDS  5
```

This should be useful as a default test fixture.

---

# 19. Difficulty system

We currently use approximate difficulty categories based on overall probability that the PLAYER SIDE wins the entire encounter.

Current provisional definitions:

```text
Easy:
75–90% player victory

Medium:
50–65% player victory

Hard:
20–35% player victory

Impossible:
0–10% player victory
```

Suggested target centers:

```text
Easy       ≈ 82%
Medium     ≈ 57.5%
Hard       ≈ 27.5%
Impossible ≈ 5%
```

These values are provisional and must be stored as configuration, not hardcoded throughout the program.

Example configuration:

```json
{
  "easy": {
    "min_win_rate": 0.75,
    "max_win_rate": 0.90,
    "target_win_rate": 0.82
  },
  "medium": {
    "min_win_rate": 0.50,
    "max_win_rate": 0.65,
    "target_win_rate": 0.575
  },
  "hard": {
    "min_win_rate": 0.20,
    "max_win_rate": 0.35,
    "target_win_rate": 0.275
  },
  "impossible": {
    "min_win_rate": 0.00,
    "max_win_rate": 0.10,
    "target_win_rate": 0.05
  }
}
```

---

# 20. Target combat duration

The user may provide a desired approximate number of rounds.

Example:

```text
target_rounds = 6
```

The encounter generator should take both into account:

```text
desired win probability
desired fight duration
```

Win probability should generally be considered more important than exact duration.

A candidate scoring system could start as:

```text
score =
win_rate_weight * abs(actual_win_rate - target_win_rate)
+
round_weight * normalized_round_difference
```

But the exact optimizer design can evolve.

---

# 21. Monte Carlo simulation

Because the rules will become increasingly complex, do NOT try to derive the entire combat outcome analytically.

Use Monte Carlo simulation.

Example:

```text
run 100,000 encounters
count victories
collect round counts
collect other statistics
```

For performance, balancing can use staged simulations.

Example:

```text
Stage 1:
many candidates
~1,000 simulations each

keep best candidates

Stage 2:
best candidates
~10,000 simulations each

keep finalists

Stage 3:
finalists
100,000+ simulations each
```

Exact counts should be configurable.

---

# 22. Encounter generator

The generator should search possible monster configurations.

Possible generated values may include:

```text
WS
DEF
RES
WOUNDS
number of attacks
attack roll values
weapon damage
target count
AI behavior
```

Example search constraints:

```json
{
  "ws_dice": [2, 8],
  "ws_skill": [2, 8],
  "def_dice": [2, 8],
  "def_skill": [2, 8],
  "res": [3, 8],
  "weapon": [1, 6],
  "wounds": [1, 6],
  "attacks": [1, 4],
  "allow_aoe": true
}
```

All constraints should be configurable.

---

# 23. Avoid mathematically valid but bad monster designs

A purely numerical optimizer may create ugly or nonsensical monsters.

For example:

```text
WS 8/8
DEF 2/2
RES 3
four strange AoE attacks
```

might mathematically match a target win rate but be undesirable for gameplay.

Therefore encounter generation should eventually support constraints and possibly monster archetypes.

Examples:

```text
brute
assassin
tank
horde
caster
boss
support
```

Example conceptual archetype:

```json
{
  "style": "brute",
  "preferences": {
    "res": "high",
    "wounds": "high",
    "weapon": "high",
    "def": "low",
    "attacks": "low"
  }
}
```

This is not necessary for the absolute first implementation, but the architecture should not prevent it.

---

# 24. AI must be separate from combatant stats

Target selection and tactical behavior should not be embedded directly into monsters.

Use separate controller/strategy objects.

Examples:

```text
RandomAI
FocusWeakestAI
FocusMostWoundedAI
FocusStaggeredAI
AggressiveAI
BossAI
```

The exact same monster can have different combat effectiveness depending on target selection.

Therefore AI strategy must be part of the encounter configuration and simulation.

---

# 25. Major architecture requirement

The system should have four clearly separated conceptual layers:

```text
RULES
How the game works

ENGINE
How one battle is executed

SIMULATION
How many battles are repeatedly executed and analyzed

BALANCER
How encounter candidates are generated and evaluated
```

The balancer should not care what "stagger" means.

It should simply ask the simulator:

```python
result = simulator.run(encounter, simulations=10000)
```

and receive something like:

```python
SimulationResult(
    player_win_rate=0.574,
    average_rounds=6.1,
    ...
)
```

Similarly, changing the stagger rules should not require rewriting the optimizer.

---

# 26. Application layer

There should also be an application/service layer between user interfaces and the engine.

Conceptually:

```text
CLI
JSON
Future GUI
Future web API

        ↓

APPLICATION SERVICES

        ↓

ENGINE / SIMULATION / BALANCER
```

Example service methods:

```python
generate_encounter(request)
simulate_encounter(request)
validate_encounter(request)
```

The GUI should never directly implement combat logic.

---

# 27. GUI future requirement

A graphical interface is planned in the future.

It will primarily be used for INPUT and OUTPUT.

It does NOT need to be a graphical rule editor.

Example GUI input:

```text
Players: 3

WS       4/7
DEF      4/4
RES      5
WEAPON   4
WOUNDS   5

Difficulty: Medium
Monsters: 2
Target rounds: 6

[GENERATE]
```

Example GUI output:

```text
Player victory: 57.4%
Average duration: 6.1 rounds

Monster 1
WS ...
DEF ...
RES ...
...

Monster 2
...
```

Potential future GUI technology:

```text
PySide6 / Qt
```

because the main application is Python.

However the engine should not depend on PySide6.

A future web frontend should also be possible without changing core logic.

---

# 28. JSON is serialization, not application logic

Important architectural principle:

Do NOT make the combat engine dependent on JSON files.

Bad architecture:

```text
JSON
 ↓
combat logic
 ↓
JSON
```

Preferred:

```text
JSON ─────┐
CLI ──────┼─> input/domain model
GUI ──────┘
               ↓
         application layer
               ↓
             engine
               ↓
          result model
          /    |     \
        JSON console GUI
```

The internal application should operate on Python domain objects.

JSON loaders/savers merely serialize and deserialize those objects.

---

# 29. Event-driven rules engine

Because the final rules will be highly branching, use an event-driven or hook-driven approach.

Possible events:

```text
BattleStarted
RoundStarted
TurnStarted

ActionDeclared
TargetsSelected

BeforeAttackRoll
AttackRoll
AfterAttackRoll

BeforeDefenseRoll
DefenseRoll
AfterDefenseRoll

OpposedRollResolved

BeforeDamageCalculated
DamageCalculated
BeforeDamageApplied
DamageApplied

StaggerApplied
WoundApplied

StatusApplied
StatusRemoved

EntityDefeated

ActionFinished
TurnEnded
RoundEnded
BattleEnded
```

Names can change, but the architectural idea is important.

Statuses, abilities, equipment, spells, etc. should be able to react to events without requiring large numbers of hardcoded `if` statements in the main battle function.

---

# 30. Dynamic stats / modifier system

Do not treat effective stats as immutable values directly read from an entity.

Example:

```text
Base WS:       4/7
Poison:        -1 die
Blessing:      +1 skill
High ground:   +1 die
```

The engine should be able to compute an effective stat from:

```text
base stat
+ active modifiers
+ contextual modifiers
```

Conceptual API:

```python
effective_ws = stat_resolver.resolve(
    entity,
    stat="WS",
    context=context
)
```

This is important for future dynamic statuses.

---

# 31. Avoid giant entity classes

Do not create something like:

```python
class Fighter:
    poisoned: bool
    burning: bool
    stunned: bool
    blessed: bool
    flying: bool
    ...
```

Prefer composition.

Conceptually:

```text
Entity
+ Stats
+ Resources
+ StatusEffects
+ Abilities
+ Equipment
+ Tags
+ Controller
```

---

# 32. Status effects

Statuses should be separate objects/components.

Example conceptual structure:

```python
StatusEffect:
    id
    source
    duration
    stacks
    modifiers
    triggers
```

Simple status example:

```json
{
  "id": "poisoned",
  "duration": 3,
  "modifiers": [
    {
      "stat": "WS_DICE",
      "operation": "subtract",
      "value": 1
    }
  ]
}
```

Another:

```json
{
  "id": "berserk",
  "duration": 2,
  "modifiers": [
    {
      "stat": "WS_DICE",
      "operation": "add",
      "value": 2
    },
    {
      "stat": "DEF_DICE",
      "operation": "subtract",
      "value": 1
    }
  ]
}
```

The core engine should not need to know specifically what "berserk" is if it can be expressed through generic modifiers.

---

# 33. Complex ability handlers

Not every rule should be forced into JSON.

Simple behavior:

```text
JSON/configuration
```

Complex behavior:

```text
Python handler/plugin
```

For example:

```text
When this entity receives a wound:
roll d10.
On 1–3:
perform a free attack.
```

Could conceptually be configured as:

```json
{
  "id": "blood_frenzy",
  "trigger": "WoundApplied",
  "handler": "blood_frenzy"
}
```

with a Python handler implementing the complex behavior.

Do NOT try to create a giant custom JSON programming language.

Use JSON for declarative rules where practical and Python handlers for complex mechanics.

---

# 34. Actions

Do not make "Attack" the only fundamental action type.

Use a more generic Action abstraction.

Potential future action types:

```text
MeleeAttack
RangedAttack
Spell
Ability
ItemUse
Movement
SpecialAction
```

Conceptually:

```python
class Action:
    ...
```

Different action implementations can emit/use shared events.

For example:

```text
MeleeAttack
    attack roll
    defense roll
    damage

Spell
    magic roll
    resistance roll
    damage
    apply status

RangedAttack
    ranged stat
    distance
    cover
    damage
```

---

# 35. Combat context

Many rules may depend on context.

Create a combat/action context object.

Potential fields:

```text
attacker
targets
action
round
phase
distance
terrain
cover
elevation
position
tags
source
```

Do not implement all of these systems immediately.

But avoid architecture that would make adding contextual values difficult.

---

# 36. Tags

Use tags extensively where appropriate.

Example physical melee attack:

```json
{
  "tags": [
    "attack",
    "melee",
    "physical",
    "slashing",
    "weapon"
  ]
}
```

Example fire spell:

```json
{
  "tags": [
    "spell",
    "magic",
    "fire",
    "area"
  ]
}
```

Future rules can then express things like:

```text
+2 RES against physical

immune to poison

+1 damage against undead

cannot dodge area attacks
```

without hardcoding a separate boolean field for every possible interaction.

---

# 37. Deterministic RNG

The simulator should support deterministic random seeds.

Example:

```json
{
  "seed": 123456
}
```

This is essential for reproducing bugs and unusual battles.

A battle should be replayable using the same seed.

Prefer dependency injection of an RNG object rather than directly calling global `random.*` everywhere.

Example conceptual API:

```python
rng = Random(seed)

battle = Battle(..., rng=rng)
```

---

# 38. Structured event logs

For debug/replay mode, combat events should be recorded in structured form.

Example:

```json
{
  "type": "attack_roll",
  "round": 3,
  "attacker": "monster_1",
  "target": "player_2",
  "dice": [2, 7, 1, 5],
  "successes": 3
}
```

Then:

```json
{
  "type": "damage_resolved",
  "source": "monster_1",
  "target": "player_2",
  "success_difference": 2,
  "weapon": 4,
  "damage": 6,
  "target_res": 5,
  "result": "wound"
}
```

Normal mass simulation should be able to disable detailed logging for performance.

---

# 39. Ruleset versioning

Rules will evolve.

Include ruleset version information.

Example:

```json
{
  "ruleset": "towr",
  "rules_version": "0.1.0"
}
```

This may later allow old simulations to remain reproducible after rule changes.

Do not overengineer historical compatibility in the first version, but reserve the concept.

---

# 40. Suggested project structure

This is conceptual and can be adjusted where technically justified:

```text
towr/
│
├── engine/
│   ├── battle.py
│   ├── events.py
│   ├── actions.py
│   ├── resolver.py
│   ├── dice.py
│   └── context.py
│
├── domain/
│   ├── combatant.py
│   ├── stats.py
│   ├── resources.py
│   ├── attacks.py
│   └── encounter.py
│
├── effects/
│   ├── statuses.py
│   ├── modifiers.py
│   └── triggers.py
│
├── rules/
│   ├── core.py
│   ├── opposed_roll.py
│   ├── damage.py
│   ├── stagger.py
│   └── wounds.py
│
├── abilities/
│   ├── registry.py
│   └── handlers/
│
├── ai/
│   ├── base.py
│   ├── random.py
│   ├── focused.py
│   └── boss.py
│
├── simulation/
│   ├── simulator.py
│   ├── statistics.py
│   └── parallel.py
│
├── balance/
│   ├── generator.py
│   ├── optimizer.py
│   ├── scoring.py
│   └── constraints.py
│
├── application/
│   ├── generate_encounter.py
│   ├── simulate_encounter.py
│   └── validate_encounter.py
│
├── interfaces/
│   ├── cli/
│   │   └── main.py
│   └── gui/
│
├── serialization/
│   ├── json_loader.py
│   └── json_writer.py
│
├── schemas/
│   └── ...
│
├── data/
│   └── rules/
│
└── tests/
```

Do not create meaningless files simply to match this tree.

Start relatively small, but preserve the architectural boundaries.

---

# 41. Suggested input representation

Avoid overly rigid top-level stat fields such as:

```json
{
  "ws": [4, 7],
  "def": [4, 4],
  "res": 5
}
```

Prefer an extensible representation such as:

```json
{
  "stats": {
    "WS": {
      "dice": 4,
      "skill": 7
    },
    "DEF": {
      "dice": 4,
      "skill": 4
    },
    "RES": 5
  }
}
```

This makes future additions easier:

```json
{
  "MAG": {
    "dice": 5,
    "skill": 6
  },
  "BS": {
    "dice": 4,
    "skill": 5
  }
}
```

However, use typed Python models internally rather than passing raw dictionaries everywhere.

---

# 42. Example encounter input

A possible early format:

```json
{
  "ruleset": "towr",
  "rules_version": "0.1.0",

  "simulation": {
    "runs": 100000,
    "seed": 123456
  },

  "players": [
    {
      "id": "player_template_1",
      "count": 3,

      "stats": {
        "WS": {
          "dice": 4,
          "skill": 7
        },
        "DEF": {
          "dice": 4,
          "skill": 4
        },
        "RES": 5
      },

      "wounds": 5,

      "actions": [
        {
          "type": "melee_attack",
          "id": "basic_weapon",
          "weapon": 4,
          "targets": 1
        }
      ]
    }
  ],

  "generation": {
    "difficulty": "medium",
    "monster_count": 2,
    "target_rounds": 6
  }
}
```

This is only a starting example.

Improve the schema if needed, but preserve extensibility.

---

# 43. Example result

Conceptually:

```json
{
  "result": {
    "player_win_rate": 0.574,
    "monster_win_rate": 0.426,

    "rounds": {
      "average": 6.12,
      "median": 6
    },

    "simulations": 100000,

    "monsters": [
      {
        "stats": {
          "WS": {
            "dice": 4,
            "skill": 5
          },
          "DEF": {
            "dice": 4,
            "skill": 4
          },
          "RES": 5
        },

        "wounds": 3,

        "actions": [
          {
            "type": "melee_attack",
            "weapon": 3,
            "targets": 1
          }
        ]
      }
    ]
  }
}
```

---

# 44. Performance

Initial implementation can use standard Python.

Likely useful libraries/features:

```text
dataclasses
typing
enum
json
random
statistics
concurrent.futures
multiprocessing
```

Avoid premature NumPy dependence if it complicates the rules engine.

Later, performance-critical simulation paths may potentially use:

```text
NumPy
Numba
multiprocessing
```

or some optimized implementation if necessary.

Correctness and extensibility are more important than maximizing early benchmark speed.

---

# 45. Testing requirements

Testing is important because the combat rules will become complex.

At minimum include unit tests for:

## Dice

```text
success threshold handling
dice counts
deterministic seeds
```

## Opposed roll

```text
attacker greater than defender
attacker less than defender
nonzero tie favors attacker
0 vs 0 special case
```

## Damage

```text
difference + weapon
damage > RES => wound
damage == RES => stagger
damage < RES => stagger
```

## Stagger

```text
1 stagger remains stagger
2 stagger => wound
wound resets stagger
```

## Defeat

```text
entity is defeated at wound limit
dead entities no longer act
```

## Multi-target

Ensure one shared attacker roll is separately resolved against each defender.

## Multiple attacks

Ensure each attack resolves independently and can target different combatants.

---

# 46. Statistical tests

Do not use fragile exact expected Monte Carlo percentages.

For simulation tests, either:

- use deterministic mocked dice;
- use fixed event sequences;
- use broad statistical tolerances where required.

Core combat resolution should be testable without Monte Carlo randomness.

---

# 47. First implementation scope

Do NOT immediately implement:

- magic;
- ranged combat;
- terrain;
- complex abilities;
- GUI;
- web API;
- full plugin systems;
- dozens of statuses.

The first milestone should implement only the currently known combat rules, but through the scalable architecture described above.

Suggested first milestone:

1. Domain models.
2. RNG abstraction.
3. Dice pools.
4. WS vs DEF opposed rolls.
5. Damage / RES.
6. Stagger.
7. Wounds/death.
8. Player/monster phases.
9. Multiple combatants.
10. Multiple attacks.
11. Multi-target attacks.
12. AI target-selection abstraction.
13. One complete deterministic battle simulation.
14. Monte Carlo simulator.
15. JSON serialization.
16. CLI.
17. Statistics.
18. Basic encounter optimizer/generator.

---

# 48. Important design principle

Do not overengineer every future feature now.

But avoid architectural decisions that make future features impossible or require rewriting the engine.

The desired balance is:

```text
simple first implementation
+
clear abstractions
+
strong test coverage
+
loose coupling
```

not:

```text
huge speculative framework
```

---

# 49. Preferred development sequence

Please work incrementally.

Before writing large amounts of code:

1. Inspect the repository.
2. Propose a concrete minimal architecture.
3. Explain key domain abstractions.
4. Identify which parts should be generic now and which should wait.
5. Then implement the first vertical slice.

The first vertical slice should ideally support something like:

```text
1 player
vs
1 monster

WS
DEF
RES
WEAPON
WOUNDS
STAGGER
```

with deterministic tests.

Then expand to:

```text
multiple entities
multiple attacks
multi-target attacks
Monte Carlo
balancing
```

Do not implement the optimizer before the combat engine is well tested.

---

# 50. Current conceptual difficulty example

Example player:

```text
WS      4/7
DEF     4/4
RES     5
WEAPON  4
WOUNDS  5
```

For encounter generation, the input may eventually say:

```text
players = 3 identical players
difficulty = medium
monster_count = 2
target_rounds = 6
```

The desired output is something like:

```text
Candidate 1

Monster A
WS ...
DEF ...
RES ...
WOUNDS ...
Attacks ...

Monster B
WS ...
DEF ...
RES ...
WOUNDS ...
Attacks ...

Estimated player victory: 57.4%
Average duration: 6.1 rounds
```

The exact monster stats must be obtained from the program's own simulations rather than hardcoded examples from previous manual calculations.

---

# 51. One important unresolved design choice

A character currently has a base WS stat, but an individual attack may potentially have its own attack profile.

For example a monster could have:

```text
Base WS 4/5

Attack A: 5/4
Attack B: 3/7
```

Design this carefully.

A reasonable approach could be:

```text
Action.roll_source
```

where an attack can:

- reference an entity stat such as WS;
- reference another stat such as MAG;
- override/add modifiers;
- or in exceptional cases contain its own roll profile.

Do not assume every future attack always uses WS.

---

# 52. Another unresolved area: attack target selection

Current behavior is not fully fixed for every combatant.

Therefore make target selection configurable through controllers.

For early tests:

Players may use:

```text
focus most wounded monster
```

Monsters may use:

```text
focus most wounded player
```

But this should not be considered an immutable core rule.

---

# 53. Output metrics worth preparing for

Eventually useful statistics may include:

```text
player win rate
monster win rate

average rounds
median rounds
round histogram

average surviving players
survivor distribution

average wounds per surviving player

average wounds dealt by each entity
average stagger inflicted
average stagger received

attack hit/wound/stagger rates

entity survival rate

ability usage counts

damage sources

death causes
```

The first version only needs a useful subset.

But `SimulationResult` should be designed so more metrics can be added later without affecting the battle engine.

---

# 54. Future GUI

When GUI development begins, preferred architecture:

```text
PySide6 GUI
      ↓
application services
      ↓
same simulator/balancer
```

The GUI should act as a visual editor/viewer for input/output models.

It should be able to:

```text
create encounter
load encounter JSON
save encounter JSON
run simulation
generate monsters
display results
save results
```

Potential later graphs:

```text
win probability
round distribution
survivor distribution
candidate comparison
```

Again, no GUI code should exist inside the engine.

---

# 55. Final instruction to Codex

Treat this as a real small software project rather than a one-file throwaway script.

At the same time, avoid unnecessary framework complexity.

The most important qualities are:

1. **Correct combat resolution.**
2. **Deterministic testability.**
3. **Clean separation of domain, rules, simulation, balancing, serialization, and UI.**
4. **Extensibility for future branching RPG mechanics.**
5. **Ability to run large Monte Carlo simulations.**
6. **Ability to add a simple GUI later without redesigning the core.**
7. **Readable Python code with type hints and tests.**

When a design tradeoff occurs, prefer composition over deep inheritance and explicit domain models over raw dictionaries.

Before implementing encounter generation, make sure the combat engine can be validated thoroughly with deterministic tests.