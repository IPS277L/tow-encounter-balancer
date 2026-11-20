"""Equipment lifecycle from typed applications and one actual Shield journal.

Prepared composition tests author authorised application sources explicitly;
they do not claim complete Attack execution. The native class obtains its
applications, physical Shield receipts and order from the real runner.
"""
from dataclasses import replace
import unittest

from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_weapon_sources import initial_weapon_items
from tests.support.talent_sources import paid_talent
from tests.unit.test_pc_npc_shield import view
from tests.unit.test_talent_armour_bane_sources import item,use
from towr.domain.armour_models import (
    ArmourLoadout,BodyArmour,HelmetKind,ShieldKind,armour_casting_grim,armour_allows_near_miss,
    protects_against_mundane_armour_effects,
)
from towr.domain.attack_models import ResilienceProfile
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedRangedFacts,GeneratedWeapon
from towr.domain.pc_armour_bane_models import (
    armour_bane_applications,armour_bane_resilience_from_sources,
)
from towr.domain.pc_melee_models import PcFatePolicy,PcMeleeWeapon,PcRepeaterBonusPolicy
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_mount_models import CombatMount
from towr.domain.pc_npc_ranged_source_models import pc_npc_ranged_policy_for_generated
from towr.domain.pc_npc_resilience_models import npc_equipment_resilience
from towr.domain.pc_npc_shield_models import (
    PcNpcShieldDropProof,PcNpcShieldRecoverProof,_with_shield,npc_shield_drop_updates,
)
from towr.domain.talent_armour_bane_models import ArmourBaneApplication,armour_bane_eligible_sources
from towr.domain.talent_catalog import TalentId
from towr.domain.weapon_catalog import WeaponKind
from towr.engine.pc_melee_runner import run_pc_melee_scenario


def application(before,identifier='prepared:hit:1',*,target='enemy'):
    actual=use(item('qualifying-axe',WeaponKind.AXE))
    return ArmourBaneApplication(identifier,'actor',target,paid_talent(TalentId.ARMOUR_BANE),
        actual,armour_bane_eligible_sources(actual,before),before)


def applications(before,count):
    result=[]
    for index in range(count):
        effect=application(before,'prepared:hit:'+str(index+1))
        result.append(effect)
        before=effect.after
    return tuple(result)


