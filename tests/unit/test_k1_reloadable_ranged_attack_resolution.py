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
from tests.unit.test_k1_reload_resolution import active_round, reload_request
from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.exacting_test_models import ExactingTestProgress
from towr.domain.ranged_weapon_attack_models import (
    ReloadableRangedAttackExecutionRequest,
)
from towr.domain.reload_models import RELOAD_RULE_ID, ReloadableWeaponState
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.rules.attack_action_execution import ATTACK_ACTION_EXECUTION_RULE_ID
from towr.rules.ranged_weapon_attack_resolution import (
    execute_reloadable_ranged_attack,
)
from towr.rules.reload_resolution import execute_reload_action


def loaded_weapon(
    *,
    required_successes: int = 2,
) -> ReloadableWeaponState:
    return ReloadableWeaponState(
        weapon_instance_id="crossbow:hero:1",
        weapon_id=RangedWeaponId.CROSSBOW,
        reload_cycle_id=None,
        required_successes=required_successes,
        loaded=True,
        exacting=None,
        reload_cycle_ids=(),
    )


def attack_request(
    weapon: ReloadableWeaponState,
    *,
    request_id: str = "ranged-shot:1",
    attack_id: str = "execute:ranged-shot:1",
    kernel_id: str = "kernel:ranged-shot:1",
    next_cycle_id: str | None = "crossbow:hero:1:reload:1",
    skill: Skill = Skill.SHOOTING,
    source: AttackActionExecutionRequest | None = None,
    **changes,
) -> ReloadableRangedAttackExecutionRequest:
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
        "attack_skill": skill,
        "attack": source,
        "weapon_state": weapon,
        "next_reload_cycle_id": next_cycle_id,
    }
    values.update(changes)
    return ReloadableRangedAttackExecutionRequest(**values)


