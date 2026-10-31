"""Public ADR-0046 runner: fresh Casting -> Miscast -> Wind -> Prone.

Copy together with magic_scenario.py; both use public APIs, never test fixtures.
PG1.4 V Free Actions116, Attack119, Prone123; VIII Casting156, Miscasts157-159.
GM1.1 VII Minions91/Champions92. Profiles and all scene/GM facts are authored.
Scripted dice prove finite execution paths, not outcome probabilities.
No pending/result fabrication, patched entry state, or saved-battle admission.
"""
from copy import deepcopy
from dataclasses import replace
from random import getstate

from magic_scenario import ScriptedDice, authored_scenario
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_models import NpcMagicMiscastContinuationPolicy, NpcMagicPronePolicy
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastFacts, NpcRosterMiscastPolicy, NpcRosterMiscastPreparationResult,
    NpcRosterMiscastRollResult, NpcRosterUnnaturalWindResult,
)
from towr.domain.npc_roster_prone_models import NpcRosterProneStandResult, NpcRosterProneTurnEndResult
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario


def opted_scenario(*, max_rounds: int = 1):
    """Fresh admitted input, explicit decline and stand-when-safe policy.

    The neighboring builder supplies exact range/departure/route frames.
    These five separate confirmations are not inferred from its other facts.
    """
    facts = NpcRosterMiscastFacts(
        all_combatants_in_roster=True,
        no_external_short_range_creatures=True,
        unmounted_combatants_only=True,
        no_effect_immunities=True,
        no_cross_zone_close=True,
    )
    policy = NpcMagicMiscastContinuationPolicy(
        choice=NpcRosterMiscastPolicy.DECLINE_CAST_BEFORE_MISCAST,
        facts=facts,
        prone_policy=NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE,
    )
    return replace(authored_scenario(), max_rounds=max_rounds, miscast_continuation=policy)


def main() -> None:
    global_rng = getstate()
    opted = opted_scenario()
    wind_dice = (9, 9, 9, 7, 7, 7) + (10,) * 10
    cases = (
        ('LEGACY', replace(opted, miscast_continuation=None), (9, 9, 9), Outcome.UNSUPPORTED_PATH),
        ('OTHER ROW', opted, (9, 9, 9, 1, 1, 1), Outcome.UNSUPPORTED_PATH),
        ('WIND LAST ROUND', opted, wind_dice, Outcome.ROUND_LIMIT_REACHED),
        ('NEXT ROUND', opted_scenario(max_rounds=2),
         wind_dice + (10,) * 3 + (1, 2, 3, 10, 10, 10), Outcome.OBJECTIVE_ACHIEVED),
    )
    total_draws = 0
    for label, source, values, outcome in cases:
        before = deepcopy(source)
        dice = ScriptedDice(values)
        result = run_npc_magic_scenario(source, dice)
        assert source == before and result.source is source
        assert result.outcome is outcome and dice.calls == len(values)
        total_draws += dice.calls
        current = result.current
        assert current.roster == current.minion_attack.roster == current.champion_attack.roster
        assert current.round_state == current.champion_attack.round_state
        preparations = [s for s in result.steps if isinstance(s.result, NpcRosterMiscastPreparationResult)]
        rolls = [s for s in result.steps if isinstance(s.result, NpcRosterMiscastRollResult)]
        winds = [s for s in result.steps if isinstance(s.result, NpcRosterUnnaturalWindResult)]
        stands = [s for s in result.steps if isinstance(s.result, NpcRosterProneStandResult)]
        prone_ends = [s for s in result.steps if isinstance(s.result, NpcRosterProneTurnEndResult)]
        if label == 'LEGACY':
            assert result.unsupported.reason is Reason.MISCAST_PREPARATION
            assert not preparations and not rolls and not winds
            assert current.pending_miscast is not None and current.wizard.magic_state.miscast_dice == 3
        else:
            assert len(preparations) == len(rolls) == 1
            index = result.steps.index(preparations[0])
            assert preparations[0].origin_witness == result.steps[index - 1].result
            assert result.steps[index + 1] is rolls[0]
            if label == 'OTHER ROW':
                assert result.unsupported.reason is Reason.MISCAST_EFFECT and not winds
                assert current.pending_miscast_continuation == rolls[0].result
                assert current.wizard.magic_state.miscast_dice == 3
            else:
                assert len(winds) == 1 and result.steps[index + 2] is winds[0]
                assert winds[0].before.wizard.magic_state.miscast_dice == 3
                assert winds[0].after.wizard.magic_state.miscast_dice == 0
                assert all(p.state.injury.conditions.has(Condition.PRONE)
                           for p in winds[0].after.roster.participants)
                assert current.pending_miscast_continuation is None
                assert [s.actor_id for s in prone_ends] == ['wizard']
                expected_stands = ['ally', 'enemy'] + (['wizard'] if label == 'NEXT ROUND' else [])
                assert [s.actor_id for s in stands] == expected_stands
                assert all(s.before.consumed_execution_ids == s.after.consumed_execution_ids for s in stands)
                # The first two Shots target actors still Prone before their turns.
                shots = [s.result.source.attack for s in result.steps if hasattr(s.result.source, 'attack')]
                assert all(not shot.execution.kernel_request.can_target_leave_zone for shot in shots[:2])
                assert (result.executed_actions, result.completed_rounds) == (
                    (3, 1) if label == 'WIND LAST ROUND' else (5, 2))
        stop = result.unsupported.reason.value if result.unsupported else '-'
        stand_names = ','.join(s.actor_id for s in stands) or '-'
        print(f'{label}: {dice.calls} d10; {result.outcome.value}; '
              f'rounds {result.started_rounds}/{result.completed_rounds}; actions {result.executed_actions}; '
              f'Pool {current.wizard.magic_state.miscast_dice}; Wind {len(winds)}; stand {stand_names}; stop {stop}')
    assert getstate() == global_rng
    print(f'{total_draws} scripted d10; finite path evidence, not probabilities; fresh sources and global RNG preserved')
    print('Native generation requires explicit family policy; JSON/CLI v1 rejects opt-in; other Miscast rows remain pending')


if __name__ == '__main__':
    main()
