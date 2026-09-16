from __future__ import annotations

import unittest
from dataclasses import replace

from tests.helpers import SequenceRandom
from tests.unit.test_k1_aim_resolution import (
    attack_execution_request,
    completed_aim,
    reserve_action,
)
from tests.unit.test_k1_attack_action_execution import (
    execution_request,
    reserve_action as reserve_basic_action,
    started_turn,
)
from towr.domain.aim_models import AimFollowUpOutcome
from towr.domain.aim_ranged_weapon_attack_models import (
    AimRangedWeaponAttackExecutionRequest,
)
from towr.domain.attack_models import (
    DamageImpactSpec,
    DamageModifier,
    NearbyTargetsStaggerSpec,
)
from towr.domain.injury_models import WoundDiceModifier
from towr.domain.ranged_weapon_attack_preparation_models import (
    ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID,
    BLACKPOWDER_LORE_REQUIREMENT_RULE_ID,
    BLUNDERBUSS_NEARBY_STAGGER_RULE_ID,
    EXTREME_RANGE_AIM_RULE_ID,
    OUTSIDE_OPTIMUM_RANGE_RULE_ID,
    SHORT_RANGE_SHOOTING_BONUS_RULE_ID,
    WEAPON_REQUIRES_AIM_RULE_ID,
    WOUNDS_TABLE_BONUS_RULE_ID,
    RangedWeaponAttackPreparationRequest,
)
from towr.domain.ranged_weapon_profiles import (
    REPEATER_SHOOTING_BONUS_RULE_ID,
    RangedWeaponId,
    RangedWeaponRange,
    ranged_weapon_combat_profile,
)
from towr.domain.reload_models import (
    RangedWeaponReloadState,
    create_initial_ranged_weapon_reload_state,
)
from towr.domain.test_models import DiceModifier
from towr.domain.turn_models import (
    ActionSlotGrant,
    CombatActionDeclaration,
    CombatActionKind,
)
from towr.rules.aim_ranged_weapon_attack_resolution import (
    execute_aim_ranged_weapon_attack,
)
from towr.rules.ranged_weapon_attack_preparation import (
    prepare_ranged_weapon_attack,
)
from towr.rules.ranged_weapon_attack_resolution import (
    execute_ranged_weapon_attack,
)


def weapon_state(weapon_id: RangedWeaponId) -> RangedWeaponReloadState:
    return create_initial_ranged_weapon_reload_state(
        f"weapon:{weapon_id.value}:hero:1",
        weapon_id,
    )


def base_attack():
    state = reserve_basic_action(
        started_turn(),
        declaration=CombatActionDeclaration(CombatActionKind.ATTACK),
    )
    return execution_request(state, request_id="attack:prepared")


def aim_and_attack():
    aim = completed_aim(values=(1, 10, 10))
    attack_state = reserve_action(
        aim.round_state,
        CombatActionKind.ATTACK,
        grant=ActionSlotGrant.ABILITY,
    )
    attack = attack_execution_request(
        state=attack_state,
        slot_index=2,
    )
    return aim, attack


def preparation_request(
    weapon_id: RangedWeaponId,
    *,
    attack=None,
    target_range: RangedWeaponRange = RangedWeaponRange.MEDIUM,
    strength: int = 4,
    lore: bool = False,
    aim=None,
    range_approved: bool = False,
    next_cycle: str | None = None,
    uses_repeater_bonus: bool = False,
    has_close_enemy: bool = False,
) -> RangedWeaponAttackPreparationRequest:
    return RangedWeaponAttackPreparationRequest(
        id=f"prepare:{weapon_id.value}:1",
        weapon_state=weapon_state(weapon_id),
        attack=attack or base_attack(),
        target_range=target_range,
        attacker_strength=strength,
        has_blackpowder_lore=lore,
        has_enemy_in_close_range=has_close_enemy,
        next_reload_cycle_id=next_cycle,
        uses_optional_reload_bonus=uses_repeater_bonus,
        aim=aim,
        range_approved_by_gm=range_approved,
    )


