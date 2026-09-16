from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import aim_request, attack_execution_request
from tests.unit.test_k1_hidden_attack_resolution import (
    execution_request as hidden_request,
)
from tests.unit.test_k1_move_quietly_resolution import reserve_action
from tests.unit.test_k1_ranged_weapon_attack_preparation import preparation_request
from towr.domain.prepared_hidden_ranged_attack_models import (
    PreparedHiddenRangedAttackExecutionRequest,
)
from towr.domain.prepared_ranged_weapon_attack_models import (
    PreparedRangedWeaponAttackExecutionRequest,
)
from towr.domain.ranged_weapon_profiles import (
    RangedReloadTrigger,
    RangedWeaponId,
    RangedWeaponRange,
    ranged_weapon_reload_profile,
)
from towr.domain.test_models import TestProfile, TestRequest
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
    CombatRoundState,
    CombatTurnStartRequest,
)
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.prepared_hidden_ranged_attack_resolution import (
    execute_prepared_hidden_ranged_attack,
)
from towr.rules.prepared_ranged_weapon_attack_resolution import (
    execute_prepared_ranged_weapon_attack,
)
from towr.rules.ranged_weapon_attack_preparation import prepare_ranged_weapon_attack
from towr.rules.turn_resolution import start_combat_turn


def request(
    weapon=RangedWeaponId.LONGBOW, *, aim_values=None, repeater_bonus=False,
):
    hidden = hidden_request(consumed=("hidden:older",))
    aim = None
    attack = hidden.attack
    if aim_values is not None:
        # Orchestration supplies a later round, with the original hiding placement.
        state = start_combat_turn(CombatTurnStartRequest(
            "turn:hero:2",
            CombatRoundState(
                round_number=2,
                participants=hidden.move_quietly.round_state.participants,
            ),
            "hero",
        )).state
        state = reserve_action(state, CombatActionDeclaration(CombatActionKind.AIM))
        aim = execute_aim_action(
            aim_request(state, target_id="scout"), SequenceRandom(aim_values)
        )
        state = reserve_action(
            aim.round_state, CombatActionDeclaration(CombatActionKind.ATTACK),
            grant=ActionSlotGrant.ABILITY,
        )
        attack = attack_execution_request(
            state=state, slot_index=2, target_id="scout", attacker_profile=TestProfile(2, 5),
        )
    profile = ranged_weapon_reload_profile(weapon)
    if repeater_bonus:
        kernel = attack.kernel_request
        attack = replace(attack, kernel_request=replace(
            kernel, attack=replace(
                kernel.attack,
                attacker_test=replace(
                    kernel.attack.attacker_test,
                    dice_modifiers=(profile.optional_bonus_modifier(),),
                ),
            ),
        ))
    reloads = profile.trigger is RangedReloadTrigger.AFTER_EVERY_SHOT or repeater_bonus
    preparation = prepare_ranged_weapon_attack(preparation_request(
        weapon, attack=attack, aim=aim, lore=True,
        target_range=RangedWeaponRange.SHORT if weapon is RangedWeaponId.REPEATER_PISTOL
        else RangedWeaponRange.MEDIUM,
        next_cycle=f"weapon:{weapon.value}:hero:1:reload:1" if reloads else None,
        uses_repeater_bonus=repeater_bonus,
    ))
    hidden = replace(
        hidden, attack=preparation.execution.attack,
        spatial_state=replace(hidden.spatial_state, round_number=attack.state.round_number),
    )
    return PreparedHiddenRangedAttackExecutionRequest(
        id="execute:prepared-hidden", hidden_attack=hidden,
        prepared_attack=PreparedRangedWeaponAttackExecutionRequest(
            id="execute:prepared", preparation=preparation,
            consumed_aim_follow_up_ids=("aim:older",),
        ),
    )


