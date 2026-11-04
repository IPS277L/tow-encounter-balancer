"""Literal heavy-injury encounters crossing actual end-turn and attack paths."""
from dataclasses import replace

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.simulation.pc_melee_models import pc_melee_trial_seed


def critical_encounter_source():
    source = make_pc_melee_scenario(enemy_count=3,max_rounds=3)
    member = source.party[0]
    # Resilience6: ordinary successful 3+3 Damage only Staggers; repeat
    # Staggered creates Wounds1/14 before the next PC action.
    return replace(source,party=(replace(member,pc=replace(member.pc,toughness=4,armour_bonus=2)),))


def critical_prefix():
    return ([10,10,10,1,1]
        + [1,1,1,10,10,10,1]
        + [1,1,1,10,10,10]
        + [1,1,1,10,10,10,7,7])


def forced_wound_rng(seed):
    # Attack kills Minion1; Critical Test fails. Minion2's unopposed
    # Damage4 vs Resilience6 must inflict Wound25 on Defenceless PC.
    return ScriptedD10(critical_prefix()
        + [1,1,1,10,10]
        + [10,10,10,10]
        + [1,10,10,8,8,9])


def critical_death_rng(seed):
    # PC misses, fails Critical Test, all NPCs miss unopposed;
    # next own empty incapacity turn fails its Critical Test and dies.
    return ScriptedD10(critical_prefix()
        + [10,10,10,1,1]
        + [10,10,10,10]
        + [10,10,10]*3
        + [10,10,10,10])


def indexed_critical_rng(seed):
    return {pc_melee_trial_seed(42,0):forced_wound_rng,
            pc_melee_trial_seed(42,1):critical_death_rng}[seed](seed)
