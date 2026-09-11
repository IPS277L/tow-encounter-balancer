from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_hidden_attack_resolution import (
    attack_execution_request,
    completed_move_quietly,
    execution_request as hidden_execution_request,
)
from tests.unit.test_k1_ranged_weapon_attack_resolution import ranged_request
from towr.domain.hidden_attack_models import HIDDEN_ATTACK_OPPORTUNITY_RULE_ID
from towr.domain.hidden_ranged_weapon_attack_models import (
    MoveQuietlyHiddenRangedAttackExecutionRequest,
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
from towr.rules.attack_action_execution import ATTACK_ACTION_EXECUTION_RULE_ID
from towr.rules.hidden_ranged_weapon_attack_resolution import (
    execute_move_quietly_hidden_ranged_attack,
)


def combined_request(
    weapon: FreeReloadWeaponState | ReloadableWeaponState,
    *,
    hidden=None,
    ranged: RangedWeaponAttackExecutionRequest | None = None,
    next_cycle_id: str | None = None,
    uses_optional_reload_bonus: bool = False,
) -> MoveQuietlyHiddenRangedAttackExecutionRequest:
    hidden = hidden or hidden_execution_request()
    ranged = ranged or ranged_request(
        weapon,
        request_id="profiled:hidden-ranged-attack",
        source=hidden.attack,
        next_cycle_id=next_cycle_id,
        uses_optional_reload_bonus=uses_optional_reload_bonus,
    )
    return MoveQuietlyHiddenRangedAttackExecutionRequest(
        id="consume:hidden-ranged-attack",
        hidden_attack=hidden,
        ranged_attack=ranged,
    )


def repeater_bonus_hidden_request(
) -> MoveQuietlyHiddenRangedAttackExecutionRequest:
    move_quietly = completed_move_quietly()
    weapon = create_initial_ranged_weapon_reload_state(
        "repeater-handgun:hero:1",
        RangedWeaponId.REPEATER_HANDGUN,
    )
    assert isinstance(weapon, ReloadableWeaponState)
    attack = attack_execution_request(move_quietly)
    modifier = ranged_weapon_reload_profile(
        weapon.weapon_id
    ).optional_bonus_modifier()
    attacker_test = replace(
        attack.kernel_request.attack.attacker_test,
        dice_modifiers=(modifier,),
    )
    attack = replace(
        attack,
        kernel_request=replace(
            attack.kernel_request,
            attack=replace(
                attack.kernel_request.attack,
                attacker_test=attacker_test,
            ),
        ),
    )
    hidden = hidden_execution_request(
        move_quietly=move_quietly,
        attack=attack,
    )
    return combined_request(
        weapon,
        hidden=hidden,
        next_cycle_id="repeater-handgun:hero:1:reload:1",
        uses_optional_reload_bonus=True,
    )


class K1HiddenRangedWeaponAttackResolutionTests(unittest.TestCase):
    def test_free_weapon_consumes_opportunity_with_one_attack(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "longbow:hero:1",
            RangedWeaponId.LONGBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        hidden = hidden_execution_request(consumed=("hidden:older",))
        request = combined_request(weapon, hidden=hidden)

        result = execute_move_quietly_hidden_ranged_attack(
            request,
            SequenceRandom([1, 10]),
        )

        self.assertIs(result.ranged_attack.weapon_state, weapon)
        self.assertIsNone(
            request.ranged_attack.attack.kernel_request.attack.defender_test
        )
        self.assertTrue(result.ranged_attack.attack.slot.executed)
        self.assertEqual(
            result.ranged_attack.attack.slot.execution.executor_rule_id,
            ATTACK_ACTION_EXECUTION_RULE_ID,
        )
        self.assertEqual(
            result.consumed_opportunity_ids,
            ("hidden:older", request.hidden_attack.opportunity.id),
        )

    def test_crossbow_opens_its_profile_reload_cycle(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "crossbow:hero:1",
            RangedWeaponId.CROSSBOW,
        )
        assert isinstance(weapon, ReloadableWeaponState)

        result = execute_move_quietly_hidden_ranged_attack(
            combined_request(
                weapon,
                next_cycle_id="crossbow:hero:1:reload:1",
            ),
            SequenceRandom([1, 10]),
        )

        self.assertFalse(result.ranged_attack.weapon_state.loaded)
        self.assertEqual(result.ranged_attack.weapon_state.required_successes, 2)
        self.assertEqual(
            result.ranged_attack.weapon_state.reload_cycle_id,
            "crossbow:hero:1:reload:1",
        )

    def test_ordinary_repeater_shot_stays_loaded(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "repeater-pistol:hero:1",
            RangedWeaponId.REPEATER_PISTOL,
        )
        assert isinstance(weapon, ReloadableWeaponState)

        result = execute_move_quietly_hidden_ranged_attack(
            combined_request(weapon),
            SequenceRandom([1, 10]),
        )

        self.assertIs(result.ranged_attack.weapon_state, weapon)
        self.assertTrue(result.ranged_attack.weapon_state.loaded)
        self.assertEqual(result.ranged_attack.weapon_state.reload_cycle_ids, ())

    def test_bonus_repeater_shot_opens_exact_profile_cycle(self) -> None:
        request = repeater_bonus_hidden_request()

        result = execute_move_quietly_hidden_ranged_attack(
            request,
            SequenceRandom([1, 10, 10, 10, 10]),
        )

        self.assertFalse(result.ranged_attack.weapon_state.loaded)
        self.assertEqual(result.ranged_attack.weapon_state.required_successes, 5)
        self.assertEqual(
            result.ranged_attack.weapon_state.reload_cycle_id,
            "repeater-handgun:hero:1:reload:1",
        )

    def test_requests_must_share_one_exact_attack(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "shortbow:hero:1",
            RangedWeaponId.SHORTBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        hidden = hidden_execution_request()
        foreign_attack = replace(hidden.attack, id="execute:foreign-hidden")
        ranged = ranged_request(
            weapon,
            request_id="profiled:foreign-hidden",
            source=foreign_attack,
        )

        with self.assertRaisesRegex(ValueError, "share one Attack"):
            combined_request(weapon, hidden=hidden, ranged=ranged)
        with self.assertRaisesRegex(ValueError, "IDs must be distinct"):
            replace(
                combined_request(weapon, hidden=hidden),
                id=hidden.id,
            )

    def test_failure_does_not_consume_and_result_is_closed(self) -> None:
        weapon = create_initial_ranged_weapon_reload_state(
            "warbow:hero:1",
            RangedWeaponId.WARBOW,
        )
        assert isinstance(weapon, FreeReloadWeaponState)
        request = combined_request(weapon)

        with self.assertRaises(RuntimeError):
            execute_move_quietly_hidden_ranged_attack(
                request,
                SequenceRandom([]),
            )
        self.assertEqual(request.hidden_attack.consumed_opportunity_ids, ())

        result = execute_move_quietly_hidden_ranged_attack(
            request,
            SequenceRandom([1, 10]),
        )
        self.assertIn(
            HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
            result.applied_rule_ids,
        )
        with self.assertRaisesRegex(ValueError, "append"):
            replace(result, consumed_opportunity_ids=())
        with self.assertRaisesRegex(ValueError, "trace is incomplete"):
            replace(
                result,
                applied_rule_ids=(HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,),
            )


if __name__ == "__main__":
    unittest.main()
