"""ADR-0057 actual native Crushed Rib journals and spawned compact trials.

Copy with crushed_rib_owner.py, stationary_wound_runner.py,
generation_contract_probe.py and magic_scenario.py. All profiles/facts are
authored. PG1.4 pp108,118,123,156-157,190; GM1.1 p92.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from fractions import Fraction
from multiprocessing import active_children
import os
from random import getstate

from crushed_rib_owner import enemy_first
from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input
from towr.domain.npc_magic_scenario_models import NpcMagicCrushedRibPolicy as Policy
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.domain.condition_models import Condition
from towr.domain.test_models import TestQuality
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.balance.magic_assessment import assess_magic_candidate
from towr.balance.magic_assessment_models import ObjectiveRateWindow, MagicAssessmentStatus
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


POLICY = Policy.NEXT_TEST_WITH_JOURNAL_WITNESSES
HIT = (1, 2, 3, 10, 10, 10)
FIRST_TEN = (*HIT, 10)
CASTING_STREAM = (*FIRST_TEN, 1, 9, 10, 9, *((10,) * 21))
PROTECTION_STREAM = (*FIRST_TEN, 10, 10, 10, 1, 6, 10, 9, *((10,) * 15))
NEW_FOUR_STREAM = (*FIRST_TEN, 1, 2, 3, 1, 6, 10, 9, 1, 3)
MISCAST_STREAM = (*FIRST_TEN, 9, 9, 9)
MOVEMENT_STREAM = (*FIRST_TEN, 1, 2, 3, 1, 2, 3, 1, 1, 1, *((10,) * 6))
DEATH_STREAM = (*HIT, 1, *((10,) * 9),
                *HIT, 1, 1, *((10,) * 9),
                *HIT, 1, 1, 8, *((10,) * 9),
                *HIT, 10, 10, 10, 10)


def casting_scenario(*, opted=True, miscast=False, rounds=2):
    source = authored_input(stationary=False, miscast=miscast)
    return replace(source, max_rounds=rounds,
        crushed_rib_continuation=POLICY if opted else None)


def protection_scenario(*, opted=True):
    return replace(enemy_first(), max_rounds=1,
        crushed_rib_continuation=POLICY if opted else None)


def miscast_scenario():
    source = casting_scenario()
    return replace(source, initial=replace(source.initial, wizard=replace(source.initial.wizard,
        caster=replace(source.initial.wizard.caster, wizard_level=2))))


def death_scenario():
    return casting_scenario(rounds=4)


def direct(source, values):
    before = deepcopy(source)
    dice = ScriptedDice(values)
    result = run_npc_magic_scenario(source, dice)
    assert dice.calls == len(values) and source == before
    assert NpcMagicScenarioResult(source, result.steps, result.unsupported) == result
    assert result.current.roster == result.current.champion_attack.roster == result.current.minion_attack.roster
    return result


@dataclass(frozen=True, slots=True)
class ScriptedFactory:
    seeds: tuple[int, ...]
    streams: tuple[tuple[int, ...], ...]
    parent_pid: int | None = None

    def __call__(self, seed):
        if self.parent_pid is not None and os.getpid() == self.parent_pid:
            raise AssertionError('spawn trial ran in its parent')
        return ScriptedDice(self.streams[self.seeds.index(seed)])


def main():
    global_rng = getstate()
    children = {child.pid for child in active_children()}
    cast = direct(casting_scenario(), CASTING_STREAM)
    casts = tuple(s.result for s in cast.steps if isinstance(s.result, NpcRosterCastingResult))
    assert len(CASTING_STREAM) == 32 and cast.outcome is Outcome.ROUND_LIMIT_REACHED
    assert len(casts) == 2 and casts[0].casting.crushed_rib is not None and casts[1].casting.crushed_rib is None
    assert casts[0].casting.crushed_rib.casting.test.successes == 0
    assert casts[0].casting.status is CowardlyFlightCastingStatus.WAITING
    assert casts[0].casting.post_test.miscast_pool.dice_added == 2
    assert casts[0].casting.post_test.state.miscast_dice == 2
    assert casts[0].casting.execution.casting.test.trace.quality is TestQuality.GRIM
    assert casts[1].casting.execution.casting.test.trace.quality is TestQuality.NORMAL
    assert cast.current.roster.participant('wizard').state.injury == casts[0].casting.crushed_rib.state
    print('CASTING-FIRST:32d10; actual first10 -> failed Grim Casting/pool+2/WAIT -> later normal Protection/Casting; one first journal witness, Drained/history retained')

    protected = direct(protection_scenario(), PROTECTION_STREAM)
    consuming = tuple(s.result for s in protected.steps if isinstance(s.result, NpcRosterChampionAttackResult)
                      and s.result.attack.crushed_rib is not None)
    assert len(PROTECTION_STREAM) == 29 and protected.outcome is Outcome.ROUND_LIMIT_REACHED
    assert len(consuming) == 1 and consuming[0].attack.execution.actor_id == 'E2'
    assert consuming[0].attack.crushed_rib.test.successes == 0
    assert consuming[0].attack.crushed_rib.test.trace.quality is TestQuality.GRIM
    e3 = next(s.result for s in protected.steps if isinstance(s.result, NpcRosterChampionAttackResult)
              and s.result.attack.execution.actor_id == 'E3')
    assert e3.attack.crushed_rib is None
    assert e3.attack.execution.resolution.attack.defender_test.trace.quality is TestQuality.NORMAL
    normal_cast = next(s.result for s in protected.steps if isinstance(s.result, NpcRosterCastingResult))
    assert normal_cast.casting.crushed_rib is None
    assert normal_cast.casting.execution.casting.test.trace.quality is TestQuality.NORMAL
    assert protected.current.roster.participant('wizard').state.injury == consuming[0].attack.crushed_rib.state
    print('PROTECTION-FIRST:29d10; current E2 Shooting consumes before Wizard turn; E3 Protection and Casting normal; full journal reconstruction retains exact first result')

    for source in (casting_scenario(opted=False), protection_scenario(opted=False)):
        legacy = direct(source, FIRST_TEN)
        assert legacy.unsupported.reason in (Reason.ACTOR_INJURY, Reason.TARGET_INJURY)
        assert not any(getattr(getattr(s.result, 'attack', None), 'crushed_rib', None) is not None
                       for s in legacy.steps)
    print('NONE: two fresh controls stop at first10/7d10 each; no extra Test, receipt or implicit opt-in')

    pending = direct(protection_scenario(), NEW_FOUR_STREAM)
    assert len(NEW_FOUR_STREAM) == 16 and pending.unsupported.reason is Reason.WOUND_EFFECT
    assert len(pending.current.champion_attack.daily_wounds.receipts) == 2
    assert len(pending.current.champion_attack.consumed_wound_roll_ids) == 2
    print('MANDATORY WOUND:16d10; Protection consumes old effect before new4; actual Endurance follow-up stops before more RNG, both daily/roll receipts retained')

    miscast = direct(miscast_scenario(), MISCAST_STREAM)
    assert len(MISCAST_STREAM) == 10 and miscast.unsupported.reason is Reason.MISCAST_PREPARATION
    assert miscast.current.pending_miscast.crushed_rib is not None
    assert miscast.current.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED)
    print('MANDATORY MISCAST:10d10; consuming Casting already applied before pool3/Level2 stop; full pending receipt retained without independent Miscast permission')

    movement = direct(casting_scenario(rounds=1), MOVEMENT_STREAM)
    origin = next(s.result for s in movement.steps if isinstance(s.result, NpcRosterCastingResult))
    completed = next(s.result for s in movement.steps if isinstance(s.result, NpcRosterCastingCompletionResult))
    assert len(MOVEMENT_STREAM) == 22 and movement.outcome is Outcome.ROUND_LIMIT_REACHED
    assert origin.casting.status is CowardlyFlightCastingStatus.MOVEMENT_REQUIRED
    assert completed.completion.casting.crushed_rib == origin.casting.crushed_rib
    assert all(target.test.trace.quality is TestQuality.NORMAL
               for target in completed.completion.casting.willpower.targets)
    assert movement.current.roster.participant('wizard').state.injury == origin.casting.crushed_rib.state
    print('MANDATORY MOVEMENT:22d10; one consuming Casting -> pending movement -> normal target Willpower; same first receipt/Drained survive completion without another Casting')

    dead = direct(death_scenario(), DEATH_STREAM)
    assert len(DEATH_STREAM) == 61 and dead.unsupported.reason is Reason.MISSING_SCENE
    assert dead.current.roster.participant('wizard').state.injury.dead
    assert any(isinstance(s.result, NpcRosterDeadChampionExclusionResult) for s in dead.steps)
    assert sum((isinstance(s.result, NpcRosterCastingResult) and s.result.casting.crushed_rib is not None)
               or (isinstance(s.result, NpcRosterChampionAttackResult) and s.result.attack.crushed_rib is not None)
               for s in dead.steps) == 1
    print('DEATH:61d10; two prior superficial Wounds ->10/one consumption -> later lethal Wound; mandatory exclusion precedes actual missing-scene stop without resetting history')

    request = NpcMagicSimulationRequest(protection_scenario(), 42, 2)
    before = deepcopy(request)
    seeds = tuple(request.seed_for(i) for i in range(request.trials))
    streams = (PROTECTION_STREAM, NEW_FOUR_STREAM)
    sequential = run_npc_magic_simulation(request, rng_factory=ScriptedFactory(seeds, streams))
    spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1,
        rng_factory=ScriptedFactory(seeds, streams, os.getpid()))
    assert sequential == spawned
    summary = summarize_npc_magic_simulation(spawned)
    assert summary == summarize_npc_magic_simulation(sequential)
    assert spawned.outcome_counts == NpcMagicOutcomeCounts(0, 0, 1, 1)
    assert tuple(r.seed for r in spawned.trials) == seeds
    assert all(r.source_scenario is request.scenario for r in spawned.trials)
    assessment = assess_magic_candidate(request, summary,
        ObjectiveRateWindow(Fraction(0), Fraction(1, 2), Fraction(1)))
    assert assessment.unsupported_path_rate == Fraction(1, 2)
    assert assessment.status is MagicAssessmentStatus.UNSUPPORTED_OBSERVATIONS
    assert request == before and getstate() == global_rng
    assert {child.pid for child in active_children()} == children
    print('REAL SPAWN: seq/process compact records and summary identical; common seed prefix/full source retained; one limit +one unsupported stay in denominator2')
    print('274 scripted d10 across direct/seq/spawn; native57 implemented, generation/JSON1-4 remain refused; source/global RNG unchanged; no runtime-percentage oracle')


if __name__ == '__main__':
    main()
