from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import completed_aim
from tests.unit.test_k1_ranged_weapon_attack_preparation import aim_and_attack
from tests.unit.test_k1_reload_resolution import reload_request, weapon_state
from towr.domain.aim_consumption_models import (
    AIM_LOSS_CONSUMPTION_RULE_ID, AimConsumptionState, AimLossConsumptionRequest,
)
from towr.domain.aim_models import AimFollowUpRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    ImproviseKind, ManoeuvreKind,
)
from towr.rules.aim_consumption_resolution import consume_lost_aim
from towr.rules.aim_resolution import resolve_aim_follow_up
from towr.rules.reload_resolution import execute_reload_action
from towr.rules.turn_resolution import reserve_combat_action_slot


def request(values=(1, 5, 10)):
    aim = completed_aim(values=values)
    reload = execute_reload_action(reload_request(weapon_state(2), action_number=2, rolls=2), SequenceRandom([10, 10]))
    receipt = reload.slot.execution
    follow_up = resolve_aim_follow_up(AimFollowUpRequest(
        "aim:lost", aim, "hero", receipt.id, receipt.declaration,
    ))
    return AimLossConsumptionRequest(
        "consume:aim-loss", AimConsumptionState("hero", ("aim:older",), ("follow:older",)), follow_up, receipt,
    )


