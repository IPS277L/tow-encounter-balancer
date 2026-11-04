"""Pure PG93 weapon preparation boundaries; these are not native encounter traces."""
import unittest

from towr.domain.attack_models import DamageModifier, DamageProfile, ResilienceProfile
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_weapon_models import (
    FLAIL_STAGGERED_RULE_ID, GREATAXE_MELEE_RULE_ID, GREATHAMMER_MELEE_RULE_ID,
    HALBERD_ARMOUR_RULE_ID, GREATAXE_ARMOUR_RULE_ID, GLAIVE_DEFENCE_RULE_ID,
    GREATHAMMER_STAGGERED_RULE_ID,
    pc_weapon_requires_two_hands, pc_weapon_damage, pc_weapon_test_modifiers,
    pc_weapon_attack_modifiers, pc_weapon_damage_modifiers,
)
from towr.domain.test_models import DiceModifier, Skill


TWO_HANDED = (PcMeleeWeapon.PICKAXE, PcMeleeWeapon.FLAIL, PcMeleeWeapon.BILLHOOK,
    PcMeleeWeapon.HALBERD, PcMeleeWeapon.GLAIVE, PcMeleeWeapon.GREATAXE, PcMeleeWeapon.GREATHAMMER)
HEALTHY = ConditionState()
STAGGERED = ConditionState(frozenset({Condition.STAGGERED}))


class PcTwoHandedWeaponPreparationTests(unittest.TestCase):
    def test_exact_hand_requirements_leave_existing_weapons_one_handed(self):
        for weapon in PcMeleeWeapon:
            with self.subTest(weapon=weapon):
                self.assertIs(pc_weapon_requires_two_hands(weapon),weapon in TWO_HANDED)

    def test_all_seven_damage_profiles_at_low_and_ordinary_strength(self):
        offsets = ((PcMeleeWeapon.PICKAXE,1),(PcMeleeWeapon.FLAIL,3),
            (PcMeleeWeapon.BILLHOOK,2),(PcMeleeWeapon.HALBERD,2),(PcMeleeWeapon.GLAIVE,2),
            (PcMeleeWeapon.GREATAXE,3),(PcMeleeWeapon.GREATHAMMER,3))
        for weapon, offset in offsets:
            for strength in (1,3):
                with self.subTest(weapon=weapon,strength=strength):
                    self.assertEqual(pc_weapon_damage(weapon,strength),DamageProfile(strength+offset))

    def test_flail_actor_penalty_only_on_melee_while_staggered_including_drained(self):
        for conditions in (STAGGERED,ConditionState(frozenset({Condition.STAGGERED,Condition.DRAINED}))):
            self.assertEqual(pc_weapon_test_modifiers(PcMeleeWeapon.FLAIL,Skill.MELEE,conditions),
                (DiceModifier(FLAIL_STAGGERED_RULE_ID,-2),))
        self.assertEqual(pc_weapon_test_modifiers(PcMeleeWeapon.FLAIL,Skill.MELEE,HEALTHY),())
        for skill in (Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE):
            self.assertEqual(pc_weapon_test_modifiers(PcMeleeWeapon.FLAIL,skill,STAGGERED),())

    def test_greataxe_and_greathammer_unconditional_melee_penalties_are_distinct_receipts(self):
        for weapon, rule_id in ((PcMeleeWeapon.GREATAXE,GREATAXE_MELEE_RULE_ID),
                (PcMeleeWeapon.GREATHAMMER,GREATHAMMER_MELEE_RULE_ID)):
            for conditions in (HEALTHY,STAGGERED,ConditionState(frozenset({Condition.DRAINED}))):
                with self.subTest(weapon=weapon,conditions=conditions):
                    self.assertEqual(pc_weapon_test_modifiers(weapon,Skill.MELEE,conditions),
                        (DiceModifier(rule_id,-1),))
            for skill in (Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE):
                self.assertEqual(pc_weapon_test_modifiers(weapon,skill,STAGGERED),())

    def test_greathammer_enemy_bonus_does_not_erase_own_actor_penalty(self):
        # An own unopposed Help Test uses actor traits, without an enemy-target bonus.
        own = pc_weapon_test_modifiers(PcMeleeWeapon.GREATHAMMER,Skill.MELEE,HEALTHY)
        enemy = pc_weapon_attack_modifiers(PcMeleeWeapon.GREATHAMMER,STAGGERED)
        self.assertEqual(own,(DiceModifier(GREATHAMMER_MELEE_RULE_ID,-1),))
        self.assertEqual(enemy,(DiceModifier(GREATHAMMER_STAGGERED_RULE_ID,1),))
        self.assertEqual(tuple(mod.amount for mod in (*enemy,*own)),(1,-1))
        self.assertEqual(pc_weapon_attack_modifiers(PcMeleeWeapon.GREATHAMMER,HEALTHY),())

    def test_only_greathammer_new_weapon_has_unmounted_target_bonus(self):
        for weapon in TWO_HANDED:
            expected = (DiceModifier(GREATHAMMER_STAGGERED_RULE_ID,1),) if weapon is PcMeleeWeapon.GREATHAMMER else ()
            self.assertEqual(pc_weapon_attack_modifiers(weapon,STAGGERED),expected)
            self.assertEqual(pc_weapon_attack_modifiers(weapon,HEALTHY),())

    def test_halberd_and_greataxe_armour_damage_bind_the_actual_numeric_target(self):
        for weapon,rule_id in ((PcMeleeWeapon.HALBERD,HALBERD_ARMOUR_RULE_ID),
                (PcMeleeWeapon.GREATAXE,GREATAXE_ARMOUR_RULE_ID)):
            with self.subTest(weapon=weapon):
                self.assertEqual(pc_weapon_damage_modifiers(weapon,ResilienceProfile(3,1)),
                    (DamageModifier(rule_id,1),))
                self.assertEqual(pc_weapon_damage_modifiers(weapon,ResilienceProfile(3,5)),
                    (DamageModifier(rule_id,1),))
                self.assertEqual(pc_weapon_damage_modifiers(weapon,ResilienceProfile(9,0)),())
        for weapon in TWO_HANDED:
            if weapon not in (PcMeleeWeapon.HALBERD,PcMeleeWeapon.GREATAXE):
                self.assertEqual(pc_weapon_damage_modifiers(weapon,ResilienceProfile(3,1)),())

    def test_glaive_defence_trait_uses_actor_stagger_and_has_no_melee_bonus(self):
        self.assertEqual(pc_weapon_test_modifiers(PcMeleeWeapon.GLAIVE,Skill.DEFENCE,HEALTHY),
            (DiceModifier(GLAIVE_DEFENCE_RULE_ID,1),))
        self.assertEqual(pc_weapon_test_modifiers(PcMeleeWeapon.GLAIVE,Skill.DEFENCE,STAGGERED),())
        for skill in (Skill.MELEE,Skill.ATHLETICS,Skill.ENDURANCE):
            self.assertEqual(pc_weapon_test_modifiers(PcMeleeWeapon.GLAIVE,skill,HEALTHY),())

    def test_pickaxe_and_billhook_traits_have_no_action_in_current_family(self):
        for weapon in (PcMeleeWeapon.PICKAXE,PcMeleeWeapon.BILLHOOK):
            for skill in (Skill.MELEE,Skill.DEFENCE,Skill.ATHLETICS,Skill.ENDURANCE):
                for conditions in (HEALTHY,STAGGERED):
                    self.assertEqual(pc_weapon_test_modifiers(weapon,skill,conditions),())


if __name__ == '__main__':
    unittest.main()
