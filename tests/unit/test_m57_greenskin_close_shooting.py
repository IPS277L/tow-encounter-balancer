"""Literal Orc/Big 'Un Close Shooting opposition and Attack-only Waaagh Help."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from tests.unit.test_m54_pistol_execution import execute, incoming, raw, shots, steps
from tests.unit.test_m56_close_shooting_execution import prepared_state
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcNpcHelpProof, PcProfileWoundProof,
    build_pc_melee_attack,
)
from towr.domain.pc_npc_catalog import PcBookNpcProfile
from towr.domain.pc_npc_close_shooting_models import (
    PcNpcCloseShootingProtectionPolicy as Policy, pc_close_shooting_protection_profile,
)
from towr.domain.pc_npc_help_models import PcNpcHelpPolicy, WAAAGH_HELP_RULE_ID
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.protection_models import CLOSE_RANGED_MELEE_RULE_ID
from towr.domain.test_models import DiceModifier, Skill, SuccessModifier
from towr.engine.pc_melee_runner import apply_pc_melee_step
from towr.rules.test_resolution import resolve_test


PROFILES = (
    (PcBookNpcProfile.ORC_BOY_CHOPPAS, 'orcs', 'orc1', False),
    (PcBookNpcProfile.ORC_BOY_SPEAR, 'unshielded_orcs', 'unshielded_orc1', False),
    (PcBookNpcProfile.BIG_UN_CHOPPAS, 'big_uns', 'big_un1', True),
    (PcBookNpcProfile.BIG_UN_SPEAR, 'unshielded_big_uns', 'unshielded_big_un1', True),
)


def greenskin_scene(profile=PcBookNpcProfile.BIG_UN_CHOPPAS, skill=Skill.MELEE,
        *, rounds=1, pc_count=1, melee_actor_ids=()):
    _, keyword, _, _ = next(row for row in PROFILES if row[0] is profile)
    base = book_pc_scenario(footpads=0,townsfolk=0,pc_count=pc_count,
        max_rounds=rounds,**{keyword:1})
    party = tuple(member if member.actor_id in melee_actor_ids else replace(member,
        pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,ranged=pistol_profile()))
        for member in base.party)
    return replace(base,party=party,facts=replace(base.facts,outnumbering_bonus_approved=False),
        npc_close_shooting_protection_policies=tuple(Policy(enemy.state.actor_id,skill)
            for enemy in base.enemies))


class GreenskinCloseShootingTests(unittest.TestCase):
    def test_all_four_canonical_loadouts_use_melee_or_printed_athletics(self):
        for profile, _, actor, brute in PROFILES:
            for skill, threshold in ((Skill.MELEE,4),(Skill.ATHLETICS,3)):
                with self.subTest(profile=profile,skill=skill):
                    source = greenskin_scene(profile,skill)
                    result = execute(source,[1]*3+[10]*3+([10]*3+[1]*3 if brute else []))
                    shot, = shots(result)
                    defender = raw(shot).defender_test
                    self.assertIs(shot.proof.protection.source_request.selected_skill,skill)
                    self.assertEqual((defender.trace.base_dice,defender.trace.rolled_dice,
                        defender.trace.threshold,defender.trace.pool_cap),(3,3,threshold,6))
                    self.assertEqual(CLOSE_RANGED_MELEE_RULE_ID in shot.proof.protection.applied_rule_ids,
                        skill is Skill.MELEE)
                    self.assertEqual(shot.source.enemy(actor).definition,source.enemy(actor).definition)
                    self.assertFalse(source.enemy(actor).state.holds_shield)
                    self.assertEqual(result.executed_actions,2 if brute else 1)

    def test_big_un_strength_four_does_not_turn_melee_or_athletics_cap_into_eight(self):
        for profile,_,_,brute in PROFILES:
            if not brute:
                continue
            state = prepared_state(greenskin_scene(profile))
            definition = state.enemies[0].definition
            for skill in (Skill.MELEE,Skill.ATHLETICS):
                selected_profile = pc_close_shooting_protection_profile(definition,skill)
                _,preparation = build_pc_melee_attack(state)
                test = replace(preparation.options[0].test,profile=selected_profile.test_profile,
                    dice_modifiers=(DiceModifier('fixture:bounded-bonus',8),))
                result = resolve_test(test,SequenceRandom([1]*6))
                self.assertEqual((result.trace.base_dice,result.trace.pool_cap,result.trace.rolled_dice),(3,6,6))

    def test_mixed_party_keeps_defence_against_melee_for_both_big_un_loadouts(self):
        for profile,_,_,brute in PROFILES:
            if not brute:
                continue
            source = greenskin_scene(profile,pc_count=2,melee_actor_ids=('pc2',))
            result = execute(source,[1]*3+[10]*3+[1]*3+[10]*3)
            pistol,melee = steps(result,PcAttackProof)
            self.assertIs(pistol.proof.protection.source_request.selected_skill,Skill.MELEE)
            self.assertIs(melee.proof.protection.source_request.selected_skill,Skill.DEFENCE)
            self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
            self.assertEqual(result.executed_actions,2)

    def test_shooting_opposition_does_not_inherit_charge_outnumber_or_pc_weapon_traits(self):
        for profile,_,_,brute in PROFILES:
            if not brute:
                continue
            source = greenskin_scene(profile,pc_count=2)
            source = replace(source,facts=replace(source.facts,outnumbering_bonus_approved=True))
            result = execute(source,[1]*3+[10]*3+[1]*3+[10]*3)
            for shot in shots(result):
                attack = raw(shot)
                self.assertEqual(attack.attacker_test.trace.regular_dice_delta,0)
                self.assertEqual(attack.defender_test.trace.regular_dice_delta,0)
                self.assertEqual(attack.defender_test.trace.success_delta,0)
                self.assertEqual(shot.proof.request.kernel_request.attack.defender_test.dice_modifiers,())

    def test_both_big_uns_keep_wound_one_drained_reload_and_second_wound_defeat(self):
        for profile,_,actor,brute in PROFILES:
            if not brute:
                continue
            for skill in (Skill.MELEE,Skill.ATHLETICS):
                source = greenskin_scene(profile,skill,rounds=3)
                result = execute(source,[1]*3+[10]*3+[10]*3+[1]*3
                    +[1]*3+[10]*3+[1]*3+[1]*3+[10]*3)
                first,second = shots(result)
                first_ack = steps(result,PcProfileWoundProof)[0]
                self.assertTrue(first_ack.state.enemy(actor).state.injury.conditions.has(Condition.DRAINED))
                self.assertTrue(second.source.enemy(actor).state.injury.conditions.has(Condition.DRAINED))
                self.assertEqual(raw(second).defender_test.trace.regular_dice_delta,0)
                self.assertEqual(raw(second).defender_test.trace.pool_cap,6)
                self.assertTrue(result.state.enemy(actor).state.injury.defeated)
                self.assertEqual(len(steps(result,PcRangedReloadProof)),1)
                self.assertEqual(result.executed_actions,5)
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_waaagh_free_success_stays_on_attack_and_never_leaks_into_defensive_melee(self):
        base = book_pc_scenario(footpads=0,townsfolk=0,orcs=1,big_uns=1,pc_count=1,max_rounds=3)
        member = base.party[0]
        priority = ('big_un1','orc1')
        member = replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,ranged=pistol_profile()),
            target_priority=priority,defeat_decisions=tuple(member.defeat_decision(actor) for actor in priority))
        source = replace(base,party=(member,),enemy_activation_order=('orc1','big_un1'),
            facts=replace(base.facts,outnumbering_bonus_approved=False),
            npc_help_policies=(PcNpcHelpPolicy('orc1','big_un1'),),
            npc_close_shooting_protection_policies=(Policy('orc1',Skill.MELEE),Policy('big_un1',Skill.MELEE)))
        result = execute(source,[1]*3+[10]*3+[10]*3+[1]*3
            +[1]*3+[10]*3+[1]*3+[1]*3+[10]*3+[10]*3+[1]*3)
        helps = steps(result,PcNpcHelpProof)
        self.assertEqual(len(helps),2)
        for attack in incoming(result):
            modifiers = attack.proof.request.kernel_request.attack.attacker_test.success_modifiers
            if attack.proof.request.actor_id=='big_un1':
                self.assertEqual(modifiers,(SuccessModifier(WAAAGH_HELP_RULE_ID,1),))
                self.assertEqual(len(attack.proof.npc_help_applications),1)
            else:
                self.assertEqual(modifiers,())
        for shot in shots(result):
            self.assertEqual(raw(shot).defender_test.trace.success_delta,0)
            self.assertEqual(shot.proof.request.kernel_request.attack.defender_test.success_modifiers,())
        self.assertTrue(helps[0].source.enemy('big_un1').state.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(result.executed_actions,8)
        self.assertEqual(result.state.participant('pc1').injury.wounds,())

    def test_defensive_melee_win_adds_no_counterattack_or_extra_action(self):
        result = execute(greenskin_scene(PcBookNpcProfile.ORC_BOY_SPEAR),
            [10]*3+[1]*3+[10]*3+[1]*3)
        shot, = shots(result)
        self.assertEqual(shot.state.participant('pc1').injury.wounds,())
        self.assertTrue(result.state.participant('pc1').injury.conditions.has(Condition.STAGGERED))
        self.assertEqual(len(incoming(result)),1)
        self.assertEqual(result.executed_actions,2)

    def test_canonical_new_profile_and_policy_cannot_be_swapped_or_replayed(self):
        result = execute(greenskin_scene(PcBookNpcProfile.ORC_BOY_CHOPPAS),[1]*3+[10]*3)
        shot, = shots(result)
        self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(shot.state,shot)
        for field in ('policy','cap'):
            forged = deepcopy(shot)
            if field=='policy':
                object.__setattr__(forged.source.source.npc_close_shooting_protection_policies[0],'skill',Skill.ATHLETICS)
            else:
                object.__setattr__(forged.proof.protection.source_request.options[0].test.profile,'pool_cap',8)
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(forged.source,forged)


if __name__ == '__main__':
    unittest.main()