class ArmourBaneEquipmentCompositionTests(unittest.TestCase):
    def test_actual_reductions_are_cumulative_and_clamp_at_present_toughness(self):
        before=ResilienceProfile(4,3)
        sources=applications(before,2)
        self.assertEqual(tuple(source.reduction for source in sources),(1,1))
        self.assertEqual(armour_bane_resilience_from_sources(before,sources).bonus,1)
        for present in (ResilienceProfile(4,1),ResilienceProfile(4,0)):
            actual=armour_bane_resilience_from_sources(present,sources)
            self.assertEqual(actual.total,4)
            self.assertEqual(actual.bonus,0)
            self.assertFalse(actual.is_armoured)

    def test_drop_recovery_and_dismount_rebuild_current_gear_without_negative_bonus_or_reset(self):
        armour=ArmourLoadout((BodyArmour.LIGHT,),BodyArmour.LIGHT,None,ShieldKind.SHIELD,True)
        state=view(armour=armour,mount=CombatMount.HORSE)
        enemy=state.enemy('enemy')
        mount=state.mounts[0]
        base=npc_equipment_resilience(enemy.definition,'enemy',shield_held=True,mount_source=mount)
        self.assertEqual(base.bonus,4)
        sources=applications(base,3)
        damaged=replace(enemy,state=replace(enemy.state,
            current_resilience=armour_bane_resilience_from_sources(base,sources)))
        self.assertEqual(damaged.state.current_resilience.bonus,1)
        dropped=_with_shield(damaged,False,mount_source=mount,armour_bane_sources=sources)
        self.assertEqual(dropped.state.current_resilience.bonus,0)
        recovered=_with_shield(dropped,True,mount_source=mount,armour_bane_sources=sources)
        self.assertEqual(recovered.state.current_resilience.bonus,1)
        self.assertEqual(recovered.definition,enemy.definition)
        unmounted=replace(mount,mounted=False)
        bare_base=npc_equipment_resilience(enemy.definition,'enemy',shield_held=True,mount_source=unmounted)
        self.assertEqual(bare_base.bonus,2)
        after_dismount=replace(recovered,state=replace(recovered.state,
            current_resilience=armour_bane_resilience_from_sources(bare_base,sources)))
        self.assertEqual(after_dismount.state.current_resilience.bonus,0)
        dropped_again=_with_shield(after_dismount,False,mount_source=unmounted,armour_bane_sources=sources)
        self.assertEqual(dropped_again.state.current_resilience.bonus,0)
        self.assertEqual(dropped_again.state.current_resilience.toughness,4)

    def test_zero_point_helmet_application_removes_armoured_without_creating_future_debt(self):
        state=view(armour=ArmourLoadout(helmet=HelmetKind.HELMET),shield=None)
        enemy=state.enemy('enemy')
        base=npc_equipment_resilience(enemy.definition,'enemy',shield_held=False,mount_source=None)
        self.assertTrue(base.armoured)
        effect=application(base)
        self.assertEqual(effect.reduction,0)
        lowered=armour_bane_resilience_from_sources(base,(effect,))
        self.assertFalse(lowered.is_armoured)
        self.assertEqual(lowered.total,lowered.toughness)
        self.assertIs(enemy.definition.generated_components.armour.helmet,HelmetKind.HELMET)
        self.assertTrue(armour_casting_grim(enemy.definition.generated_components.armour,working_shield=False))
        later_shield=ResilienceProfile(4,1)
        self.assertEqual(armour_bane_resilience_from_sources(later_shield,(effect,)).bonus,1)

    def test_past_ordinary_gear_loss_cannot_remove_a_current_meteoric_ward_or_its_items(self):
        # These receipts precede the supplied current Ward base. No new
        # application through a cancelled mundane Trait is asserted here.
        past=applications(ResilienceProfile(4,2),2)
        armour=ArmourLoadout((BodyArmour.METEORIC_IRON,),BodyArmour.METEORIC_IRON,
            HelmetKind.HUNT,ShieldKind.BRIARROOT)
        state=view(armour=armour)
        enemy=state.enemy('enemy')
        base=npc_equipment_resilience(enemy.definition,'enemy',shield_held=True,mount_source=None)
        actual=armour_bane_resilience_from_sources(base,past)
        self.assertEqual(actual.bonus,base.bonus-2)
        self.assertTrue(actual.mundane_armour_ward)
        self.assertTrue(protects_against_mundane_armour_effects(armour))
        self.assertIs(enemy.definition.generated_components.armour.helmet,HelmetKind.HUNT)
        self.assertIs(enemy.definition.generated_components.armour.shield,ShieldKind.BRIARROOT)
        self.assertFalse(armour_allows_near_miss(armour))

    def test_foreign_duplicate_and_erased_sources_cannot_reclassify_the_prepared_shield_base(self):
        state=view()
        enemy=state.enemy('enemy')
        sources=applications(enemy.state.current_resilience,1)
        damaged=replace(enemy,state=replace(enemy.state,
            current_resilience=armour_bane_resilience_from_sources(enemy.state.current_resilience,sources)))
        for wrong in ((),sources*2,(replace(sources[0],target_id='foreign'),),list(sources)):
            with self.subTest(wrong=wrong),self.assertRaises((TypeError,ValueError)):
                _with_shield(damaged,False,mount_source=None,armour_bane_sources=wrong)


