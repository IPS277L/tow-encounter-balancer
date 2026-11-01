"""ADR-0053 actual native repeated stand, bounded history, and spawned trials.

Copy with stationary_wound_runner.py and magic_scenario.py. Authored Wizard4.
PG1.4 Rules116/119/122-123, Wounds190; GM1.1 Champions92.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
import os
from random import getstate

from magic_scenario import ScriptedDice
from stationary_wound_runner import authored_input, ScriptedFactory
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_models import NpcMagicRepeatedLegSpasmPolicy
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_repeated_leg_spasm_policy import (
    initial_magic_repeated_leg_spasm_history, advance_magic_repeated_leg_spasm_history,
)
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome, NpcMagicUnsupportedReason
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import NpcRosterRepeatedLegSpasmStandResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


HIT = (1, 2, 3, 10, 10, 10)
PREFIX = (*HIT, 9, *((10,) * 9), *HIT, 4, 5, *((10,) * 9))
FULL = (*PREFIX, *((10,) * 15))
POST_SIX = (*PREFIX, *HIT, 1, 2, 3, *((10,) * 9))
THIRD_NINE = (*PREFIX, *HIT, 3, 3, 3)


@dataclass(frozen=True, slots=True)
class ChildScriptedFactory:
    source: ScriptedFactory
    parent_pid: int

    def __call__(self, seed):
        assert os.getpid() != self.parent_pid, 'spawned trial must execute in a child'
        return self.source(seed)


def authored_repeated(*, miscast=False):
    return replace(authored_input(miscast=miscast), repeated_leg_spasm_continuation=
        NpcMagicRepeatedLegSpasmPolicy.STAND_ONCE_WITH_JOURNAL_WITNESSES)


def execute(source, values):
    before = deepcopy(source)
    dice = ScriptedDice(values)
    result = run_npc_magic_scenario(source, dice)
    assert dice.calls == len(values) and source == before
    assert NpcMagicScenarioResult(source, result.steps, result.unsupported) == result
    return result


def main():
    rng_before = getstate()
    baseline = None
    for miscast in (False, True):
        source = authored_repeated(miscast=miscast)
        result = execute(source, FULL)
        assert len(FULL) == 48 and result.outcome is NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED
        assert (result.executed_actions, result.started_rounds, result.completed_rounds) == (9, 3, 3)
        first = tuple(s for s in result.steps if isinstance(s.result, NpcRosterLegSpasmStandResult))
        repeated = tuple(s for s in result.steps if isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult))
        assert len(first) == len(repeated) == 1
        second = repeated[0]
        assert second.result.source.previous_stand == first[0].result
        assert any(s.result == second.result.source.wound_attack for s in result.steps)
        assert second.before.round_state == second.after.round_state
        assert second.before.consumed_execution_ids == second.after.consumed_execution_ids
        assert second.after.spatial_state.placements == second.before.spatial_state.placements
        assert second.after.spatial_state.free_move_used_entity_ids == ('wizard',)
        history = initial_magic_repeated_leg_spasm_history(source)
        for step in result.steps:
            history = advance_magic_repeated_leg_spasm_history(source, history, step)
        assert history.state == result.current and history.repeated_stand == second.result
        assert history.previous_stand == first[0].result
        assert history.wound_attack == second.result.source.wound_attack
        injury = result.current.roster.participant('wizard').state.injury
        assert tuple(w.table_total for w in injury.wounds) == (9, 9)
        assert not injury.conditions.has(Condition.PRONE) and len(injury.active_wound_effects) == 2
        if baseline is not None:
            assert result.steps == baseline.steps and result.current == baseline.current
        baseline = result
        print(f'NATIVE repeated=on miscast={"on" if miscast else "None"}: 48 d10; stand48 + stand52; 9 actions; 3 completed rounds')
    for stationary, values in ((False, (*HIT, 9)), (True, FULL[:24])):
        old = execute(authored_input(stationary=stationary), values)
        assert old.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
        assert not any(isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult) for s in old.steps)
        print(f'OLD repeated=None stationary={"on" if stationary else "None"}: {len(values)} d10; unchanged actor-injury stop')
    six = execute(authored_repeated(), POST_SIX)
    assert len(POST_SIX) == 51 and six.outcome is NpcMagicScenarioOutcome.ROUND_LIMIT_REACHED
    injury = six.current.roster.participant('wizard').state.injury
    assert tuple(w.table_total for w in injury.wounds) == (9, 9, 6)
    assert not injury.conditions.has(Condition.DRAINED) and not six.current.wound_expiries
    assert len(tuple(e for end in six.current.wound_turn_end_receipts for e in end.expired_sources)) == 1
    assert len(injury.active_wound_effects) == 2
    assert len(six.current.champion_attack.daily_wounds.receipts) == 3
    print('POST-STAND WOUND6: 51 d10; bound Drained expiry at round3 end; all three wounds/daily records and both terrains retained')
    third = execute(authored_repeated(), THIRD_NINE)
    assert len(THIRD_NINE) == 42 and third.unsupported.reason is NpcMagicUnsupportedReason.ACTOR_INJURY
    assert sum(isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult) for s in third.steps) == 1
    assert tuple(w.table_total for w in third.current.roster.participant('wizard').state.injury.wounds) == (9, 9, 9)
    print('ONE REPEAT ONLY: 42 d10; third9 stops; no renewal of prior witnesses or consumed permission')
    request = NpcMagicSimulationRequest(authored_repeated(), 42, 2)
    before = deepcopy(request)
    factory = ScriptedFactory(tuple(request.seed_for(i) for i in range(2)), (FULL, (*HIT, 10)))
    sequential = run_npc_magic_simulation(request, rng_factory=factory)
    spawned = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1,
        rng_factory=ChildScriptedFactory(factory, os.getpid()))
    assert sequential == spawned and summarize_npc_magic_simulation(sequential) == summarize_npc_magic_simulation(spawned)
    assert sequential.outcome_counts == NpcMagicOutcomeCounts(0, 0, 1, 1)
    assert all(record.source_scenario is request.scenario for record in spawned.trials)
    assert summarize_npc_magic_simulation(spawned).trials == 2 and request == before
    assert getstate() == rng_before
    print('SEQUENTIAL/SPAWN: exact records/full source/summary; round-limit + unsupported; denominator2')
    print('330 scripted d10 total; bounded journal-derived witnesses; immutable sources/global RNG; native only')


if __name__ == '__main__':
    main()
