"""Armour Bane from actual PC/generated attacks, without prepared battle states."""
from dataclasses import replace
import unittest

from tests.support.armour_fixtures import light_loadout
from tests.support.generated_weapon_sources import initial_generated_weapons
from tests.support.pc_melee_fixtures import make_pc_melee_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.support.pc_weapon_sources import initial_weapon_items
from tests.support.talent_sources import paid_talent,free_talent
from towr.domain.attack_models import AttackOutcome,ImpactOutcome
from towr.domain.generated_npc_models import GeneratedNpc,GeneratedWeapon
from towr.domain.pc_melee_models import (
    PcFatePolicy,PcNearMissPolicy,PcMeleeWeapon,PcTwoHandedGrip,PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcMeleeStep,PcWoundCompletionProof,initial_pc_melee_state,
)
from towr.domain.pc_shield_models import pc_shield_resilience
from towr.domain.talent_catalog import TalentId
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario


BANE=(paid_talent(TalentId.ARMOUR_BANE),)


def pc_source(weapon=PcMeleeWeapon.AXE):
    if weapon is PcMeleeWeapon.PISTOL:
        source=make_pc_pistol_scenario(max_rounds=3,ballistic_skill=4,shooting=5,dexterity=5)
        toughness,strength=20,3
    else:
        source=make_pc_melee_scenario(weapon=weapon,max_rounds=2)
        toughness,strength=(4,1) if weapon is PcMeleeWeapon.GREATAXE else (3,3)
    member=source.party[0]
    hand=PcTwoHandedGrip.BOTH if weapon is PcMeleeWeapon.GREATAXE else PcWeaponHand.LEFT
    member=replace(member,pc=replace(member.pc,strength=strength,toughness=20),
        initial_weapon_hand=hand,combat_equipment=initial_weapon_items(weapon,hand,
            initially_loaded=True if weapon is PcMeleeWeapon.PISTOL else None),talents=BANE)
    target=GeneratedNpc(2,3,toughness,2,4,4,initial_generated_weapons(GeneratedWeapon.STAFF),
        light_loadout(light=True,shield=True),defence=4)
    return replace(source,party=(member,),enemies=(target.participant('minion1'),),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


def npc_source():
    source=make_pc_melee_scenario(max_rounds=2)
    member=source.party[0]
    member=replace(member,pc=replace(member.pc,armour_bonus=1),
        armour=light_loadout(light=True,shield=True),shield=shield_loadout(PcWeaponHand.RIGHT),
        combat_equipment=initial_weapon_items(PcMeleeWeapon.STAFF,PcWeaponHand.LEFT))
    attacker=GeneratedNpc(2,3,20,2,4,4,initial_generated_weapons(GeneratedWeapon.AXE),
        light_loadout(),defence=4,talents=BANE)
    return replace(source,party=(member,),enemies=(attacker.participant('minion1'),),
        facts=replace(source.facts,outnumbering_bonus_approved=False))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def attacks(result,actor):
    return tuple(step for step in result.steps if type(step.proof) is PcAttackProof
        and step.proof.request.actor_id==actor)


class ArmourBaneExecutionTests(unittest.TestCase):
    def assert_replays(self,result):
        state=initial_pc_melee_state(result.source)
        for step in result.steps:
            state=apply_pc_melee_step(state,step)
        self.assertEqual(state,result.state)

    def test_pc_axe_and_greataxe_use_old_resilience_before_future_attacks_see_reduction(self):
        for weapon,first_rolls,old,damage in ((PcMeleeWeapon.AXE,[1,10,10],5,5),
                (PcMeleeWeapon.GREATAXE,[1,10],6,6)):
            with self.subTest(weapon=weapon):
                source=pc_source(weapon)
                result=execute(source,first_rolls+[10]*7+first_rolls+[10]*2)
                first,second=attacks(result,source.party[0].actor_id)
                actual=first.proof.execution.resolution.attack
                self.assertIs(actual.outcome,AttackOutcome.HIT)
                self.assertEqual((actual.damage,actual.effective_resilience),(damage,old))
                self.assertIs(actual.impact,ImpactOutcome.STAGGERED)
                self.assertEqual(first.proof.armour_bane.before.total,old)
                self.assertEqual(first.proof.armour_bane.after.total,old-1)
                self.assertEqual(first.state.enemy('minion1').state.current_resilience.total,old-1)
                self.assertEqual(second.proof.request.kernel_request.attack.impact_spec.resilience.total,old-1)
                self.assertIs(second.proof.execution.resolution.attack.impact,ImpactOutcome.WOUND)
                self.assertEqual(result.source.enemies[0].definition.generated_components.armour,
                    first.state.enemy('minion1').definition.generated_components.armour)
                self.assertEqual(initial_pc_melee_state(source).enemy('minion1').state.current_resilience.total,old)
                self.assert_replays(result)

    def test_pc_pistol_keeps_toughness_comparison_while_reducing_real_armour_between_shots(self):
        source=pc_source(PcMeleeWeapon.PISTOL)
        shot=[1,10,10,10]+[10]*2
        result=execute(source,shot+[10]*5+[1]*3+[10]*5+shot+[10]*5)
        first,second=attacks(result,source.party[0].actor_id)
        for step,total in ((first,22),(second,21)):
            self.assertEqual(step.proof.armour_bane.before.total,total)
            self.assertEqual(step.proof.armour_bane.after.total,total-1)
            self.assertEqual(step.proof.execution.resolution.attack.effective_resilience,20)
            self.assertTrue(step.proof.request.kernel_request.attack.impact_spec.ignores_armour)
        self.assertEqual(second.state.enemy('minion1').state.current_resilience.total,20)
        self.assertFalse(second.state.enemy('minion1').state.current_resilience.is_armoured)
        self.assert_replays(result)

    def test_generated_npc_axe_changes_pc_future_resilience_without_touching_physical_items(self):
        source=npc_source()
        # First PC hit Staggers the high-T NPC. NPC first hit equals the PC's
        # original R5, second hit exceeds reduced R4 and rolls superficial1.
        result=execute(source,[1,10,10]+[10]*2+[1,10]+[10]*3
            +[10]*5+[1,10]+[10]*3+[1])
        first,second=attacks(result,'minion1')
        self.assertEqual(first.proof.execution.resolution.attack.damage,5)
        self.assertEqual(first.proof.execution.resolution.attack.effective_resilience,5)
        self.assertIs(first.proof.execution.resolution.attack.impact,ImpactOutcome.STAGGERED)
        self.assertEqual(pc_shield_resilience(first.state,'pc').total,4)
        self.assertEqual(second.proof.execution.resolution.attack.effective_resilience,4)
        self.assertEqual(pc_shield_resilience(second.state,'pc').total,3)
        self.assertFalse(pc_shield_resilience(second.state,'pc').is_armoured)
        self.assertEqual(result.state.participant('pc').shield.location,
            initial_pc_melee_state(source).participant('pc').shield.location)
        self.assertFalse(hasattr(result.state.enemy('minion1').state,'fate'))
        self.assertEqual(pc_shield_resilience(initial_pc_melee_state(source),'pc').total,5)
        self.assert_replays(result)

    def test_miss_does_not_create_an_application(self):
        source=replace(pc_source(),max_rounds=1)
        result=execute(source,[10]*10)
        actual=attacks(result,source.party[0].actor_id)[0]
        self.assertIs(actual.proof.execution.resolution.attack.outcome,AttackOutcome.MISS)
        self.assertIsNone(actual.proof.armour_bane)
        self.assertEqual(actual.state.enemy('minion1').state.current_resilience.total,5)
        self.assert_replays(result)

    def test_atomic_application_cannot_be_erased_repeated_replaced_or_forged(self):
        source=pc_source()
        hit=[1,10,10]
        result=execute(source,hit+[10]*7+hit+[10]*2)
        first,second=attacks(result,source.party[0].actor_id)
        application=first.proof.armour_bane
        for changes in (dict(armour_bane=None),dict(armour_bane=second.proof.armour_bane),
                dict(armour_bane=replace(application,talent=free_talent(TalentId.ARMOUR_BANE))),
                dict(armour_bane=replace(application,target_id='foreign')),
                dict(armour_bane=replace(application,before=replace(application.before,bonus=3)))):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(first.source,replace(first.proof,**changes))
        with self.assertRaises(ValueError):
            PcMeleeStep(first.state,first.proof)
        changed=replace(source,party=(replace(source.party[0],talents=()),))
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(replace(first.source,source=changed),first.proof)

    def test_generated_npc_hit_keeps_bane_loss_after_actual_pc_near_miss(self):
        from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome
        source=npc_source()
        member=replace(source.party[0],fate_policy=PcFatePolicy.CONFIGURED,
            near_miss_policy=PcNearMissPolicy(1,0))
        npc=replace(source.enemies[0].definition.generated_components,strength=4)
        source=replace(source,max_rounds=1,party=(member,),enemies=(npc.participant('minion1'),))
        result=execute(source,[1,10,10]+[10]*2+[1,10]+[10]*3+[1])
        attack,=attacks(result,'minion1')
        self.assertIs(attack.proof.execution.resolution.attack.outcome,AttackOutcome.HIT)
        self.assertIs(attack.proof.execution.resolution.attack.impact,ImpactOutcome.WOUND)
        self.assertEqual(attack.proof.execution.resolution.attack.effective_resilience,5)
        self.assertEqual(attack.proof.armour_bane.reduction,1)
        self.assertEqual(attack.proof.armour_bane.after.total,4)
        completion,=tuple(step.proof.completion for step in result.steps
            if type(step.proof) is PcWoundCompletionProof)
        self.assertIs(completion.outcome,CharacterWoundLifecycleOutcome.NEAR_MISS)
        pc=result.state.participant('pc')
        self.assertEqual(pc.injury.wounds,())
        self.assertEqual(pc.daily_wounds.wound_count,0)
        self.assertEqual(pc.fate.rating,member.fate.rating-1)
        self.assertEqual(pc_shield_resilience(result.state,'pc').total,4)
        self.assert_replays(result)

    def test_actual_meteoric_ward_cancels_mundane_axe_qualification_on_a_hit(self):
        from towr.domain.armour_models import ArmourLoadout,BodyArmour,ShieldKind
        source=pc_source()
        npc=replace(source.enemies[0].definition.generated_components,
            armour=ArmourLoadout((BodyArmour.METEORIC_IRON,),BodyArmour.METEORIC_IRON,
                shield=ShieldKind.SHIELD))
        source=replace(source,max_rounds=1,enemies=(npc.participant('minion1'),))
        result=execute(source,[1,10,10]+[10]*7)
        attack,=attacks(result,source.party[0].actor_id)
        self.assertIs(attack.proof.execution.resolution.attack.outcome,AttackOutcome.HIT)
        self.assertTrue(attack.proof.request.kernel_request.attack.impact_spec.resilience.mundane_armour_ward)
        self.assertEqual(attack.proof.execution.resolution.attack.damage,4)
        self.assertEqual(attack.proof.execution.resolution.attack.effective_resilience,7)
        self.assertIsNone(attack.proof.armour_bane)
        self.assertEqual(result.state.enemy('minion1').state.current_resilience.total,7)
        self.assertTrue(result.state.enemy('minion1').state.current_resilience.mundane_armour_ward)
        self.assert_replays(result)


if __name__=='__main__':
    unittest.main()
