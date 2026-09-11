from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import (
    attack_execution_request,
    completed_aim,
    follow_up_request,
    reserve_action,
)
from tests.unit.test_k1_ranged_weapon_attack_resolution import ranged_request
from towr.domain.aim_models import (
    AIM_FOLLOW_UP_RULE_ID,
    AimFollowUpOutcome,
)
from towr.domain.aim_ranged_weapon_attack_models import (
    AIM_RANGED_ATTACK_EXECUTION_RULE_ID,
    AimRangedWeaponAttackExecutionRequest,
)
from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionRequest,
)
from towr.domain.reload_models import (
    FreeReloadWeaponState,
    ReloadableWeaponState,
    create_initial_ranged_weapon_reload_state,
)
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId,
    ranged_weapon_reload_profile,
)
from towr.domain.test_models import DiceModifier, Skill, TestProfile
from towr.domain.turn_models import ActionSlotGrant, CombatActionKind
from towr.rules.aim_ranged_weapon_attack_resolution import (
    execute_aim_ranged_weapon_attack,
)
from towr.rules.aim_resolution import resolve_aim_follow_up
from towr.rules.attack_action_execution import ATTACK_ACTION_EXECUTION_RULE_ID


def aimed_ranged_request(
    weapon: FreeReloadWeaponState | ReloadableWeaponState,
    *,
    aim_values: tuple[int, ...] = (1, 2, 10),
    next_cycle_id: str | None = None,
    uses_optional_reload_bonus: bool = False,
    existing_modifiers: tuple[DiceModifier, ...] = (),
    attack_skill: Skill = Skill.SHOOTING,
    target_id: str = "enemy",
    consumed: tuple[str, ...] = (),
) -> AimRangedWeaponAttackExecutionRequest:
    aim = completed_aim(values=aim_values)
    attack_state = reserve_action(
        aim.round_state,
        CombatActionKind.ATTACK,
        grant=ActionSlotGrant.ABILITY,
    )
    attack = attack_execution_request(
        state=attack_state,
        slot_index=2,
        target_id=target_id,
        attacker_profile=TestProfile(2, 5),
        existing_modifiers=existing_modifiers,
    )
    follow_up = resolve_aim_follow_up(
        follow_up_request(
            aim,
            attack=attack,
            skill=attack_skill,
        )
    )
    prepared_attack = follow_up.attack or attack
    ranged = ranged_request(
        weapon,
        request_id="profiled:aim-ranged-attack",
        source=prepared_attack,
        next_cycle_id=next_cycle_id,
        uses_optional_reload_bonus=uses_optional_reload_bonus,
    )
    return AimRangedWeaponAttackExecutionRequest(
        id="consume:aim-ranged-attack",
        aim_follow_up=follow_up,
        ranged_attack=ranged,
        consumed_aim_follow_up_ids=consumed,
    )


