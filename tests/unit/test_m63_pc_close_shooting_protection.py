"""Close Shooting opposition selects actual PC Skills, equipment, Fate and Help."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_party_scenario
from tests.support.pc_pistol_scenarios import make_pc_pistol_scenario
from tests.support.pc_shield_scenarios import shield_loadout
from tests.unit.test_m61_npc_pistol_execution import execute, raw, scene as pistol_scene, shots, steps, PC_MISS
from tests.unit.test_m61_npc_pistol_source import OFFICIAL, OGRE, policy
from towr.domain.attack_models import AttackOutcome
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.pc_heavy_wound_models import critical_for_hand, usable_weapon_hand
from towr.domain.pc_help_models import build_pc_test_help
from towr.domain.pc_melee_models import (
    PcFatePolicy, PcGloriousPolicy, PcHelpPolicy, PcHelpTarget, PcMeleePolicy,
    PcMeleeWeapon, PcTwoHandedGrip, PcWeaponHand,
)
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcHelpProof, PcMeleeStep, build_pc_melee_attack, pc_protection_skill,
)
from towr.domain.pc_npc_catalog import create_pc_book_npc
from towr.domain.pc_shield_models import PcShieldLocation, pc_protection_hand
from towr.domain.pc_weapon_models import pc_weapon_requires_two_hands
from towr.domain.test_models import Skill, TestQuality
from towr.engine.pc_melee_runner import apply_pc_melee_step


def scene(*,choice=Skill.MELEE,weapon=PcMeleeWeapon.STAFF,shield=False,profiles=(OFFICIAL,),rounds=1):
    source = pistol_scene(profiles=profiles,rounds=rounds)
    member = source.party[0]
    return replace(source,party=(replace(member,pc=replace(member.pc,weapon=weapon),
        initial_weapon_hand=PcTwoHandedGrip.BOTH if pc_weapon_requires_two_hands(weapon) else PcWeaponHand.RIGHT,
        shield=shield_loadout() if shield else None,close_shooting_protection_skill=choice),))


def help_scene():
    source = make_pc_melee_party_scenario(max_rounds=1,enemy_count=1)
    enemy = create_pc_book_npc(OFFICIAL,'minion1')
    helper,receiver = source.party
    return replace(source,enemies=(enemy,),npc_pistol_policies=(policy('minion1'),),
        facts=replace(source.facts,outnumbering_bonus_approved=False),enemy_target_priority=('pc2','pc1'),
        party=(replace(helper,policy=PcMeleePolicy.HELP_ALLY_OR_ATTACK_OR_RECOVER_SELF,
            help_policy=PcHelpPolicy('pc2',PcHelpTarget.FIRST_INCOMING_PROTECTION,Skill.MELEE)),
            replace(receiver,close_shooting_protection_skill=Skill.MELEE)))


class PcCloseShootingProtectionTests(unittest.TestCase):
    def test_explicit_melee_athletics_and_absent_shield_policy_select_real_test(self):
        for choice,shield,expected,threshold in (
                (Skill.MELEE,False,Skill.MELEE,5),(Skill.ATHLETICS,True,Skill.ATHLETICS,4),
                (None,True,Skill.DEFENCE,5),(None,False,Skill.ATHLETICS,4)):
            with self.subTest(choice=choice,shield=shield):
                result = execute(scene(choice=choice,weapon=PcMeleeWeapon.SWORD,shield=shield),
                    PC_MISS+[10]*2+[1]*3)
                incoming, = shots(result)
                self.assertIs(incoming.proof.protection.source_request.selected_skill,expected)
                self.assertEqual(raw(incoming).defender_test.trace.threshold,threshold)
                self.assertEqual(raw(incoming).defender_test.trace.rolled_dice,3)
                self.assertEqual(result.executed_actions,2)
                self.assertEqual(len(steps(result,PcAttackProof)),2)
                if shield:
                    self.assertIs(result.state.participant('pc').shield.location,PcShieldLocation.HELD)

    def test_actual_weapon_drop_retains_melee_permission_without_pickup_or_fallback(self):
        result = execute(scene(weapon=PcMeleeWeapon.GREATAXE,profiles=(OFFICIAL,OFFICIAL)),
            [10]*2+[1]*3+[1]*2+[10]*2+[8,1]+[10]*2+[1]*3)
        first,second = shots(result)
        self.assertIs(first.proof.protection.source_request.selected_skill,Skill.MELEE)
        self.assertEqual(raw(first).defender_test.trace.regular_dice_delta,-1)
        self.assertIsNone(second.source.participant('pc').weapon_hand)
        self.assertIs(second.proof.protection.source_request.selected_skill,Skill.MELEE)
        self.assertEqual(raw(second).defender_test.trace.rolled_dice,3)
        self.assertEqual(raw(second).defender_test.trace.regular_dice_delta,0)
        self.assertFalse(second.proof.protection.source_request.defender_wields_weapon)
        self.assertIsNone(pc_protection_hand(second.source.participant('pc'),Skill.SHOOTING,Skill.MELEE))

    def test_owned_pistol_opposes_with_melee_without_spending_a_second_charge_or_action(self):
        source = scene()
        pistol = make_pc_pistol_scenario().party[0].pc
        source = replace(source,party=(replace(source.party[0],pc=pistol,initial_weapon_hand=PcWeaponHand.RIGHT),))
        result = execute(source,PC_MISS+[10]*2+[1]*3)
        incoming, = shots(result)
        owned_before = incoming.source.participant('pc').ranged
        self.assertFalse(owned_before.loaded)
        self.assertEqual(owned_before,incoming.state.participant('pc').ranged)
        self.assertIs(incoming.proof.protection.source_request.selected_skill,Skill.MELEE)
        self.assertEqual(raw(incoming).defender_test.trace.threshold,5)
        self.assertEqual(result.executed_actions,2)
        self.assertEqual(sum(step.proof.ranged_shot is not None for step in steps(result,PcAttackProof)),1)
        self.assertIs(pc_protection_hand(incoming.source.participant('pc'),Skill.SHOOTING,Skill.MELEE),
            PcWeaponHand.RIGHT)

    def test_general_melee_traits_apply_to_opposition_using_the_held_weapon(self):
        for weapon,own_dice,defender_dice,delta in (
                (PcMeleeWeapon.GREATAXE,2,2,-1),(PcMeleeWeapon.GREATHAMMER,2,2,-1),
                (PcMeleeWeapon.FLAIL,3,1,-2),(PcMeleeWeapon.MORNING_STAR,3,2,-1)):
            with self.subTest(weapon=weapon):
                result = execute(scene(weapon=weapon),[10]*own_dice+[1]*3+[10]*2+[1]*defender_dice)
                incoming, = shots(result)
                self.assertTrue(incoming.source.participant('pc').injury.conditions.has(Condition.STAGGERED))
                trace = raw(incoming).defender_test.trace
                self.assertEqual((trace.rolled_dice,trace.regular_dice_delta),(defender_dice,delta))

    def test_sword_glaive_defence_and_warhammer_attack_traits_do_not_become_melee_opposition_bonuses(self):
        for weapon in (PcMeleeWeapon.SWORD,PcMeleeWeapon.GLAIVE,PcMeleeWeapon.WARHAMMER):
            with self.subTest(weapon=weapon):
                # Exactly one success only Staggers the Ogre; the PC stays
                # healthy and the active Sword/Glaive Defence trait is visible
                # to the selector without applying to selected Melee.
                result = execute(scene(weapon=weapon,profiles=(OGRE,)),
                    [1,10,10]+[10]*3+[10]*3+[1]*3)
                incoming, = shots(result)
                self.assertFalse(incoming.source.participant('pc').injury.conditions.has(Condition.STAGGERED))
                self.assertTrue(incoming.source.enemy('minion1').state.injury.conditions.has(Condition.STAGGERED))
                self.assertEqual(raw(incoming).defender_test.trace.regular_dice_delta,0)
                self.assertEqual(raw(incoming).defender_test.trace.rolled_dice,3)

    def test_melee_glorious_window_and_wound_ten_grim_are_bound_to_actual_protection(self):
        source = scene(profiles=(OGRE,))
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,strength=1),
            fate_policy=PcFatePolicy.CONFIGURED,glorious_policy=PcGloriousPolicy((Skill.MELEE,),0,0)),))
        result = execute(source,[1]*3+[10]*3+[1,10,10]+[10]*3+[1]*3)
        incoming, = shots(result)
        trace = raw(incoming).defender_test.trace
        self.assertIs(trace.quality,TestQuality.GLORIOUS)
        self.assertEqual(trace.initial_values,(10,10,10))
        self.assertEqual(trace.final_values,(1,1,1))
        self.assertEqual(len(result.state.participant('pc').fate.spends),1)
        self.assertEqual(incoming.proof.glorious.source_request.test,
            incoming.proof.request.kernel_request.attack.defender_test)
        result = execute(scene(profiles=(OFFICIAL,)*3),PC_MISS+[1]*2+[10]*3+[10]
            +[10]*2+[1]*3+[10]*3+[10]*2+[1]*3)
        _,second,third = shots(result)
        self.assertTrue(second.source.participant('pc').injury.conditions.has(Condition.DRAINED))
        self.assertIs(raw(second).defender_test.trace.quality,TestQuality.GRIM)
        self.assertIs(raw(third).defender_test.trace.quality,TestQuality.NORMAL)
        self.assertEqual(raw(second).defender_test.trace.threshold,5)

    def test_melee_protection_help_binds_incoming_test_id_and_never_the_ally_attack(self):
        result = execute(help_scene(),[1]*3+PC_MISS+[10]*2+[1]*6)
        helper, = steps(result,PcHelpProof)
        incoming, = shots(result)
        own = next(step for step in steps(result,PcAttackProof) if step.proof.request.actor_id=='pc2')
        self.assertIs(helper.proof.request.help_skill,Skill.MELEE)
        intended = result.source.id+':r1:minion1:protection'
        self.assertEqual(helper.proof.request.beneficiary_test_id,intended)
        self.assertEqual(raw(incoming).defender_test.trace.request_id,intended)
        self.assertEqual(own.proof.help_applications,())
        application, = incoming.proof.help_applications
        self.assertEqual(application.source_request.help,helper.proof.execution)
        self.assertEqual(raw(incoming).defender_test.trace.regular_dice_delta,3)
        self.assertEqual(result.executed_actions,3)
        self.assertEqual(len(steps(result,PcAttackProof)),2)
        for step in (helper,incoming):
            self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
            with self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(step.state,step)
        for changes in ({'id':intended+':other'},{'id':result.source.id+':r2:minion1:protection'}):
            # Pure receipt eligibility boundary: a previous receipt must not
            # follow a different actual Test into another action or round.
            test = replace(incoming.proof.request.kernel_request.attack.defender_test,**changes,dice_modifiers=())
            _,applications = build_pc_test_help(incoming.source,'pc2',Skill.MELEE,test)
            self.assertEqual(applications,())
        original = replace(incoming.proof.request.kernel_request.attack.defender_test,dice_modifiers=())
        _,applications = build_pc_test_help(incoming.source,'pc2',Skill.ATHLETICS,original)
        self.assertEqual(applications,())
        forged = deepcopy(helper.proof)
        object.__setattr__(forged.request,'help_skill','melee')
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(helper.source,forged)

    def test_focused_drained_defenceless_and_non_shooting_preparation_preserve_boundaries(self):
        result = execute(help_scene(),[1]*3+PC_MISS+[10]*2+[1]*6)
        incoming, = shots(result)
        for condition in (Condition.DRAINED,Condition.DEFENCELESS):
            # Focused pure preparation, not a claimed fresh public journal.
            state = replace(incoming.source,party=tuple(replace(member,injury=replace(member.injury,
                conditions=ConditionState(frozenset({condition})))) if member.actor_id=='pc2' else member
                for member in incoming.source.party))
            prepared,protection = build_pc_melee_attack(state)
            if condition is Condition.DRAINED:
                self.assertIs(protection.selected_skill,Skill.MELEE)
                self.assertFalse(any(modifier.amount>0 for modifier in prepared.kernel_request.attack.defender_test.dice_modifiers))
            else:
                self.assertIsNone(protection.selected_skill)
                self.assertIsNone(prepared.kernel_request.attack.defender_test)
        member = incoming.source.participant('pc2')
        self.assertIs(pc_protection_skill(member,Skill.THROWING,Skill.MELEE),Skill.ATHLETICS)
        self.assertIs(pc_protection_skill(member,Skill.MELEE,Skill.ATHLETICS),Skill.DEFENCE)
        self.assertIs(pc_protection_skill(member,Skill.BRAWN,Skill.MELEE),Skill.ENDURANCE)

    def test_focused_actual_hand_twelve_both_and_unusable_weapon_do_not_invent_hand_use(self):
        hit = [1]*2+[10]*3
        result = execute(scene(weapon=PcMeleeWeapon.GLAIVE,profiles=(OFFICIAL,)*3),PC_MISS+hit+[1]+hit+[1,1]
            +hit+[10,1,1]+[1]+[1,10,10])
        injured = result.state.participant('pc')
        self.assertIsNone(injured.weapon_hand)
        self.assertFalse(injured.injury.conditions.has(Condition.CRITICALLY_INJURED))
        # Focused equipment use on a real W12/body record. The public journal
        # above dropped its weapon; this does not claim a free pickup.
        held = replace(injured,weapon_hand=PcTwoHandedGrip.BOTH)
        hand = pc_protection_hand(held,Skill.SHOOTING,Skill.MELEE)
        self.assertIs(hand,PcTwoHandedGrip.BOTH)
        self.assertTrue(critical_for_hand(held,hand).conditions.has(Condition.CRITICALLY_INJURED))
        self.assertIsNone(pc_protection_hand(injured,Skill.SHOOTING,Skill.MELEE))
        self.assertIsNone(pc_protection_hand(held,Skill.SHOOTING,Skill.ATHLETICS))
        self.assertFalse(critical_for_hand(held,None).conditions.has(Condition.CRITICALLY_INJURED))
        result = execute(scene(weapon=PcMeleeWeapon.GLAIVE,profiles=(OFFICIAL,)*3),PC_MISS+hit+[1]+hit+[1,1]
            +hit+[10,5,1]+[1])
        unusable = result.state.participant('pc')
        self.assertIsNone(usable_weapon_hand(unusable))
        self.assertIs(pc_protection_skill(unusable,Skill.SHOOTING,Skill.MELEE),Skill.MELEE)
        self.assertIsNone(pc_protection_hand(unusable,Skill.SHOOTING,Skill.MELEE))


if __name__ == '__main__':
    unittest.main()
