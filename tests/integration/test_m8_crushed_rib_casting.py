"""Manual full-owner Casting, followups and retained first consumption witness."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_crushed_rib_casting import first_ten, prepared, execute, Dice
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_completion_models import CowardlyFlightCastingCompletionRequest
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest
from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionRequest, NpcRosterCastingCompletionResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_turn_models import NpcRosterTurnStartRequest, NpcRosterRoundAdvanceRequest
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.resolution_models import GiveGroundResolutionRequest
from towr.domain.test_models import Skill, TestQuality
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind
from towr.engine.cowardly_flight_casting import complete_cowardly_flight_casting
from towr.rules.cowardly_flight_resolution import complete_cowardly_flight_movement
from towr.rules.npc_roster_casting_completion_resolution import apply_npc_roster_casting_completion
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_minion_attack_resolution import execute_npc_roster_minion_attack, apply_npc_roster_minion_attack_result
from towr.rules.npc_roster_shooting_preparation import prepare_npc_roster_shooting
from towr.rules.npc_roster_turn_resolution import (
    start_npc_roster_turn, advance_npc_roster_round,
    apply_npc_roster_turn_start_result, apply_npc_roster_round_advance_result,
)
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result
from towr.rules.spatial_resolution import resolve_give_ground


def end(state, actor, identifier, witness=None):
    context = None if witness is None else Context(state, actor, True, witness)
    result = end_npc_wound_turn(NpcWoundTurnEndRequest(identifier, state, actor, crushed_rib_context=context))
    return apply_npc_wound_turn_end_result(state, result)


def start(state, actor, identifier, *, casting=False):
    declaration = (CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SPELL,
        improvise_approach_id='lore:battle-magic') if casting else CombatActionDeclaration(CombatActionKind.ATTACK))
    result = start_npc_roster_turn(NpcRosterTurnStartRequest(identifier, state, actor, declaration))
    return apply_npc_roster_turn_start_result(state, result)


def missed_shot(state, actor, target, identifier, witness=None):
    context = None if witness is None else Context(state, target, True, witness)
    request = prepare_npc_roster_shooting(request_id=identifier, state=state, actor_id=actor, target_id=target,
        selected_attack_id=state.roster.participant(actor).state.available_attack_ids[0],
        target_range=RangedWeaponRange.SHORT, has_enemy_in_close_range=False, range_approved_by_gm=False,
        defender_is_aware=True, selected_protection_skill=Skill.ATHLETICS, can_target_leave_zone=False,
        crushed_rib_context=context)
    dice = Dice((10,) * 6)
    if witness is None:
        result = execute_npc_roster_minion_attack(request, dice)
        current = apply_npc_roster_minion_attack_result(state, result)
    else:
        result = NpcRosterChampionAttackResult(request, execute_npc_champion_attack(request.attack, dice))
        current = apply_npc_roster_champion_attack_result(state, result)
        assert result.attack.crushed_rib is None
        assert result.attack.resolution.attack.defender_test.trace.quality is TestQuality.NORMAL
    dice.exhausted()
    return current


def next_wizard_turn(state, witness):
    state = end(state, 'wizard', 'crushed:end-wizard', witness)
    state = start(state, 'ally', 'crushed:start-ally')
    state = missed_shot(state, 'ally', 'enemy', 'crushed:ally-shot')
    state = end(state, 'ally', 'crushed:end-ally')
    advance = advance_npc_roster_round(NpcRosterRoundAdvanceRequest('crushed:round2', state))
    state = apply_npc_roster_round_advance_result(state, advance)
    state = start(state, 'enemy', 'crushed:start-enemy')
    state = missed_shot(state, 'enemy', 'wizard', 'crushed:enemy-shot', witness)
    state = end(state, 'enemy', 'crushed:end-enemy')
    return start(state, 'wizard', 'crushed:start-wizard', casting=True)


class CrushedRibCastingIntegrationTests(unittest.TestCase):
    def test_actual_consumption_end_round_normal_protection_and_normal_casting(self):
        rng = getstate()
        state = first_ten()
        before = deepcopy(state)
        first, current = execute(prepared(state), (10, 10, 10))
        witness = Witness(first, first.casting.crushed_rib)
        current = next_wizard_turn(current, witness)
        context = Context(current, 'wizard', True, witness)
        request = prepared(current, identifier='crushed:normal-casting', context=context)
        self.assertIsNone(request.casting.crushed_rib_preparation)
        with patch('towr.rules.crushed_rib_test_resolution.complete_crushed_rib_casting', side_effect=AssertionError('no repeat')):
            later, final = execute(request, (1, 10, 10))
        self.assertIsNone(later.casting.crushed_rib)
        self.assertIs(later.casting.execution.casting.test.trace.quality, TestQuality.NORMAL)
        self.assertEqual(later.casting.execution.casting.test.trace.rerolls, ())
        self.assertEqual(final.roster.participant('wizard').state.injury, witness.consumption.state)
        self.assertEqual(Context(final, 'wizard', True, witness).injury, witness.consumption.state)
        with self.assertRaises(ValueError): Witness(later, witness.consumption)
        with self.assertRaisesRegex(ValueError, 'Wound10'):
            NpcRosterCastingRequest(current, request.casting)
        with self.assertRaises(ValueError): replace(request, casting=replace(request.casting,
            crushed_rib_preparation=first.source.casting.crushed_rib_preparation))
        with self.assertRaises(ValueError): NpcWoundTurnEndRequest('no-context:end', final, 'wizard')
        final = end(final, 'wizard', 'crushed:end-wizard2', witness)
        self.assertIsNone(final.round_state.active_turn)
        self.assertTrue(final.roster.participant('wizard').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(state, before)
        self.assertEqual(getstate(), rng)

    def test_actual_movement_completion_retains_consumption_without_another_cast(self):
        state = first_ten()
        before = deepcopy(state)
        first, pending = execute(prepared(state, can_move=True), (1, 2, 3, 1, 2, 3))
        self.assertIs(first.casting.status, Status.MOVEMENT_REQUIRED)
        self.assertEqual(pending.roster.participant('wizard').state.injury, first.casting.crushed_rib.state)
        with self.assertRaises(ValueError): Context(pending, 'wizard', True, Witness(first, first.casting.crushed_rib))
        spatial = pending.spatial_state
        completions = []
        for follow in pending.pending_movement.pending_movements:
            target = pending.roster.participant(follow.target_id)
            movement = resolve_give_ground(GiveGroundResolutionRequest(follow.request, spatial,
                follow.target_id, 'middle', target.state.injury.conditions, away_from_entity_id='wizard'))
            completions.append(complete_cowardly_flight_movement(follow, movement))
            spatial = movement.state
        request = NpcRosterCastingCompletionRequest(pending,
            CowardlyFlightCastingCompletionRequest(pending.pending_movement, tuple(completions), spatial))
        dice = Dice((1, 2, 3))
        with patch('towr.engine.cowardly_flight_casting.execute_casting_attempt', side_effect=AssertionError('no recast')):
            lower = complete_cowardly_flight_casting(request.completion, dice)
        dice.exhausted()
        result = NpcRosterCastingCompletionResult(request, lower)
        final = apply_npc_roster_casting_completion(pending, result)
        self.assertIsNone(final.pending_movement)
        self.assertIs(lower.casting.crushed_rib, first.casting.crushed_rib)
        self.assertEqual(final.roster.participant('wizard').state.injury, first.casting.crushed_rib.state)
        self.assertEqual(final.roster, final.champion_attack.roster)
        self.assertEqual(final.roster, final.minion_attack.roster)
        self.assertEqual(final.consumed_execution_ids, pending.consumed_execution_ids)
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ('enemy',))
        self.assertIsNotNone(Context(final, 'wizard', True, Witness(first, first.casting.crushed_rib)))
        self.assertEqual(state, before)
        with self.assertRaises(ValueError): apply_npc_roster_casting_completion(final, result)


if __name__ == '__main__':
    unittest.main()
