"""Actual native ADR-0061 runner and mass API; copy with magic_scenario.py.

PG1.4 Characteristics/Skills pp68-70, Prone p123, Wounds Table p190; GM1.1 p92.
All numeric profiles/facts are authored. This is not a named book NPC profile.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
from random import getstate

from magic_scenario import ScriptedDice, authored_scenario
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_models import (
    NpcMagicBatteredLegPolicy, NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy,
)
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_battered_leg_models import NpcRosterBatteredLegResult
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastFacts, NpcRosterMiscastPolicy
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest, NpcMagicOutcomeCounts
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel
from towr.simulation.npc_magic_simulation import run_npc_magic_simulation
from towr.simulation.npc_magic_summary import summarize_npc_magic_simulation


FIRST_FIVE = (1, 2, 3, 10, 10, 10, 5)
SUCCESS = (*FIRST_FIVE, 1, 10, *((10,) * 9))
FAILURE = (*FIRST_FIVE, 10, 10)


@dataclass(frozen=True, slots=True)
class ScriptedFactory:
    seeds: tuple[int, ...]
    streams: tuple[tuple[int, ...], ...]

    def __call__(self, seed):
        return ScriptedDice(self.streams[self.seeds.index(seed)])


def authored_input(*, opted=True, rounds=1, miscast=False, completed_wizard=False):
    source = authored_scenario(wizard_side=(CombatSide.PLAYERS_AND_ALLIES
        if completed_wizard else CombatSide.OPPOSITION))
    return replace(source, max_rounds=rounds,
        battered_leg_continuation=NpcMagicBatteredLegPolicy(InlineProfile(2, 5)) if opted else None,
        miscast_continuation=(NpcMagicMiscastContinuationPolicy(
            NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
            NpcRosterMiscastFacts(True, True, True, True, True),
            NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE) if miscast else None))


def main():
    global_rng = getstate()
    cases = (
        ('NONE', authored_input(opted=False), FIRST_FIVE, Reason.WOUND_EFFECT),
        ('NONE WITH MISCAST', authored_input(opted=False, miscast=True), FIRST_FIVE, Reason.WOUND_EFFECT),
        ('SUCCESS', authored_input(), SUCCESS, None),
        ('FAILURE', authored_input(), FAILURE, Reason.ACTOR_INJURY),
        ('FAILURE WITH MISCAST', authored_input(miscast=True), FAILURE, Reason.ACTOR_INJURY),
        ('LATER STAGGERED', authored_input(rounds=2), (*SUCCESS, 1, 10, 10, 10, 10, 10), Reason.END_TURN),
        ('LATER SUPERFICIAL', authored_input(rounds=2),
            (*SUCCESS, 1, 2, 3, 10, 10, 10, 1, 1), Reason.END_TURN),
        ('LATER PENDING WOUND4', authored_input(rounds=2),
            (*SUCCESS, 1, 2, 3, 10, 10, 10, 1, 3), Reason.WOUND_EFFECT),
        ('COMPLETED WIZARD SUCCESS', authored_input(completed_wizard=True),
            (*((10,) * 9), *FIRST_FIVE, 1, 10), None),
        ('COMPLETED WIZARD FAILURE', authored_input(completed_wizard=True),
            (*((10,) * 9), *FIRST_FIVE, 10, 10), None),
        ('LATER MISCAST PENDING', authored_input(), (*FIRST_FIVE, 1, 10, 9, 9, 9), Reason.MISCAST_PREPARATION),
    )
    total = 0
    for label, source, values, stop in cases:
        before = deepcopy(source)
        dice = ScriptedDice(values)
        result = run_npc_magic_scenario(source, dice)
        assert dice.calls == len(values) and source == before
        assert NpcMagicScenarioResult(source, result.steps, result.unsupported) == result
        assert result.current.roster == result.current.champion_attack.roster == result.current.minion_attack.roster
        completions = tuple(step for step in result.steps if isinstance(step.result, NpcRosterBatteredLegResult))
        if not source.battered_leg_continuation:
            assert not completions and result.current.battered_leg_receipt is None
            assert result.current.champion_attack.pending is not None
        else:
            assert len(completions) == 1
            completion = completions[0]
            assert completion.actor_id == 'wizard'
            assert completion.before.round_state.active_turn.actor_id == 'enemy'
            assert result.steps[result.steps.index(completion) - 1].result == completion.result.source.attack
            assert completion.before.consumed_execution_ids == completion.after.consumed_execution_ids
            assert completion.before.round_state == completion.after.round_state
            assert result.current.battered_leg_receipt == completion.after.battered_leg_receipt
            assert completion.result.source.endurance_profile == source.battered_leg_continuation.endurance_profile
            assert len(result.current.champion_attack.daily_wounds.receipts) == (
                2 if label.startswith('LATER ') and 'WOUND4' in label or label == 'LATER SUPERFICIAL' else 1)
            if 'FAILURE' in label:
                assert result.current.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE)
        if stop is None:
            assert result.outcome is Outcome.ROUND_LIMIT_REACHED and result.completed_rounds == 1
        else:
            assert result.outcome is Outcome.UNSUPPORTED_PATH and result.unsupported.reason is stop
            if stop is Reason.END_TURN:
                assert result.unsupported.actor_id == 'enemy'
                assert result.unsupported.missing_actor_ids == ('wizard',)
        total += dice.calls
        print(f'{label}: {dice.calls}d10; {result.outcome.value}; {stop.value if stop else "completed round"}; full owners/receipts retained')

    request = NpcMagicSimulationRequest(authored_input(), 42, 2)
    original = deepcopy(request)
    factory = ScriptedFactory(tuple(request.seed_for(index) for index in range(2)), (SUCCESS, FAILURE))
    sequential = run_npc_magic_simulation(request, rng_factory=factory)
    spawned = run_npc_magic_simulation_parallel(request, workers=2, batch_size=1, rng_factory=factory)
    assert sequential == spawned and request == original
    assert sequential.outcome_counts == NpcMagicOutcomeCounts(0, 0, 1, 1)
    assert summarize_npc_magic_simulation(sequential) == summarize_npc_magic_simulation(spawned)
    assert summarize_npc_magic_simulation(spawned).trials == 2
    assert all(trial.source_scenario is request.scenario for trial in spawned.trials)
    total += 2 * (len(SUCCESS) + len(FAILURE))
    assert total == 228 and getstate() == global_rng
    print('NATIVE sequential/real spawn: equal full source, seed records and summary; round limit + unsupported both in denominator2')
    print('228 scripted d10; actual native runner/completion60 and mass APIs; immutable sources/global RNG; generation and JSON1-5 remain separate')


if __name__ == '__main__':
    main()
