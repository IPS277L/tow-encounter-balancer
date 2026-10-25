"""Supplied turns with real Curse/Recover and real Champion Wound histories."""
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_cowardly_flight_casting import CountingDice
from tests.unit.test_m8_cowardly_flight_casting_models import casting_input
from tests.unit.test_m8_npc_roster_casting import bound_request
from tests.integration.test_m8_champion_casting_handoff import incoming_attack, wizard_turn
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.magic_models import WizardMagicState
from towr.domain.movement_models import FreeMovementRequest, MovementSpeed
from towr.domain.npc_broken_recover_models import NpcBrokenRecoverRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackRequest, NpcRosterChampionAttackResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.recover_models import RecoverActionExecutionRequest, RecoverMode, RecoverStandardChoice
from towr.domain.spatial_models import ZoneConnection, ZoneGraph
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatTurnEndRequest, CombatTurnStartRequest,
)
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.engine.npc_broken_recover import execute_npc_broken_recover, apply_npc_broken_recover_result
from towr.rules.npc_champion_attack_execution import execute_npc_champion_attack
from towr.rules.npc_roster_champion_attack_resolution import apply_npc_roster_champion_attack_result
from towr.rules.npc_roster_casting_resolution import apply_npc_roster_casting_result, prepare_npc_roster_casting
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.turn_resolution import end_combat_turn, start_combat_turn, reserve_combat_action_slot


def first_enemy_recover_turn(combat):
    combat = end_combat_turn(CombatTurnEndRequest('end:wizard', combat, 'wizard')).state
    combat = start_combat_turn(CombatTurnStartRequest('start:friend', combat, 'friend')).state
    combat = reserve_combat_action_slot(CombatActionSlotRequest('slot:friend', combat, 'friend',
        CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD)).state
    combat = execute_recover_action(RecoverActionExecutionRequest('recover:friend', combat, 'friend',
        ConditionState(), True, 1, RecoverMode.STANDARD, RecoverStandardChoice(WizardMagicState())), SequenceRandom(())).round_state
    combat = end_combat_turn(CombatTurnEndRequest('end:friend', combat, 'friend')).state
    combat = start_combat_turn(CombatTurnStartRequest('start:first', combat, 'first')).state
    return reserve_combat_action_slot(CombatActionSlotRequest('slot:first', combat, 'first',
        CombatActionDeclaration(CombatActionKind.RECOVER), ActionSlotGrant.STANDARD)).state