def shield_battle():
    source=make_pc_pistol_scenario(max_rounds=4,ballistic_skill=3)
    member=source.party[0]
    weapon=PcMeleeWeapon.REPEATER_PISTOL
    member=replace(member,pc=replace(member.pc,weapon=weapon,toughness=20,
        ranged=replace(member.pc.ranged,repeater_bonus_policy=PcRepeaterBonusPolicy.NEVER)),
        combat_equipment=initial_weapon_items(weapon,member.initial_weapon_hand,initially_loaded=True),
        talents=(paid_talent(TalentId.ARMOUR_BANE),),fate_policy=PcFatePolicy.DECLINE_OPTIONAL_FATE,
        near_miss_policy=None,glorious_policy=None)
    npc=GeneratedNpc(3,3,20,3,4,4,
        initial_generated_weapons(GeneratedWeapon.PISTOL,initially_loaded=False),
        ArmourLoadout((BodyArmour.LIGHT,),BodyArmour.LIGHT,None,ShieldKind.SHIELD),
        defence=4,ranged=GeneratedRangedFacts(3, 4,  True, True, True), initiative=3, dexterity=5)
    return replace(source,party=(member,),enemies=(npc.participant('minion1'),),
        npc_ranged_policies=(pc_npc_ranged_policy_for_generated(npc,'minion1'),),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


class ArmourBaneEquipmentNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=shield_battle()
        # Two nonconsecutive hits, with genuine Reload and Shield Recover
        # clearing Staggered between them; the last turn supplies drop2.
        values=([1]*3+[10]*3+[1]*3 + [10]*6
            + [1]*3+[10]*9 + [10]*6+[1]*3)
        cls.rng=ScriptedD10(values)
        cls.result=run_pc_melee_scenario(cls.source,cls.rng)
        cls.rng.assert_exhausted()

    def test_actual_hit_loss_survives_real_drop_paid_recovery_and_second_drop_at_floor(self):
        result=self.result
        self.assertIsNone(result.unsupported)
        hits=tuple(step.proof for step in result.steps
            if type(step.proof) is PcAttackProof and step.proof.armour_bane is not None)
        self.assertEqual(len(hits),2)
        sources=armour_bane_applications(result.state,'minion1')
        self.assertEqual(sources,tuple(proof.armour_bane for proof in hits))
        self.assertEqual(tuple(effect.reduction for effect in sources),(1,1))
        drops=tuple(step for step in result.steps if type(step.proof) is PcNpcShieldDropProof)
        self.assertEqual(len(drops),2)
        pickup=next(step for step in result.steps if type(step.proof) is PcNpcShieldRecoverProof)
        self.assertEqual(drops[0].proof.armour_bane_sources,sources[:1])
        self.assertEqual(pickup.proof.armour_bane_sources,sources[:1])
        self.assertEqual(drops[1].proof.armour_bane_sources,sources)
        self.assertEqual(drops[0].state.enemy('minion1').state.current_resilience.bonus,0)
        self.assertEqual(pickup.state.enemy('minion1').state.current_resilience.bonus,1)
        self.assertEqual(drops[1].source.enemy('minion1').state.current_resilience.bonus,0)
        self.assertEqual(drops[1].state.enemy('minion1').state.current_resilience.bonus,0)
        self.assertEqual(result.state.enemy('minion1').definition,self.source.enemies[0].definition)

    def test_reordered_or_erased_actual_drop_provenance_cannot_pass_the_source_owner(self):
        drop=tuple(step for step in self.result.steps if type(step.proof) is PcNpcShieldDropProof)[1]
        sources=drop.proof.armour_bane_sources
        reversed_proof=replace(drop.proof,armour_bane_sources=sources[::-1])
        with self.assertRaisesRegex(ValueError,'current weapon|prefix|source'):
            npc_shield_drop_updates(drop.source,reversed_proof)
        for wrong in ((),sources[:1],sources*2):
            with self.subTest(wrong=wrong),self.assertRaises((TypeError,ValueError)):
                forged=replace(drop.proof,armour_bane_sources=wrong)
                npc_shield_drop_updates(drop.source,forged)


if __name__=='__main__':
    unittest.main()