class K1RangedWeaponAttackPreparationTests(unittest.TestCase):
    def test_strength_damage_and_outside_optimum_penalty_are_prepared(self) -> None:
        result = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.SLING,
                target_range=RangedWeaponRange.SHORT,
                strength=5,
            )
        )

        attack = result.execution.attack.kernel_request.attack
        impact = attack.impact_spec
        assert isinstance(impact, DamageImpactSpec)
        self.assertEqual(impact.damage.base, 5)
        self.assertEqual(
            attack.attacker_test.dice_modifiers,
            (DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),),
        )
        self.assertFalse(attack.is_close_range)
        self.assertIn(OUTSIDE_OPTIMUM_RANGE_RULE_ID, result.applied_rule_ids)

    def test_shortbow_short_range_bonus_and_existing_modifiers_stack(self) -> None:
        source = base_attack()
        external = DiceModifier("RULE-TALENT:test", 1)
        source = replace(
            source,
            kernel_request=replace(
                source.kernel_request,
                attack=replace(
                    source.kernel_request.attack,
                    attacker_test=replace(
                        source.kernel_request.attack.attacker_test,
                        dice_modifiers=(external,),
                    ),
                ),
            ),
        )

        result = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.SHORTBOW,
                attack=source,
                target_range=RangedWeaponRange.SHORT,
            )
        )

        modifiers = result.profile_attack.kernel_request.attack.attacker_test
        self.assertEqual(
            modifiers.dice_modifiers,
            (
                external,
                DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID, 1),
            ),
        )

    def test_crossbow_uses_armoured_bonus_and_ready_reload_transition(self) -> None:
        result = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.CROSSBOW,
                target_range=RangedWeaponRange.LONG,
                next_cycle="weapon:crossbow:hero:1:reload:1",
            )
        )

        impact = result.execution.attack.kernel_request.attack.impact_spec
        assert isinstance(impact, DamageImpactSpec)
        self.assertEqual(impact.damage.base, 4)
        self.assertEqual(
            impact.damage_modifiers,
            (DamageModifier(ARMOURED_TARGET_DAMAGE_BONUS_RULE_ID, 1),),
        )
        executed = execute_ranged_weapon_attack(
            result.execution,
            SequenceRandom([10, 10, 10]),
        )
        self.assertFalse(executed.weapon_state.loaded)

    def test_blackpowder_lore_close_range_and_armour_ignore_are_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "Blackpowder Lore"):
            preparation_request(
                RangedWeaponId.PISTOL,
                target_range=RangedWeaponRange.CLOSE,
                next_cycle="weapon:pistol:hero:1:reload:1",
            )

        result = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.PISTOL,
                target_range=RangedWeaponRange.CLOSE,
                lore=True,
                next_cycle="weapon:pistol:hero:1:reload:1",
            )
        )
        attack = result.execution.attack.kernel_request.attack
        impact = attack.impact_spec
        assert isinstance(impact, DamageImpactSpec)
        self.assertTrue(attack.is_close_range)
        self.assertTrue(impact.ignores_armour)
        self.assertIn(
            BLACKPOWDER_LORE_REQUIREMENT_RULE_ID,
            result.applied_rule_ids,
        )

        with self.assertRaisesRegex(ValueError, "cannot attack at Close"):
            preparation_request(
                RangedWeaponId.LONGBOW,
                target_range=RangedWeaponRange.CLOSE,
            )

    def test_blunderbuss_adds_named_effect_and_respects_hard_maximum(self) -> None:
        result = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.BLUNDERBUSS,
                target_range=RangedWeaponRange.SHORT,
                lore=True,
                next_cycle="weapon:blunderbuss:hero:1:reload:1",
            )
        )
        attack = result.execution.attack.kernel_request.attack
        self.assertIn(
            DiceModifier(SHORT_RANGE_SHOOTING_BONUS_RULE_ID, 2),
            attack.attacker_test.dice_modifiers,
        )
        self.assertIn(
            NearbyTargetsStaggerSpec(BLUNDERBUSS_NEARBY_STAGGER_RULE_ID),
            attack.secondary_effects,
        )

        with self.assertRaisesRegex(ValueError, "fixed Maximum Range"):
            preparation_request(
                RangedWeaponId.BLUNDERBUSS,
                target_range=RangedWeaponRange.LONG,
                lore=True,
                next_cycle="weapon:blunderbuss:hero:1:reload:1",
            )

    def test_long_rifle_requires_aim_and_prepares_wounds_table_bonus(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires Aim"):
            preparation_request(
                RangedWeaponId.HOCHLAND_LONG_RIFLE,
                lore=True,
                next_cycle="weapon:hochland_long_rifle:hero:1:reload:1",
            )

        aim, attack = aim_and_attack()
        result = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.HOCHLAND_LONG_RIFLE,
                attack=attack,
                target_range=RangedWeaponRange.EXTREME,
                lore=True,
                aim=aim,
                range_approved=True,
                next_cycle="weapon:hochland_long_rifle:hero:1:reload:1",
            )
        )

        self.assertIsNotNone(result.aim_follow_up)
        assert result.aim_follow_up is not None
        self.assertIs(
            result.aim_follow_up.outcome,
            AimFollowUpOutcome.APPLIED_TO_RANGED_ATTACK,
        )
        self.assertEqual(result.aim_follow_up.attack, result.execution.attack)
        self.assertEqual(
            result.execution.attack.kernel_request.wound_dice_modifiers,
            (WoundDiceModifier(WOUNDS_TABLE_BONUS_RULE_ID, 1),),
        )
        self.assertIn(WEAPON_REQUIRES_AIM_RULE_ID, result.applied_rule_ids)
        self.assertIn(EXTREME_RANGE_AIM_RULE_ID, result.applied_rule_ids)

        combined = AimRangedWeaponAttackExecutionRequest(
            id="consume:prepared-long-rifle",
            aim_follow_up=result.aim_follow_up,
            ranged_attack=result.execution,
        )
        executed = execute_aim_ranged_weapon_attack(
            combined,
            SequenceRandom([10, 10, 10, 10]),
        )
        self.assertFalse(executed.ranged_attack.weapon_state.loaded)

    def test_extreme_range_requires_matching_aim_and_gm_approval(self) -> None:
        with self.assertRaisesRegex(ValueError, "Aim and GM approval"):
            preparation_request(
                RangedWeaponId.LONGBOW,
                target_range=RangedWeaponRange.EXTREME,
            )

        aim, attack = aim_and_attack()
        with self.assertRaisesRegex(ValueError, "Aim and GM approval"):
            preparation_request(
                RangedWeaponId.LONGBOW,
                attack=attack,
                target_range=RangedWeaponRange.EXTREME,
                aim=aim,
            )
        with self.assertRaisesRegex(ValueError, "another actor or target"):
            preparation_request(
                RangedWeaponId.LONGBOW,
                attack=attack_execution_request(
                    state=attack.state,
                    slot_index=2,
                    target_id="ally",
                ),
                aim=aim,
            )

        with self.assertRaisesRegex(ValueError, "two-handed Optimum"):
            preparation_request(
                RangedWeaponId.SHORTBOW,
                target_range=RangedWeaponRange.LONG,
            )
        long_shot = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.SHORTBOW,
                target_range=RangedWeaponRange.LONG,
                range_approved=True,
            )
        )
        modifiers = (
            long_shot.execution.attack.kernel_request.attack.attacker_test
            .dice_modifiers
        )
        self.assertIn(
            DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),
            modifiers,
        )

    def test_one_handed_maximum_cannot_be_bypassed_with_aim_and_gm_approval(self) -> None:
        aim, attack = aim_and_attack()
        for weapon in (RangedWeaponId.PISTOL, RangedWeaponId.REPEATER_PISTOL):
            with self.subTest(weapon=weapon):
                with self.assertRaisesRegex(ValueError, "fixed Maximum Range"):
                    preparation_request(
                        weapon, attack=attack, target_range=RangedWeaponRange.EXTREME,
                        lore=True, aim=aim, range_approved=True,
                    )
        result = prepare_ranged_weapon_attack(preparation_request(
            RangedWeaponId.PISTOL, target_range=RangedWeaponRange.LONG,
            lore=True, next_cycle="weapon:pistol:hero:1:reload:1",
        ))
        self.assertIn(OUTSIDE_OPTIMUM_RANGE_RULE_ID, result.applied_rule_ids)

    def test_repeater_and_forged_profile_effects_are_rejected(self) -> None:
        source = base_attack()
        source = replace(
            source,
            kernel_request=replace(
                source.kernel_request,
                attack=replace(
                    source.kernel_request.attack,
                    attacker_test=replace(
                        source.kernel_request.attack.attacker_test,
                        dice_modifiers=(
                            DiceModifier(REPEATER_SHOOTING_BONUS_RULE_ID, 2),
                        ),
                    ),
                ),
            ),
        )
        result = prepare_ranged_weapon_attack(
            preparation_request(
                RangedWeaponId.REPEATER_PISTOL,
                attack=source,
                target_range=RangedWeaponRange.SHORT,
                lore=True,
                next_cycle="weapon:repeater_pistol:hero:1:reload:1",
                uses_repeater_bonus=True,
            )
        )
        self.assertTrue(result.execution.uses_optional_reload_bonus)

        forged_source = base_attack()
        forged = replace(
            forged_source,
            kernel_request=replace(
                forged_source.kernel_request,
                attack=replace(
                    forged_source.kernel_request.attack,
                    attacker_test=replace(
                        forged_source.kernel_request.attack.attacker_test,
                        dice_modifiers=(
                            DiceModifier(OUTSIDE_OPTIMUM_RANGE_RULE_ID, -1),
                        ),
                    ),
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "already contains"):
            preparation_request(RangedWeaponId.SLING, attack=forged)

    def test_result_rejects_foreign_profile_execution_and_trace(self) -> None:
        result = prepare_ranged_weapon_attack(
            preparation_request(RangedWeaponId.LONGBOW)
        )

        with self.assertRaisesRegex(ValueError, "another weapon profile"):
            replace(
                result,
                profile=ranged_weapon_combat_profile(RangedWeaponId.WARBOW),
            )
        with self.assertRaisesRegex(ValueError, "execution is inconsistent"):
            replace(
                result,
                execution=replace(
                    result.execution,
                    attack=result.source_request.attack,
                ),
            )
        with self.assertRaisesRegex(ValueError, "trace is inconsistent"):
            replace(result, applied_rule_ids=(result.rule_id,))

        fields = RangedWeaponAttackPreparationRequest.__dataclass_fields__
        self.assertNotIn("ammunition", fields)
        self.assertNotIn("inventory", fields)


if __name__ == "__main__":
    unittest.main()