def wounded_broken_wizard(pool):
    source = incoming_attack()
    attack = execute_npc_champion_attack(source.attack, SequenceRandom((1, 2, 10, 10, 10, 10, 6)))
    owner = apply_npc_roster_champion_attack_result(source.state, NpcRosterChampionAttackResult(source, attack))
    owner = wizard_turn(owner)
    # Broken is an explicit initial fact for this transition; the real Stomach
    # Wound/daily history comes from the existing Champion attack boundary.
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=replace(p.state.injury,
        conditions=p.state.injury.conditions.with_condition(Condition.BROKEN))))
        if p.state.actor_id == owner.wizard.actor_id else p for p in owner.roster.participants))
    turn = owner.round_state.active_turn
    slot = replace(turn.action_slots[0], declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
    combat = replace(owner.round_state, active_turn=replace(turn, action_slots=(slot,)))
    spatial = replace(owner.spatial_state, graph=ZoneGraph(('arena', 'empty'), (ZoneConnection('arena', 'empty'),)))
    return source, attack, replace(owner, roster=roster, round_state=combat, spatial_state=spatial,
        champion_attack=replace(owner.champion_attack, roster=roster, round_state=combat),
        wizard=replace(owner.wizard, magic_state=WizardMagicState(pool, 1, 'lore:battle-magic', 1)))


def wizard_recovery(owner):
    actor = owner.wizard.actor_id
    conditions = owner.roster.participant(actor).state.injury.conditions
    movement = FreeMovementRequest('broken:free-move', owner.round_state, owner.spatial_state,
                                    actor, MovementSpeed.NORMAL, conditions, ('empty',))
    return NpcBrokenRecoverRequest('broken', owner, actor, InlineProfile(3, 3), movement, True, True)


class NpcBrokenRecoverIntegrationTests(unittest.TestCase):
    def test_real_curse_then_minion_free_move_and_successful_or_failed_recover(self):
        for dice, removed in (([1, 2, 3], True), ([10, 10, 10], False)):
            with self.subTest(removed=removed):
                source = casting_input()
                source = replace(source, spatial_state=replace(source.spatial_state,
                    graph=ZoneGraph(('arena', 'elsewhere', 'empty'), (ZoneConnection('arena', 'empty'),)),
                    gave_ground_entity_ids=('second', 'first')))
                bound = bound_request(source)
                rng = CountingDice([1, 2, 3] + [10] * 6 + dice)
                cast = execute_cowardly_flight_casting(bound.casting, rng)
                owner = apply_npc_roster_casting_result(bound.state, NpcRosterCastingResult(bound, cast))
                combat = first_enemy_recover_turn(owner.round_state)
                owner = replace(owner, round_state=combat)
                conditions = owner.roster.participant('first').state.injury.conditions
                movement = FreeMovementRequest('broken:free-move', combat, owner.spatial_state,
                    'first', MovementSpeed.NORMAL, conditions, ('empty',))
                request = NpcBrokenRecoverRequest('broken', owner, 'first', InlineProfile(3, 3), movement, True, True)
                result = execute_npc_broken_recover(request, rng)
                final = apply_npc_broken_recover_result(owner, result)
                self.assertEqual(rng.calls, 12)
                self.assertEqual(final.spatial_state.placement_for('first').zone_id, 'empty')
                self.assertEqual(final.spatial_state.gave_ground_entity_ids, ('second', 'first'))
                self.assertEqual(final.spatial_state.free_move_used_entity_ids, ('first',))
                self.assertEqual(final.roster.participant('first').state.injury.conditions.has(Condition.BROKEN), not removed)
                self.assertTrue(final.roster.participant('second').state.injury.conditions.has(Condition.BROKEN))
                self.assertIs(final.wizard, owner.wizard)
                self.assertEqual(final.consumed_execution_ids, ('cast', 'broken'))
                self.assertIsNone(result.interruption)
                self.assertEqual(final.round_state.completed_turn_entity_ids, ('wizard', 'friend'))

    def test_wizard_recover_preserves_real_wound_daily_and_both_histories(self):
        source, attack, owner = wounded_broken_wizard(1)
        request = wizard_recovery(owner)
        result = execute_npc_broken_recover(request, CountingDice([1, 2, 3]))
        final = apply_npc_broken_recover_result(owner, result)
        injury = final.roster.participant(final.wizard.actor_id).state.injury
        self.assertEqual(injury.wounds, attack.resolution.target_state.wounds)
        self.assertEqual(injury.active_wound_effects, attack.resolution.target_state.active_wound_effects)
        self.assertTrue(injury.conditions.has(Condition.DRAINED))
        self.assertFalse(injury.conditions.has(Condition.BROKEN))
        self.assertEqual(final.wizard.magic_state, WizardMagicState(2, 1, 'lore:battle-magic', 1))
        self.assertIsNone(final.pending_interruption)
        self.assertEqual(final.champion_attack.daily_wounds, owner.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, owner.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.champion_attack.consumed_execution_ids, (source.attack.execution.id,))
        self.assertEqual(final.consumed_execution_ids, (source.attack.execution.id, 'broken'))
        self.assertEqual(final.champion_attack.roster, final.roster)
        self.assertIs(final.champion_attack.round_state, final.round_state)
        self.assertIs(final.round_state.active_turn.action_slots[0].execution, result.interruption.action)

    def test_failed_wizard_recover_triggers_pending_without_clearing_casting_or_rolling_table(self):
        source, _, owner = wounded_broken_wizard(2)
        rng = CountingDice([10] * 3)
        result = execute_npc_broken_recover(wizard_recovery(owner), rng)
        final = result.state
        self.assertEqual(rng.calls, 3)
        self.assertTrue(final.roster.participant(final.wizard.actor_id).state.injury.conditions.has(Condition.BROKEN))
        self.assertIs(final.pending_interruption, result.interruption)
        self.assertEqual(final.wizard.magic_state, WizardMagicState(3, 1, 'lore:battle-magic', 1))
        self.assertEqual(final.pending_interruption.miscast_pool.roll_request.bonus_dice, 0)
        self.assertEqual(final.champion_attack.daily_wounds, owner.champion_attack.daily_wounds)
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            NpcRosterChampionAttackRequest(final, source.attack)
        with self.assertRaisesRegex(ValueError, 'pending interruption'):
            prepare_npc_roster_casting(request_id='next', state=final, selected_zone_id='arena', targets=(),
                facts=casting_input().facts, policy=casting_input().policy)


if __name__ == '__main__':
    unittest.main()