class K1AimConsumptionTests(unittest.TestCase):
    def test_registers_zero_or_positive_aim_loss_once_without_executing_actions(self):
        for values in ((1, 5, 10), (10, 10, 10)):
            with self.subTest(values=values):
                source = request(values)
                before = deepcopy(source)
                with patch("towr.rules.aim_resolution.resolve_aim_follow_up") as follow_up, \
                     patch("towr.rules.reload_resolution.execute_reload_action") as reload:
                    result = consume_lost_aim(source)
                follow_up.assert_not_called()
                reload.assert_not_called()
                self.assertIs(result.source_request, source)
                self.assertIs(result.previous_state, source.state)
                self.assertEqual(result.state.consumed_aim_source_ids, ("aim:older", "aim:execute"))
                self.assertEqual(result.state.consumed_aim_follow_up_ids, ("follow:older", "aim:lost"))
                self.assertEqual(result.state.actor_id, "hero")
                self.assertIn(AIM_LOSS_CONSUMPTION_RULE_ID, result.applied_rule_ids)
                self.assertIn(source.action.executor_rule_id, result.applied_rule_ids)
                self.assertTrue(set(source.follow_up.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertTrue(set(source.follow_up.source_request.aim.applied_rule_ids) <= set(result.applied_rule_ids))
                self.assertEqual(source, before)
                with self.assertRaises(FrozenInstanceError):
                    result.state.actor_id = "other"

    def test_replay_rejects_original_source_even_with_new_request_and_follow_up_ids(self):
        source = request()
        result = consume_lost_aim(source)
        for follow_up in (source.follow_up, resolve_aim_follow_up(replace(source.follow_up.source_request, id="new:follow"))):
            with self.subTest(id=follow_up.request_id), self.assertRaisesRegex(ValueError, "source was already consumed"):
                replace(source, id="new:registration", state=result.state, follow_up=follow_up)

    def test_consumed_follow_up_is_rejected_even_without_source_history(self):
        source = request()
        with self.assertRaisesRegex(ValueError, "follow-up was already consumed"):
            replace(source, state=AimConsumptionState("hero", consumed_aim_follow_up_ids=(source.follow_up.request_id,)))

    def test_same_turn_second_action_and_later_turn_first_action_are_allowed(self):
        source = request()
        aim = source.follow_up.source_request.aim
        reserved = reserve_combat_action_slot(CombatActionSlotRequest(
            "slot:reload", aim.round_state, "hero", source.action.declaration,
            ActionSlotGrant.ABILITY, "RULE-ABILITY:test-extra-action",
        )).state
        reload = execute_reload_action(reload_request(
            weapon_state(2), round_state=reserved, slot_index=2, rolls=2,
        ), SequenceRandom([1, 10]))
        follow_up = resolve_aim_follow_up(replace(source.follow_up.source_request, next_action_id=reload.request_id))
        self.assertEqual(consume_lost_aim(replace(source, follow_up=follow_up, action=reload.slot.execution)).state,
                         consume_lost_aim(source).state)
        # Receipt chronology has no round expiry; identifying the actual next action is caller-owned.
        consume_lost_aim(replace(source, action=replace(source.action, round_number=5)))

    def test_same_or_earlier_action_and_later_turn_second_slot_are_rejected(self):
        source = request()
        for round_number, slot in ((1, 1), (2, 2)):
            with self.subTest(round=round_number, slot=slot), self.assertRaises(ValueError):
                replace(source, action=replace(source.action, round_number=round_number, slot_index=slot))

    def test_actor_and_exact_follow_up_receipt_binding_are_required(self):
        source = request()
        for changes in (
            {"state": AimConsumptionState("other")},
            {"action": replace(source.action, actor_id="other")},
            {"action": replace(source.action, id="other:action")},
            {"action": replace(source.action, declaration=CombatActionDeclaration(CombatActionKind.RECOVER))},
            {"action": replace(source.action, declaration=replace(source.action.declaration, improvise_approach_id="other:weapon"))},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(source, **changes)

    def test_applied_aim_and_attacking_declarations_are_out_of_scope(self):
        source = request()
        aim, attack = aim_and_attack()
        applied = resolve_aim_follow_up(AimFollowUpRequest(
            "aim:applied", aim, "hero", attack.id, CombatActionDeclaration(CombatActionKind.ATTACK), Skill.SHOOTING, attack,
        ))
        with self.assertRaisesRegex(ValueError, "requires LOST"):
            replace(source, follow_up=applied)
        for declaration in (
            CombatActionDeclaration(CombatActionKind.MANOEUVRE, manoeuvre=ManoeuvreKind.CHARGE),
            CombatActionDeclaration(CombatActionKind.IMPROVISE, improvise_kind=ImproviseKind.SKILL,
                                    improvise_approach_id="attack:skill", improvise_produces_attack=True),
        ):
            follow_up = resolve_aim_follow_up(replace(source.follow_up.source_request, declaration=declaration))
            with self.subTest(declaration=declaration), self.assertRaisesRegex(ValueError, "non-attacking"):
                replace(source, follow_up=follow_up, action=replace(source.action, declaration=declaration))

    def test_histories_normalize_and_reject_duplicate_or_empty_ids(self):
        self.assertEqual(AimConsumptionState("hero", ["aim:old"], ["follow:old"]),
                         AimConsumptionState("hero", ("aim:old",), ("follow:old",)))
        for field in ("consumed_aim_source_ids", "consumed_aim_follow_up_ids"):
            for ids in ("not-a-tuple", ("x", "x"), ("",), (7,)):
                with self.subTest(field=field, ids=ids), self.assertRaises((ValueError, TypeError)):
                    AimConsumptionState("hero", **{field: ids})

    def test_result_rejects_forged_state_provenance_and_trace(self):
        source = request()
        result = consume_lost_aim(source)
        for changes in (
            {"request_id": "foreign"}, {"rule_id": "foreign"}, {"source_request": None},
            {"previous_state": AimConsumptionState("hero")}, {"state": source.state},
            {"state": replace(result.state, actor_id="other")}, {"applied_rule_ids": ()},
            {"applied_rule_ids": (*result.applied_rule_ids, "foreign")},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(result, **changes)

    def test_bad_types_and_unknown_rule_are_rejected(self):
        source = request()
        for changes in ({"state": None}, {"follow_up": None}, {"action": None}, {"rule_id": "foreign"}, {"id": ""}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                replace(source, **changes)
        with self.assertRaises(TypeError):
            consume_lost_aim(None)