class K1ReloadableRangedAttackResolutionTests(unittest.TestCase):
    def test_hit_and_miss_both_fire_weapon_and_open_empty_reload_cycle(self) -> None:
        for number, rolls in enumerate(((1, 10, 10), (10, 10, 10)), 1):
            with self.subTest(rolls=rolls):
                weapon = loaded_weapon()
                request = attack_request(
                    weapon,
                    request_id=f"ranged-shot:{number}",
                    attack_id=f"execute:ranged-shot:{number}",
                    kernel_id=f"kernel:ranged-shot:{number}",
                    next_cycle_id=f"crossbow:hero:1:reload:{number}",
                )
                result = execute_reloadable_ranged_attack(
                    request,
                    SequenceRandom(list(rolls)),
                )

                self.assertIs(result.previous_weapon_state, weapon)
                self.assertFalse(result.weapon_state.loaded)
                self.assertEqual(
                    result.weapon_state.reload_cycle_id,
                    request.next_reload_cycle_id,
                )
                self.assertEqual(
                    result.weapon_state.reload_cycle_ids,
                    (request.next_reload_cycle_id,),
                )
                self.assertEqual(
                    result.weapon_state.exacting,
                    ExactingTestProgress(
                        f"{request.next_reload_cycle_id}:exacting",
                        2,
                    ),
                )
                self.assertTrue(result.attack.slot.executed)
                self.assertEqual(
                    result.attack.slot.execution.executor_rule_id,
                    ATTACK_ACTION_EXECUTION_RULE_ID,
                )

    def test_completed_reload_can_fire_and_preserves_cycle_history(self) -> None:
        spent = execute_reloadable_ranged_attack(
            attack_request(loaded_weapon()),
            SequenceRandom([10, 10, 10]),
        ).weapon_state
        reloaded = execute_reload_action(
            reload_request(
                spent,
                action_number=2,
                round_state=active_round(spent, round_number=2),
                rolls=2,
            ),
            SequenceRandom([1, 2]),
        ).state

        result = execute_reloadable_ranged_attack(
            attack_request(
                reloaded,
                request_id="ranged-shot:2",
                attack_id="execute:ranged-shot:2",
                kernel_id="kernel:ranged-shot:2",
                next_cycle_id="crossbow:hero:1:reload:2",
            ),
            SequenceRandom([10, 10, 10]),
        )

        self.assertEqual(
            result.weapon_state.reload_cycle_ids,
            (
                "crossbow:hero:1:reload:1",
                "crossbow:hero:1:reload:2",
            ),
        )
        self.assertFalse(result.weapon_state.loaded)
        self.assertEqual(result.weapon_state.exacting.accumulated_successes, 0)

    def test_unloaded_weapon_is_rejected_before_attack_or_rng(self) -> None:
        spent = ReloadableWeaponState(
            weapon_instance_id="crossbow:hero:1",
            weapon_id=RangedWeaponId.CROSSBOW,
            reload_cycle_id="crossbow:hero:1:reload:1",
            required_successes=2,
            loaded=False,
            exacting=ExactingTestProgress(
                "crossbow:hero:1:reload:1:exacting",
                2,
            ),
            reload_cycle_ids=("crossbow:hero:1:reload:1",),
        )

        with self.assertRaisesRegex(ValueError, "must be loaded"):
            attack_request(spent)

    def test_only_shooting_can_use_reloadable_ranged_weapon(self) -> None:
        for skill in (Skill.MELEE, Skill.THROWING, Skill.BRAWN):
            with self.subTest(skill=skill):
                with self.assertRaisesRegex(ValueError, "with Shooting"):
                    attack_request(loaded_weapon(), skill=skill)

    def test_reload_cycle_ids_cannot_be_reused(self) -> None:
        spent = execute_reloadable_ranged_attack(
            attack_request(loaded_weapon()),
            SequenceRandom([10, 10, 10]),
        ).weapon_state
        reloaded = execute_reload_action(
            reload_request(spent, action_number=2, rolls=2),
            SequenceRandom([1, 2]),
        ).state

        with self.assertRaisesRegex(ValueError, "already used"):
            attack_request(
                reloaded,
                request_id="ranged-shot:2",
                attack_id="execute:ranged-shot:2",
                kernel_id="kernel:ranged-shot:2",
                next_cycle_id="crossbow:hero:1:reload:1",
            )

    def test_failed_attack_execution_does_not_change_weapon_state(self) -> None:
        weapon = loaded_weapon()
        round_state = reserve_action(
            started_turn(),
            CombatActionDeclaration(CombatActionKind.ATTACK),
        )
        invalid_source = execution_request(
            round_state,
            actor_id="enemy",
            request_id="execute:invalid-ranged-shot",
        )
        request = attack_request(
            weapon,
            source=invalid_source,
            attack_id="ignored",
        )

        with self.assertRaisesRegex(ValueError, "does not own"):
            execute_reloadable_ranged_attack(request, SequenceRandom([]))
        self.assertTrue(weapon.loaded)
        self.assertIsNone(weapon.reload_cycle_id)

    def test_result_is_closed_and_traces_attack_and_reload_rule(self) -> None:
        result = execute_reloadable_ranged_attack(
            attack_request(loaded_weapon()),
            SequenceRandom([10, 10, 10]),
        )

        self.assertIn(RELOAD_RULE_ID, result.applied_rule_ids)
        self.assertIn(ATTACK_ACTION_EXECUTION_RULE_ID, result.applied_rule_ids)
        with self.assertRaisesRegex(ValueError, "unrelated weapon state"):
            replace(result, weapon_state=result.previous_weapon_state)
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(result, applied_rule_ids=(RELOAD_RULE_ID,))
        foreign = execute_reloadable_ranged_attack(
            attack_request(
                loaded_weapon(),
                request_id="ranged-shot:foreign",
                attack_id="execute:ranged-shot:foreign",
                kernel_id="kernel:ranged-shot:foreign",
                next_cycle_id="crossbow:hero:1:reload:foreign",
            ),
            SequenceRandom([10, 10, 10]),
        ).attack
        with self.assertRaisesRegex(ValueError, "another Attack"):
            replace(result, attack=foreign)

    def test_contract_does_not_add_ammunition_or_full_inventory(self) -> None:
        fields = ReloadableRangedAttackExecutionRequest.__dataclass_fields__
        self.assertNotIn("ammunition", fields)
        self.assertNotIn("inventory", fields)


if __name__ == "__main__":
    unittest.main()