class K1AimRangedWeaponAttackResolutionTests(unittest.TestCase):
    def test_aim_bonus_executes_one_free_profile_attack(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "longbow:hero:1",
            RangedWeaponId.LONGBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        request = aimed_ranged_request(
            weapon,
            consumed=("aim:follow-up:older",),
        )

        result = execute_aim_ranged_weapon_attack(
            request,
            SequenceRandom([1, 10, 10, 10]),
        )

        self.assertIs(result.ranged_attack.weapon_state, weapon)
        trace = result.ranged_attack.attack.resolution.attack.attacker_test.trace
        self.assertEqual(trace.regular_dice_delta, 2)
        self.assertEqual(trace.rolled_dice, 4)
        self.assertTrue(result.ranged_attack.attack.slot.executed)
        self.assertEqual(
            result.ranged_attack.attack.slot.execution.executor_rule_id,
            ATTACK_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(
            result.consumed_aim_follow_up_ids,
            ("aim:follow-up:older", request.aim_follow_up.request_id),
        )

    def test_crossbow_aim_opens_profile_reload_cycle(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "crossbow:hero:1",
            RangedWeaponId.CROSSBOW,
        )
        assert isinstance(weapon, ReloadableWeaponState)

        result = execute_aim_ranged_weapon_attack(
            aimed_ranged_request(
                weapon,
                next_cycle_id="crossbow:hero:1:reload:1",
            ),
            SequenceRandom([1, 10, 10, 10]),
        )

        self.assertFalse(result.ranged_attack.weapon_state.loaded)
        self.assertEqual(result.ranged_attack.weapon_state.required_successes, 2)
        self.assertEqual(
            result.ranged_attack.weapon_state.reload_cycle_id,
            "crossbow:hero:1:reload:1",
        )

    def test_aim_and_repeater_bonuses_stack_before_one_attack(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "repeater-pistol:hero:1",
            RangedWeaponId.REPEATER_PISTOL,
        )
        assert isinstance(weapon, ReloadableWeaponState)
        repeater = ranged_weapon_reload_profile(
            weapon.weapon_id
        ).optional_bonus_modifier()
        request = aimed_ranged_request(
            weapon,
            aim_values=(1, 10, 10),
            next_cycle_id="repeater-pistol:hero:1:reload:1",
            uses_optional_reload_bonus=True,
            existing_modifiers=(repeater,),
        )

        result = execute_aim_ranged_weapon_attack(
            request,
            SequenceRandom([1, 10, 10, 10]),
        )

        trace = result.ranged_attack.attack.resolution.attack.attacker_test.trace
        self.assertEqual(trace.regular_dice_delta, 3)
        self.assertEqual(trace.rolled_dice, 4)
        self.assertFalse(result.ranged_attack.weapon_state.loaded)
        self.assertEqual(result.ranged_attack.weapon_state.required_successes, 3)

    def test_zero_success_aim_is_still_consumed_by_shooting(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "shortbow:hero:1",
            RangedWeaponId.SHORTBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        request = aimed_ranged_request(
            weapon,
            aim_values=(8, 9, 10),
        )
        self.assertIsNone(request.aim_follow_up.modifier)

        result = execute_aim_ranged_weapon_attack(
            request,
            SequenceRandom([1, 10]),
        )

        self.assertEqual(
            result.consumed_aim_follow_up_ids,
            (request.aim_follow_up.request_id,),
        )
        self.assertEqual(
            result.ranged_attack.attack.resolution.attack.attacker_test.trace
            .regular_dice_delta,
            0,
        )

    def test_lost_throwing_mismatched_and_replayed_aim_are_rejected(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "warbow:hero:1",
            RangedWeaponId.WARBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)

        with self.assertRaisesRegex(ValueError, "was not applied"):
            aimed_ranged_request(weapon, target_id="enemy:other")
        with self.assertRaisesRegex(ValueError, "requires Shooting"):
            aimed_ranged_request(weapon, attack_skill=Skill.THROWING)

        request = aimed_ranged_request(weapon)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            replace(
                request,
                consumed_aim_follow_up_ids=(request.aim_follow_up.request_id,),
            )
        foreign = replace(
            request.ranged_attack.attack,
            id="attack:foreign-aim-preparation",
        )
        foreign_ranged = replace(request.ranged_attack, attack=foreign)
        with self.assertRaisesRegex(ValueError, "share the prepared Attack"):
            replace(request, ranged_attack=foreign_ranged)

    def test_failure_does_not_consume_and_result_is_closed(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "sling:hero:1",
            RangedWeaponId.SLING,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        request = aimed_ranged_request(weapon)

        with self.assertRaises(RuntimeError):
            execute_aim_ranged_weapon_attack(request, SequenceRandom([]))
        self.assertEqual(request.consumed_aim_follow_up_ids, ())

        result = execute_aim_ranged_weapon_attack(
            request,
            SequenceRandom([1, 10, 10, 10]),
        )
        self.assertIn(AIM_FOLLOW_UP_RULE_ID, result.applied_rule_ids)
        self.assertIn(
            AIM_RANGED_ATTACK_EXECUTION_RULE_ID,
            result.applied_rule_ids,
        )
        with self.assertRaisesRegex(ValueError, "append"):
            replace(result, consumed_aim_follow_up_ids=())
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(
                result,
                applied_rule_ids=(AIM_RANGED_ATTACK_EXECUTION_RULE_ID,),
            )


if __name__ == "__main__":
    unittest.main()
