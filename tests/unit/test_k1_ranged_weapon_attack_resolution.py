from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_attack_action_execution import (
    execution_request,
    kernel_request,
    reserve_action,
    started_turn,
)
from tests.unit.test_k1_ranged_weapon_reload_profiles import (
    attack_source_with_modifier,
)
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionRequest,
)
from towr.domain.reload_models import (
    RELOAD_RULE_ID,
    FreeReloadWeaponState,
    ReloadableWeaponState,
    create_initial_ranged_weapon_reload_state,
)
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId,
    ranged_weapon_reload_profile,
)
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules.attack_action_execution import ATTACK_ACTION_EXECUTION_RULE_ID
from towr.rules.ranged_weapon_attack_resolution import (
    execute_ranged_weapon_attack,
)


def ranged_request(
    weapon: FreeReloadWeaponState | ReloadableWeaponState,
    *,
    request_id: str = "profiled-ranged-shot:1",
    attack_id: str = "execute:profiled-ranged-shot:1",
    kernel_id: str = "kernel:profiled-ranged-shot:1",
    next_cycle_id: str | None = None,
    source: AttackActionExecutionRequest | None = None,
    **changes,
) -> RangedWeaponAttackExecutionRequest:
    if source is None:
        round_state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )
        source = AttackActionExecutionRequest(
            id=attack_id,
            state=round_state,
            actor_id="hero",
            target_id="enemy",
            slot_index=1,
            kernel_request=kernel_request(request_id=kernel_id),
        )
    values = {
        "id": request_id,
        "attack_skill": Skill.SHOOTING,
        "attack": source,
        "weapon_state": weapon,
        "next_reload_cycle_id": next_cycle_id,
    }
    values.update(changes)
    return RangedWeaponAttackExecutionRequest(**values)


class K1RangedWeaponAttackResolutionTests(unittest.TestCase):
    def test_free_reload_profile_executes_attack_and_preserves_state(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "longbow:hero:1",
            RangedWeaponId.LONGBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)

        result = execute_ranged_weapon_attack(
            ranged_request(weapon),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIs(result.previous_weapon_state, weapon)
        self.assertIs(result.weapon_state, weapon)
        self.assertTrue(result.attack.slot.executed)
        self.assertEqual(
            result.attack.slot.execution.executor_rule_id,
            ATTACK_ACTION_EXECUTION_RULE_ID,
        )

    def test_reloadable_profile_routes_through_existing_transition(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "crossbow:hero:1",
            RangedWeaponId.CROSSBOW,
        )
        assert isinstance(weapon, ReloadableWeaponState)

        result = execute_ranged_weapon_attack(
            ranged_request(
                weapon,
                next_cycle_id="crossbow:hero:1:reload:1",
            ),
            SequenceRandom([10, 10, 10]),
        )

        self.assertFalse(result.weapon_state.loaded)
        self.assertEqual(result.weapon_state.required_successes, 2)
        self.assertEqual(
            result.weapon_state.reload_cycle_id,
            "crossbow:hero:1:reload:1",
        )
        self.assertTrue(result.attack.slot.executed)

    def test_repeater_bonus_uses_same_profile_aware_entry_point(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "repeater-handgun:hero:1",
            RangedWeaponId.REPEATER_HANDGUN,
        )
        assert isinstance(weapon, ReloadableWeaponState)
        modifier = ranged_weapon_reload_profile(
            weapon.weapon_id
        ).optional_bonus_modifier()
        source = attack_source_with_modifier(
            modifier,
            request_id="execute:repeater-handgun:bonus",
            kernel_id="kernel:repeater-handgun:bonus",
        )

        result = execute_ranged_weapon_attack(
            ranged_request(
                weapon,
                request_id="profiled-repeater-handgun:bonus",
                source=source,
                next_cycle_id="repeater-handgun:hero:1:reload:1",
                uses_optional_reload_bonus=True,
            ),
            SequenceRandom([10, 10, 10, 10, 10, 10]),
        )

        self.assertFalse(result.weapon_state.loaded)
        self.assertEqual(result.weapon_state.required_successes, 5)
        self.assertEqual(
            len(result.attack.state.active_turn.action_slots),
            1,
        )

    def test_free_profile_rejects_cycle_bonus_and_non_shooting(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "sling:hero:1",
            RangedWeaponId.SLING,
        )
        assert isinstance(weapon, FreeReloadWeaponState)

        with self.assertRaisesRegex(ValueError, "does not open"):
            ranged_request(weapon, next_cycle_id="sling:reload:invalid")
        with self.assertRaisesRegex(ValueError, "no Repeater bonus"):
            ranged_request(weapon, uses_optional_reload_bonus=True)
        with self.assertRaisesRegex(ValueError, "with Shooting"):
            ranged_request(weapon, attack_skill=Skill.THROWING)

    def test_failed_attack_does_not_create_a_weapon_transition(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "longbow:hero:1",
            RangedWeaponId.LONGBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        round_state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )
        invalid_source = execution_request(
            round_state,
            actor_id="enemy",
            request_id="execute:invalid-profiled-shot",
        )
        request = ranged_request(weapon, source=invalid_source)

        with self.assertRaisesRegex(ValueError, "does not own"):
            execute_ranged_weapon_attack(request, SequenceRandom([]))
        self.assertIsInstance(weapon, FreeReloadWeaponState)

    def test_result_is_closed_traced_and_inventory_free(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "shortbow:hero:1",
            RangedWeaponId.SHORTBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        result = execute_ranged_weapon_attack(
            ranged_request(weapon),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIn(RELOAD_RULE_ID, result.applied_rule_ids)
        self.assertIn(ATTACK_ACTION_EXECUTION_RULE_ID, result.applied_rule_ids)
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(result, applied_rule_ids=(RELOAD_RULE_ID,))
        foreign = create_initial_ranged_weapon_reload_state(
            "warbow:hero:2",
            RangedWeaponId.WARBOW,
        )
        with self.assertRaisesRegex(ValueError, "unrelated state"):
            replace(result, weapon_state=foreign)

        fields = RangedWeaponAttackExecutionRequest.__dataclass_fields__
        self.assertNotIn("ammunition", fields)
        self.assertNotIn("inventory", fields)


if __name__ == "__main__":
    unittest.main()
