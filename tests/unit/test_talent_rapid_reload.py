"""Rapid Reload's typed action budget and complete successful-Test source."""
from dataclasses import replace
import pickle
import unittest

from tests.helpers import SequenceRandom
from tests.support.talent_sources import paid_talent
from tests.unit.test_k1_reload_resolution import reload_request, weapon_state
from towr.domain.talent_action_grant_models import RAPID_RELOAD_RULE_ID, RapidReloadGrant
from towr.domain.talent_catalog import TalentId
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlot,
    CombatActionSlotRequest,
)
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import reserve_combat_action_slot


def result(values):
    return execute_reload_action(reload_request(weapon_state()), SequenceRandom(values))


def grant(source, kind=CombatActionKind.ATTACK, **changes):
    fields = dict(actor_id='hero', round_number=1, slot_request_id='rapid:reserve',
        source_reload=source, owned_talent=paid_talent(TalentId.RAPID_RELOAD),
        target_id='enemy', action_kind=kind)
    fields.update(changes)
    return RapidReloadGrant(**fields)


def request(value):
    return CombatActionSlotRequest(value.slot_request_id, value.source_reload.round_state,
        value.actor_id, CombatActionDeclaration(value.action_kind), ActionSlotGrant.ABILITY,
        RAPID_RELOAD_RULE_ID, rapid_reload=value)


class RapidReloadGrantTests(unittest.TestCase):
    def test_completed_success_can_reserve_exactly_one_second_attack_and_pickles(self):
        source = result([1, 2, 3])
        value = grant(source)
        self.assertEqual(pickle.loads(pickle.dumps(value)), value)
        reservation = reserve_combat_action_slot(request(value))
        self.assertEqual(reservation.slot.rapid_reload.source_reload, source)
        self.assertEqual(value.weapon_instance_id, source.state.weapon_instance_id)
        self.assertEqual(value.first_execution, source.slot.execution)
        self.assertEqual(len(reservation.state.active_turn.action_slots), 2)
        with self.assertRaises(ValueError):
            reserve_combat_action_slot(replace(request(value), state=reservation.state))

    def test_successful_incomplete_exacting_grants_aim_but_never_an_unloaded_attack(self):
        source = result([1, 10, 10])
        self.assertTrue(source.exacting.test_result.succeeded)
        self.assertFalse(source.completed)
        reservation = reserve_combat_action_slot(request(grant(source, CombatActionKind.AIM)))
        self.assertIs(reservation.slot.declaration.kind, CombatActionKind.AIM)
        with self.assertRaises(ValueError):
            grant(source)

    def test_zero_success_and_foreign_talent_actor_round_target_are_rejected(self):
        with self.assertRaises(ValueError):
            grant(result([10, 10, 10]), CombatActionKind.AIM)
        source = result([1, 1, 1])
        for changes in (dict(actor_id='another'), dict(round_number=2), dict(round_number=True),
                dict(owned_talent=paid_talent(TalentId.MIGHTY_BLOW)), dict(target_id='hero'),
                dict(action_kind=CombatActionKind.RECOVER), dict(ranged_bonus=1)):
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                grant(source, **changes)

    def test_raw_rule_id_forged_source_and_changed_declaration_cannot_reserve(self):
        source = result([1, 1, 1])
        value = grant(source)
        with self.assertRaises(ValueError):
            CombatActionSlot(2, CombatActionDeclaration(CombatActionKind.ATTACK),
                ActionSlotGrant.ABILITY, RAPID_RELOAD_RULE_ID)
        with self.assertRaises(ValueError):
            replace(request(value), rapid_reload=None)
        with self.assertRaises(ValueError):
            replace(request(value), declaration=CombatActionDeclaration(CombatActionKind.AIM))
        forged = pickle.loads(pickle.dumps(value))
        object.__setattr__(forged.source_reload.exacting.test_result.trace, 'successes', 0)
        with self.assertRaises(ValueError):
            request(forged)

    def test_aim_cannot_declare_a_repeater_attack_mode(self):
        with self.assertRaises(ValueError):
            grant(result([1, 10, 10]), CombatActionKind.AIM, ranged_bonus=True)
        with self.assertRaises(ValueError):
            grant(result([1,1,1]),ranged_bonus=True)  # Ordinary Pistol has no mode.

    def test_staggered_actual_reload_source_cannot_authorize_the_talent(self):
        source=execute_reload_action(reload_request(weapon_state(),
            actor_conditions=ConditionState(frozenset((Condition.STAGGERED,)))),SequenceRandom([1,1,1]))
        with self.assertRaises(ValueError):
            grant(source)

    def test_finite_repeater_forecast_adds_same_turn_shot_only_after_completed_success(self):
        from towr.domain.pc_generated_ranged_advice import _repeater_choice
        self.assertFalse(_repeater_choice(.3,.5,(0.,0.,0.,1.),2,3,False))
        self.assertTrue(_repeater_choice(.3,.5,(0.,0.,0.,1.),2,3,True))
        for values in ((1.,),(0.,1.)):
            self.assertFalse(_repeater_choice(.3,.5,values,2,3,True))

    def test_mandatory_aim_forecast_costs_an_action_and_rapid_aim_never_adds_a_third(self):
        from towr.domain.pc_generated_ranged_advice import _repeater_choice
        # Current shot was already Aimed. Later shots must earn another Aim.
        self.assertFalse(_repeater_choice(.3,.5,(0.,0.,0.,1.),3,3,False,
            aim_required=True))
        self.assertTrue(_repeater_choice(.3,.5,(0.,0.,0.,1.),3,3,True,
            aim_required=True))
        self.assertFalse(_repeater_choice(.3,.5,(0.,1.),3,3,True,aim_required=True))


if __name__ == '__main__':
    unittest.main()
