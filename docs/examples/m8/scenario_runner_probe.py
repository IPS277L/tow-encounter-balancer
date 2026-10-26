"""Public single-run M8 smoke probe; authored profiles, no tests/private API.

PG1.4 Rules pp112,119,122; Magic pp156-157,162; GM1.1 pp91-92.
The two-Zone authored arena deliberately supplies only the initial scene frame.
"""
from dataclasses import replace
from random import getstate

from encounter_contract_probe import ScriptedDice, admitted_scenario
from towr.domain.npc_magic_scene_models import NpcMagicAttackDeparture
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_objective_models import NpcDefeatObjective
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario


def main() -> None:
    global_rng = getstate()
    source = admitted_scenario()
    # Explicit GM facts for this authored open arena, including Wizard/ally.
    # Ordinary departure is separate from the Curse's supplied away-route.
    facts = (NpcMagicAttackDeparture('wizard', True), NpcMagicAttackDeparture('ally', True),
             NpcMagicAttackDeparture('enemy', True))
    source = replace(source, scene_frames=(replace(source.initial_frame, attack_departures=facts),))
    ally_first = replace(source, activation_order=('ally', 'wizard', 'enemy'))
    opposite = replace(ally_first, perspective_side=CombatSide.OPPOSITION, objective=NpcDefeatObjective(('wizard', 'ally')))
    cases = (
        ('OBJECTIVE', ally_first, (1, 2, 3, 10, 10, 10), Outcome.OBJECTIVE_ACHIEVED),
        ('PERSPECTIVE', opposite, (1, 2, 3, 10, 10, 10), Outcome.PERSPECTIVE_DEFEATED),
        ('LIMIT', replace(source, max_rounds=2), (10,) * 30, Outcome.ROUND_LIMIT_REACHED),
        ('MISCAST', source, (9, 9, 9), Outcome.UNSUPPORTED_PATH),
        ('MISSING FRAME', source, (1, 2, 3, 10, 10, 10), Outcome.UNSUPPORTED_PATH),
    )
    for label, scenario, values, outcome in cases:
        initial = scenario.initial_runtime_state
        rng = ScriptedDice(values)
        result = run_npc_magic_scenario(scenario, rng)
        rng.exhausted()
        assert result.source is scenario and result.outcome is outcome
        assert scenario.initial_runtime_state == initial
        assert len(result.current.roster.participants) == len(result.current.spatial_state.placements) == 3
        assert result.current.minion_attack.roster == result.current.champion_attack.roster == result.current.roster
        if label in ('OBJECTIVE', 'PERSPECTIVE'):
            assert result.executed_actions == 1 and result.completed_rounds == 0
            assert result.current.round_state.completed_turn_entity_ids == ('ally',)
            assert result.current.minion_attack.acknowledged_defeat_execution_ids == result.current.consumed_execution_ids
        elif label == 'LIMIT':
            assert (result.started_rounds, result.completed_rounds, result.executed_actions) == (2, 2, 6)
            assert result.current.round_state.round_number == result.current.spatial_state.round_number == 2
        elif label == 'MISCAST':
            assert result.unsupported.reason is Reason.MISCAST_PREPARATION
            assert result.current.pending_miscast is not None and result.current.wizard.magic_state.miscast_dice == 3
        else:
            assert result.unsupported.reason is Reason.MISSING_SCENE and result.unsupported.actor_id == 'ally'
            assert result.current.pending_movement is None
            assert result.current.spatial_state.placement_for('enemy').zone_id == 'shelter'
        print(f'{label}: {rng.calls} d10; {result.outcome.value}; '
              f'rounds {result.started_rounds}/{result.completed_rounds}; actions {result.executed_actions}; '
              f'steps {len(result.steps)}')
    assert getstate() == global_rng
    print('51 scripted d10; full owners/sources retained; global RNG unchanged; no Miscast effect or post-battle recovery')


if __name__ == '__main__':
    main()
