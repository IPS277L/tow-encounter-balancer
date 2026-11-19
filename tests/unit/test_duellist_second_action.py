"""Duellist source authority, real action budget and typed once-only receipts."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from tests.helpers import SequenceRandom
from tests.support.weapon_fixtures import weapon_use
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest, DamageImpactSpec, DamageProfile, ResilienceProfile
from towr.domain.injury_models import ProfileInjuryState
from towr.domain.pc_duellist_models import duellist_action_index
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import InlineProfile, TestRequest
from towr.domain.turn_models import (
    DUELLIST_BLADES_RULE_ID, CROWN_OF_ANTLERS_RULE_ID, ENDURING_STRENGTH_RULE_ID,
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlot,
    CombatActionSlotRequest, CombatRoundState, CombatSide, CombatTurnParticipant,
    CombatTurnState, CrownOfAntlersGrant, DuellistBladesGrant, EnduringStrengthGrant,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_inventory_models import (
    WeaponGrip, WeaponItemLocation, WeaponItemSource, initial_weapon_inventory,
)
from towr.domain.weapon_use_models import build_weapon_use
from towr.rules.attack_action_execution import execute_attack_action
from towr.rules.turn_resolution import reserve_combat_action_slot


def first_clock():
    return CombatRoundState(1, (
        CombatTurnParticipant('actor', CombatSide.PLAYERS_AND_ALLIES),
        CombatTurnParticipant('victim', CombatSide.OPPOSITION),
        CombatTurnParticipant('ally', CombatSide.PLAYERS_AND_ALLIES)),
        active_turn=CombatTurnState('actor', CombatSide.PLAYERS_AND_ALLIES, (
            CombatActionSlot(1, CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.STANDARD),)))


def attack_request(state, *, index=1, target='victim'):
    attack = AttackRequest(f'a{index}:attack', TestRequest(f'a{index}:test', InlineProfile(1, 3)),
        None, DamageImpactSpec(DamageProfile(1), ResilienceProfile(99)), True, False)
    kernel = KernelAttackRequest(f'a{index}:kernel', target, attack, TargetInjuryPolicy.MINION,
        ProfileInjuryState(0, 1), False, False)
    return AttackActionExecutionRequest(f'a{index}:execute', state, 'actor', target, index, kernel)


def duellist_request():
    first = execute_attack_action(attack_request(first_clock()), SequenceRandom([1]))
    use = weapon_use(WeaponKind.DUELLIST_BLADES)
    grant = DuellistBladesGrant('actor', 1, 'reserve2', first.slot.execution, use, 'victim')
    return CombatActionSlotRequest('reserve2', first.state, 'actor',
        CombatActionDeclaration(CombatActionKind.ATTACK), ActionSlotGrant.ABILITY,
        DUELLIST_BLADES_RULE_ID, duellist_blades=grant)


class DuellistSecondActionTests(unittest.TestCase):
    def test_real_first_receipt_grants_a_distinct_second_attack(self):
        request = duellist_request()
        reserved = reserve_combat_action_slot(request)
        self.assertEqual(reserved.slot.index, 2)
        self.assertEqual(reserved.slot.duellist_blades, request.duellist_blades)
        self.assertIsNone(reserved.slot.enduring_strength)
        self.assertIsNone(reserved.slot.crown_of_antlers)
        self.assertEqual(reserved.applied_rule_ids,
            ('RULE-COMBAT-002:action-budget', DUELLIST_BLADES_RULE_ID))
        self.assertEqual(reserved.state.active_turn.action_slots[0], request.state.active_turn.action_slots[0])
        second = execute_attack_action(attack_request(reserved.state, index=2), SequenceRandom([1]))
        self.assertTrue(second.slot.executed)
        self.assertEqual(second.slot.duellist_blades.weapon_use.primary_item_id,
            request.duellist_blades.weapon_use.primary_item_id)
        with self.assertRaises(ValueError):
            execute_attack_action(attack_request(second.state, index=2), Mock())

    def test_rule_id_alone_never_authorizes_a_repeated_attack(self):
        request = duellist_request()
        with self.assertRaises(ValueError):
            replace(request, duellist_blades=None)
        with self.assertRaises(ValueError):
            CombatActionSlot(2, request.declaration, ActionSlotGrant.ABILITY, DUELLIST_BLADES_RULE_ID)

    def test_other_weapon_or_actor_cannot_be_the_source(self):
        request = duellist_request()
        for use in (weapon_use(WeaponKind.GREATSWORD), weapon_use(WeaponKind.UNARMED)):
            with self.subTest(kind=use.kind), self.assertRaises(ValueError):
                replace(request.duellist_blades, weapon_use=use)
        with self.assertRaises(ValueError):
            replace(request.duellist_blades, actor_id='victim')

    def test_wrong_round_slot_request_or_target_is_rejected(self):
        request = duellist_request()
        for change in (dict(round_number=2), dict(slot_request_id='other'), dict(target_id='actor'),
                dict(target_id='ally'), dict(target_id='absent')):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError, KeyError)):
                replace(request, duellist_blades=replace(request.duellist_blades, **change))

    def test_grant_cannot_borrow_fate_another_ability_or_another_action(self):
        request = duellist_request()
        for change in (dict(grant=ActionSlotGrant.FATE, grant_rule_id=None),
                dict(grant_rule_id=ENDURING_STRENGTH_RULE_ID),
                dict(grant_rule_id=CROWN_OF_ANTLERS_RULE_ID),
                dict(declaration=CombatActionDeclaration(CombatActionKind.RECOVER))):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                replace(request, **change)

    def test_no_combined_bear_or_crown_grant(self):
        request = duellist_request()
        receipt = request.duellist_blades.first_execution
        bear = EnduringStrengthGrant('actor', 1, 'reserve2', receipt, 'first', 'victim')
        crown = CrownOfAntlersGrant('actor', 1, 'reserve2', receipt, 'victim', 'victim', 'trample')
        for change in (dict(enduring_strength=bear), dict(crown_of_antlers=crown)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(request, **change)
            with self.subTest(slot=change), self.assertRaises(ValueError):
                CombatActionSlot(2, request.declaration, ActionSlotGrant.ABILITY,
                    DUELLIST_BLADES_RULE_ID, duellist_blades=request.duellist_blades, **change)

    def test_foreign_or_unexecuted_first_cannot_grant_second(self):
        request = duellist_request()
        first = request.state.active_turn.action_slots[0]
        for replacement in (replace(first, execution=None),
                replace(first, execution=replace(first.execution, id='foreign'))):
            current = replace(request.state, active_turn=replace(request.state.active_turn,
                action_slots=(replacement,)))
            with self.assertRaises(ValueError):
                replace(request, state=current)

    def test_no_third_action_even_if_the_original_source_still_exists(self):
        request = duellist_request()
        second = reserve_combat_action_slot(request)
        with self.assertRaises(ValueError):
            replace(request, state=second.state)
        with self.assertRaises(ValueError):
            CombatTurnState('actor', CombatSide.PLAYERS_AND_ALLIES,
                (*second.state.active_turn.action_slots, replace(second.slot, index=2)))

    def test_nested_equal_aliases_and_mutated_weapon_source_are_readmitted(self):
        state = reserve_combat_action_slot(duellist_request()).state
        for subject, field, value in (('grant', 'round_number', 1.0),
                ('receipt', 'slot_index', True), ('declaration', 'improvise_produces_attack', 0),
                ('item', 'unit_index', False)):
            changed = deepcopy(state)
            grant = changed.active_turn.action_slots[1].duellist_blades
            record = {'grant': grant, 'receipt': grant.first_execution,
                'declaration': changed.active_turn.action_slots[1].declaration,
                'item': grant.weapon_use.primary}[subject]
            object.__setattr__(record, field, value)
            self.assertEqual(changed, state)
            with self.subTest(subject=subject), self.assertRaises(TypeError):
                replace(changed)

    def test_wrong_second_target_is_rejected_before_rng(self):
        state = reserve_combat_action_slot(duellist_request()).state
        rng = Mock()
        with self.assertRaises(ValueError):
            execute_attack_action(attack_request(state, index=2, target='ally'), rng)
        rng.randint.assert_not_called()

    def test_quality_index_needs_the_actual_slot_and_same_physical_item(self):
        request = duellist_request()
        use = request.duellist_blades.weapon_use
        self.assertEqual(duellist_action_index(SimpleNamespace(round_state=first_clock()), use), 1)
        self.assertIsNone(duellist_action_index(SimpleNamespace(round_state=request.state), use))
        second = reserve_combat_action_slot(request)
        self.assertEqual(duellist_action_index(SimpleNamespace(round_state=second.state), use), 2)
        self.assertIsNone(duellist_action_index(SimpleNamespace(round_state=second.state),
            weapon_use(WeaponKind.SWORD)))
        other_inventory = initial_weapon_inventory('actor', (WeaponItemSource('other',
            WeaponKind.DUELLIST_BLADES, WeaponItemLocation.HELD, WeaponGrip.BOTH),))
        current = build_weapon_use('actor', other_inventory, other_inventory.items[0].id)
        with self.assertRaises(ValueError):
            duellist_action_index(SimpleNamespace(round_state=second.state), current)


if __name__ == '__main__':
    unittest.main()
