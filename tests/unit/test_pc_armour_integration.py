"""Item facts reach real encounter Tests, resilience and independent burdens."""
from tests.support.generated_weapon_sources import initial_generated_weapons
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.armour_models import ArmourLoadout,BodyArmour,HelmetKind,body_resilience_bonus,helmet_resilience_bonus
from towr.domain.condition_models import Condition
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_melee_result_models import initial_pc_melee_state,_pc_test
from towr.domain.pc_potion_models import pc_effective_definition
from towr.domain.pc_shield_models import pc_shield_resilience
from towr.domain.pc_generated_equipment import npc_protection_test
from towr.domain.pc_armour_models import actor_armour_quality_modifiers,actor_armour_test_modifiers
from towr.domain.test_models import Skill
from towr.rules.test_resolution import resolve_test


def protected_source(armour,*,strength=3):
    source=make_pc_melee_scenario()
    member=source.party[0]
    pc=replace(member.pc,strength=strength,
        armour_bonus=body_resilience_bonus(armour)+helmet_resilience_bonus(armour))
    member=replace(member,pc=pc,armour=armour,armour_worn=bool(armour.body or armour.helmet),
        agilulf_code_confirmed=True if BodyArmour.AGILULF in armour.body else None)
    return replace(source,party=(member,))


class PcArmourIntegrationTests(unittest.TestCase):
    def test_heavy_armour_changes_actual_athletics_dice_not_cap(self):
        source=protected_source(ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY))
        state=initial_pc_melee_state(source)
        request=_pc_test(state,'pc','athletics',Skill.ATHLETICS)
        rng=ScriptedD10([1,1])
        result=resolve_test(request,rng)
        rng.assert_exhausted()
        self.assertEqual(result.trace.initial_values,(1,1))
        self.assertEqual(request.profile.maximum_dice,6)
        self.assertEqual(pc_shield_resilience(state,'pc').total,5)
        self.assertFalse(state.party[0].injury.conditions.has(Condition.BURDENED))

    def test_low_strength_burden_is_present_before_first_turn(self):
        for armour,strength in ((BodyArmour.HEAVY,2),(BodyArmour.FULL_PLATE,3)):
            with self.subTest(armour=armour):
                state=initial_pc_melee_state(protected_source(
                    ArmourLoadout((armour,),armour),strength=strength))
                self.assertTrue(state.party[0].injury.conditions.has(Condition.BURDENED))

    def test_agilulf_fixes_real_profiles_without_rewriting_base_facts(self):
        source=protected_source(ArmourLoadout((BodyArmour.AGILULF,),BodyArmour.AGILULF))
        state=initial_pc_melee_state(source)
        pc=pc_effective_definition(state,'pc')
        self.assertEqual((pc.weapon_skill,pc.melee,pc.defence),(5,5,5))
        self.assertEqual(source.party[0].pc.weapon_skill,3)
        self.assertEqual(_pc_test(state,'pc','defence',Skill.DEFENCE).profile.characteristic,5)

    def test_helm_bonus_is_additive_to_real_full_plate(self):
        state=initial_pc_melee_state(protected_source(ArmourLoadout(
            (BodyArmour.FULL_PLATE,),BodyArmour.FULL_PLATE,HelmetKind.HUNT),strength=4))
        self.assertEqual(pc_shield_resilience(state,'pc').total,7)

    def test_native_helmet_source_is_armoured_without_the_optional_old_worn_fact(self):
        source=make_pc_melee_scenario()
        member=replace(source.party[0],armour=ArmourLoadout(helmet=HelmetKind.HELMET))
        self.assertIsNone(member.armour_worn)
        state=initial_pc_melee_state(replace(source,party=(member,)))
        resilience=pc_shield_resilience(state,'pc')
        self.assertTrue(resilience.is_armoured)
        self.assertEqual(resilience.bonus,0)

    def test_native_generic_npc_cannot_claim_meteoric_protection_without_the_item(self):
        source=make_pc_melee_scenario()
        enemy=source.enemies[0]
        resilience=replace(enemy.definition.resilience,mundane_armour_ward=True)
        forged=replace(enemy,definition=replace(enemy.definition,resilience=resilience),
            state=replace(enemy.state,current_resilience=resilience))
        with self.assertRaisesRegex(ValueError,'complete generated armour item source'):
            replace(source,enemies=(forged,))
        generated=GeneratedNpc(3,3,3,3,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),
            ArmourLoadout((BodyArmour.METEORIC_IRON,),BodyArmour.METEORIC_IRON),
            defence=4).participant('minion1')
        admitted=initial_pc_melee_state(replace(source,enemies=(generated,)))
        self.assertTrue(admitted.enemy('minion1').state.current_resilience.mundane_armour_ward)

    def test_generated_armour_changes_actual_defence_choice(self):
        source=make_pc_melee_scenario()
        enemy=GeneratedNpc(3,2,3,3,4,5,initial_generated_weapons(GeneratedWeapon.STAFF),
            ArmourLoadout((BodyArmour.HEAVY,),BodyArmour.HEAVY),defence=4).participant('minion1')
        state=initial_pc_melee_state(replace(source,enemies=(enemy,)))
        self.assertTrue(state.enemy('minion1').state.injury.conditions.has(Condition.BURDENED))
        option,request=npc_protection_test(state,'minion1','pc','actual-protection')
        # Athletics would win at 3d/5; armour makes it 2d/5 vs Defence3d/4.
        self.assertIs(option.skill,Skill.DEFENCE)
        self.assertFalse(any(m.amount<0 for m in request.dice_modifiers))

    def test_drained_suppresses_item_glorious_and_environment_bonus(self):
        source=protected_source(ArmourLoadout((BodyArmour.ITHILMAR,),BodyArmour.ITHILMAR,HelmetKind.HUNT))
        state=initial_pc_melee_state(source)
        self.assertTrue(actor_armour_quality_modifiers(state,'pc',charge_attack=True))
        self.assertEqual(sum(mod.amount for mod in actor_armour_test_modifiers(
            state,'pc',Skill.ENDURANCE,environmental=True)),1)
        member=state.party[0]
        state=replace(state,party=(replace(member,injury=replace(member.injury,
            conditions=member.injury.conditions.with_condition(Condition.DRAINED))),))
        self.assertEqual(actor_armour_quality_modifiers(state,'pc',charge_attack=True),())
        self.assertEqual(actor_armour_test_modifiers(state,'pc',Skill.ENDURANCE,environmental=True),())


if __name__=='__main__':
    unittest.main()
