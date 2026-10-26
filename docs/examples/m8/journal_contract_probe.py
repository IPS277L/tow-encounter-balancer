"""Explicit action chains checked by the production M8 journal, not a runner.

Uses public authored fixtures from encounter_contract_probe. PG1.4 Combat
p112, Magic pp156-157,162; GM1.1 Allies and Antagonists / Minions p91.
"""
from random import getstate

from encounter_contract_probe import ScriptedDice, admitted_scenario, casting, attack_parts
from towr.domain.npc_magic_step_models import (
    NpcMagicStep, NpcMagicUnsupported, NpcMagicPhase, NpcMagicUnsupportedReason, NpcMagicScenarioOutcome,
)
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_attack_models import NpcRosterAttackExecutionRequest
from towr.domain.npc_roster_minion_attack_models import NpcRosterMinionAttackRequest
from towr.domain.npc_roster_minion_defeat_models import NpcRosterMinionDefeatRequest
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack
from towr.rules.npc_roster_minion_defeat_resolution import acknowledge_npc_roster_minion_defeat
from towr.rules.npc_roster_turn_resolution import start_npc_roster_turn
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def main() -> None:
    global_rng = getstate()
    scenario = admitted_scenario()
    initial = scenario.initial_runtime_state
    spell = CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
                                   improvise_approach_id=scenario.spell.lore_id)
    start = NpcMagicStep(start_npc_roster_turn(NpcRosterTurnStartRequest(
        scenario.id + ':wizard:turn', initial, 'wizard', spell)))
    request = casting(start.after, scenario.id + ':cast', can_give_ground=True)
    rng = ScriptedDice((9, 9, 9))
    miscast = NpcMagicStep(NpcRosterCastingResult(request, execute_cowardly_flight_casting(request.casting, rng)))
    rng.exhausted()
    diagnostic = NpcMagicUnsupported(NpcMagicPhase.CONTINUATION, NpcMagicUnsupportedReason.MISCAST_PREPARATION,
                                     'wizard', miscast.id)
    stopped = NpcMagicScenarioResult(scenario, (start, miscast), diagnostic)
    assert stopped.outcome is NpcMagicScenarioOutcome.UNSUPPORTED_PATH
    assert stopped.current.pending_miscast is miscast.result.casting
    assert stopped.current.wizard.magic_state.miscast_dice == 3
    assert (stopped.started_rounds, stopped.completed_rounds, stopped.executed_actions) == (1, 0, 1)
    print('MISCAST JOURNAL: 3 d10; 2 bound steps; exact source/pending/pool retained; no preparation or table')

    # Independent explicit WAIT -> ally Attack -> supplied defeat -> end-turn.
    rng = ScriptedDice((10, 10, 10))
    wait = NpcMagicStep(NpcRosterCastingResult(request, execute_cowardly_flight_casting(request.casting, rng)))
    rng.exhausted()
    end_wizard = NpcMagicStep(end_npc_wound_turn(NpcWoundTurnEndRequest(scenario.id + ':wizard:end', wait.after, 'wizard')))
    ally = NpcMagicStep(start_npc_roster_turn(NpcRosterTurnStartRequest(scenario.id + ':ally:turn', end_wizard.after,
        'ally', CombatActionDeclaration(CombatActionKind.ATTACK))))
    protected, execution = attack_parts(ally.after, 'enemy', actor_id='ally', prefix=scenario.id + ':shot')
    attack_request = NpcRosterMinionAttackRequest(ally.after,
        NpcRosterAttackExecutionRequest(ally.after.minion_attack, protected, execution))
    rng = ScriptedDice((1, 2, 3, 10, 10, 10))
    attack = NpcMagicStep(execute_npc_roster_minion_attack(attack_request, rng))
    rng.exhausted()
    decision, = scenario.policy_for('ally').defeat_decisions
    acknowledgement = NpcMagicStep(acknowledge_npc_roster_minion_defeat(NpcRosterMinionDefeatRequest(
        scenario.id + ':ack', attack.after, decision)))
    end_ally = NpcMagicStep(end_npc_wound_turn(NpcWoundTurnEndRequest(scenario.id + ':ally:end', acknowledgement.after, 'ally')))
    finished = NpcMagicScenarioResult(scenario, (start, wait, end_wizard, ally, attack, acknowledgement, end_ally))
    assert finished.outcome is NpcMagicScenarioOutcome.OBJECTIVE_ACHIEVED
    assert (finished.started_rounds, finished.completed_rounds, finished.executed_actions) == (1, 1, 2)
    assert len(finished.current.roster.participants) == len(finished.current.spatial_state.placements) == 3
    assert finished.current.minion_attack.acknowledged_defeat_execution_ids == (attack.id,)
    try:
        NpcMagicScenarioResult(scenario, finished.steps[:-1])
    except ValueError:
        pass
    else:
        raise AssertionError('journal must retain mandatory end-turn before outcome')
    print('OBJECTIVE JOURNAL: 9 d10; 7 bound steps; acknowledgement/end-turn required; archive and both ledgers retained')
    assert scenario.initial_runtime_state == initial and getstate() == global_rng
    print('12 scripted d10; journal validation uses 0; sources/global RNG unchanged; no automatic runner')


if __name__ == '__main__':
    main()