class K1PreparedHiddenRangedAttackResolutionTests(unittest.TestCase):
    def assert_transition(self, source, result):
        hidden = source.hidden_attack
        self.assertEqual(result.consumed_opportunity_ids,
                         ("hidden:older", hidden.opportunity.id))
        self.assertEqual(result.revealed_hiding_position_id, hidden.hiding_position_id)
        self.assertEqual(result.prepared_attack.source_request, source.prepared_attack)
        before = hidden.attack.state.active_turn.action_slots
        after = result.ranged_attack.attack.state.active_turn.action_slots
        self.assertEqual(len(before), len(after))
        self.assertEqual(sum(s.executed for s in after), sum(s.executed for s in before) + 1)
        self.assertEqual(after[:-1], before[:-1])
        self.assertTrue(set(hidden.move_quietly.applied_rule_ids) <= set(result.applied_rule_ids))
        self.assertTrue(set(source.prepared_attack.preparation.applied_rule_ids)
                        <= set(result.applied_rule_ids))
        self.assertIsNone(result.ranged_attack.attack.resolution.attack.defender_test)

    def test_free_shot_calls_prepared_executor_once_and_keeps_both_traces(self):
        source = request()
        rng = SequenceRandom([1, 10, 7])
        decisions = Mock()
        with patch(
            "towr.rules.prepared_hidden_ranged_attack_resolution.execute_prepared_ranged_weapon_attack",
            wraps=execute_prepared_ranged_weapon_attack,
        ) as execute:
            result = execute_prepared_hidden_ranged_attack(source, rng, decisions=decisions)
        execute.assert_called_once_with(source.prepared_attack, rng, decisions=decisions)
        self.assertEqual(rng.randint(1, 10), 7)
        self.assertIs(result.ranged_attack.weapon_state, source.prepared_attack.preparation.execution.weapon_state)
        self.assertEqual(result.consumed_aim_follow_up_ids, ("aim:older",))
        self.assert_transition(source, result)

    def test_reloadable_hit_and_miss_each_consume_one_hidden_opportunity(self):
        for values in ([1, 10, 1], [10, 10]):
            with self.subTest(values=values):
                source = request(RangedWeaponId.CROSSBOW)
                rng = SequenceRandom([*values, 7])
                result = execute_prepared_hidden_ranged_attack(source, rng)
                self.assertEqual(rng.randint(1, 10), 7)
                self.assertFalse(result.ranged_attack.weapon_state.loaded)
                self.assertEqual(result.ranged_attack.weapon_state.reload_cycle_id,
                                 "weapon:crossbow:hero:1:reload:1")
                self.assert_transition(source, result)

    def test_aim_zero_positive_and_repeater_choices_keep_separate_chains(self):
        for aim_values in ((10, 10, 10), (1, 10, 10)):
            for bonus in (False, True):
                with self.subTest(aim_values=aim_values, bonus=bonus):
                    source = request(RangedWeaponId.REPEATER_PISTOL,
                                     aim_values=aim_values, repeater_bonus=bonus)
                    count = min(4, 2 + (aim_values[0] == 1) + (2 if bonus else 0))
                    rng = SequenceRandom([10] * count + [7])
                    result = execute_prepared_hidden_ranged_attack(source, rng)
                    self.assertEqual(rng.randint(1, 10), 7)
                    self.assertEqual(result.consumed_aim_follow_up_ids, (
                        "aim:older", source.prepared_attack.preparation.aim_follow_up.request_id,
                    ))
                    self.assertEqual(result.previous_consumed_aim_follow_up_ids, ("aim:older",))
                    self.assertEqual(result.ranged_attack.weapon_state.loaded, not bonus)
                    self.assert_transition(source, result)

    def test_preparation_and_hidden_preflight_must_bind_exact_same_attack(self):
        source = request()
        for changed in (
            replace(source.hidden_attack.attack, id="attack:foreign"),
            source.prepared_attack.preparation.source_request.attack,
        ):
            with self.subTest(changed=changed.id):
                with self.assertRaisesRegex(ValueError, "share one Attack"):
                    replace(source, hidden_attack=replace(source.hidden_attack, attack=changed))
        for invalid in ("", source.hidden_attack.id, source.prepared_attack.id,
                        source.prepared_attack.preparation.request_id):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                replace(source, id=invalid)
        with self.assertRaises(TypeError):
            replace(source, prepared_attack=source.prepared_attack.preparation)
        with self.assertRaises(ValueError):
            replace(source, rule_id="foreign")

    def test_aware_moved_opposed_and_replayed_contexts_reject_before_rng(self):
        source = request(aim_values=(1, 10, 10))
        rng = Mock()
        hidden = source.hidden_attack
        attack = hidden.attack
        opposed = replace(attack, kernel_request=replace(
            attack.kernel_request, attack=replace(
                attack.kernel_request.attack,
                defender_test=TestRequest("defender", TestProfile(2, 5)),
            ),
        ))
        for changed in (
            {"target_is_unaware": False}, {"hiding_position_id": "elsewhere"},
            {"spatial_state": replace(hidden.spatial_state, placements=tuple(
                replace(p, zone_id="zone:d") if p.entity_id == hidden.actor_id else p
                for p in hidden.spatial_state.placements
            ))},
            {"attack": opposed}, {"consumed_opportunity_ids": (hidden.opportunity.id,)},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                execute_prepared_hidden_ranged_attack(
                    replace(source, hidden_attack=replace(hidden, **changed)), rng
                )
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(source.prepared_attack, consumed_aim_follow_up_ids=(
                source.prepared_attack.preparation.aim_follow_up.request_id,
            ))
        rng.randint.assert_not_called()

    def test_rng_failure_preserves_weapon_slot_and_both_chains(self):
        source = request(RangedWeaponId.CROSSBOW, aim_values=(1, 10, 10))
        with self.assertRaises(RuntimeError):
            execute_prepared_hidden_ranged_attack(source, SequenceRandom([]))
        self.assertEqual(source.hidden_attack.consumed_opportunity_ids, ("hidden:older",))
        self.assertEqual(source.prepared_attack.consumed_aim_follow_up_ids, ("aim:older",))
        self.assertTrue(source.prepared_attack.preparation.execution.weapon_state.loaded)
        self.assertFalse(source.hidden_attack.attack.state.active_turn.action_slots[-1].executed)
        result = execute_prepared_hidden_ranged_attack(source, SequenceRandom([10] * 3))
        self.assert_transition(source, result)

    def test_result_rejects_forged_preparation_reveal_consumption_and_trace(self):
        source = request()
        result = execute_prepared_hidden_ranged_attack(source, SequenceRandom([10, 10]))
        foreign = execute_prepared_ranged_weapon_attack(
            request(RangedWeaponId.WARBOW).prepared_attack, SequenceRandom([10, 10])
        )
        for changed in (
            {"prepared_attack": foreign}, {"request_id": "other"},
            {"revealed_hiding_position_id": "other"},
            {"previous_consumed_opportunity_ids": ()},
            {"consumed_opportunity_ids": ("hidden:older",)},
            {"applied_rule_ids": (result.rule_id,)},
            {"applied_rule_ids": (*result.applied_rule_ids, "invented")},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                replace(result, **changed)


if __name__ == "__main__":
    unittest.main()
