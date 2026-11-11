"""Literal protective Melee uses generic bonuses, never Attack-only abilities."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_pistol_scenarios import pistol_profile
from tests.unit.test_m54_pistol_execution import execute, incoming, raw, shots, steps
from towr.domain.condition_models import Condition
from towr.domain.pc_bestigor_models import PcNpcBloodRageProof, pc_bestigor_glorious_source
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, PcProfileWoundProof,
    build_pc_melee_attack, initial_pc_melee_state,
)
from towr.domain.pc_npc_blood_rage_policy_models import BLOOD_RAGE_RULE_ID
from towr.domain.pc_npc_catalog import PcBookNpcProfile
from towr.domain.pc_npc_close_shooting_models import PcNpcCloseShootingProtectionPolicy as Policy
from towr.domain.pc_npc_distraction_models import (
    DISTRACTED_TEST_RULE_ID, PcNpcDistractionExpiredProof,
)
from towr.domain.pc_npc_grudge_models import expected_pc_npc_grudge_encounter
from towr.domain.pc_npc_grudge_policy_models import GRUDGES_TO_SETTLE_RULE_ID, PcNpcGrudgePolicy
from towr.domain.pc_ranged_models import PcRangedReloadProof
from towr.domain.protection_models import CLOSE_RANGED_MELEE_RULE_ID
from towr.domain.test_models import DiceModifier, Skill, TestQuality
from towr.domain.turn_models import CombatTurnStartRequest
from towr.engine.pc_melee_runner import apply_pc_melee_step
from towr.rules.test_resolution import resolve_test
from towr.rules.turn_resolution import start_combat_turn


PROFILES = (
    (PcBookNpcProfile.NASTY_SKULKER, 'skulkers', 'skulker1', 4, 4, 3, 6, False),
    (PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER, 'brewguards', 'brewguard1', 4, 3, 2, 4, True),
    (PcBookNpcProfile.DWARF_MINER_PICKAXE, 'miners', 'miner1', 4, 3, 1, 4, False),
    (PcBookNpcProfile.BESTIGOR_MASSIVE_AXE, 'bestigors', 'bestigor1', 4, 4, 3, 8, True),
)


def special_scene(profile=PcBookNpcProfile.BESTIGOR_MASSIVE_AXE, skill=Skill.MELEE,
        *, rounds=1, pc_count=1, melee_actor_ids=(), grudge_focus=None, voluntary_rage=False):
    _, keyword, actor, _, _, _, _, _ = next(row for row in PROFILES if row[0] is profile)
    base = book_pc_scenario(footpads=0,townsfolk=0,pc_count=pc_count,
        max_rounds=rounds,**{keyword:1})
    party = tuple(member if member.actor_id in melee_actor_ids else replace(member,
        pc=replace(member.pc,weapon=PcMeleeWeapon.PISTOL,ranged=pistol_profile()))
        for member in base.party)
    return replace(base,party=party,facts=replace(base.facts,outnumbering_bonus_approved=False),
        npc_grudge_policies=() if grudge_focus is None else (PcNpcGrudgePolicy(actor,grudge_focus),),
        npc_blood_rage_actor_ids=(actor,) if voluntary_rage else (),
        npc_close_shooting_protection_policies=(Policy(actor,skill),))


def prepared(source, actor='pc1'):
    state = initial_pc_melee_state(source)
    while (proof := expected_pc_npc_grudge_encounter(state)) is not None:
        state = PcMeleeStep(state,proof).state
    clock = start_combat_turn(CombatTurnStartRequest('fixture:start:'+actor,state.round_state,actor)).state
    return replace(state,round_state=clock)


class SpecialCloseShootingTests(unittest.TestCase):
    def test_all_four_profiles_use_actual_skill_without_counterattack(self):
        for profile,_,actor,melee_dice,threshold,athletics,athletics_cap,brute in PROFILES:
            for skill,dice,cap in ((Skill.MELEE,melee_dice,8),(Skill.ATHLETICS,athletics,athletics_cap)):
                with self.subTest(profile=profile,skill=skill):
                    source = special_scene(profile,skill)
                    npc_miss = ([10]*6+[1]*3 if profile is PcBookNpcProfile.BESTIGOR_MASSIVE_AXE
                        else [10]*4+[1]*3)
                    result = execute(source,[1]*3+[10]*dice+(npc_miss if brute else []))
                    shot, = shots(result)
                    test = raw(shot).defender_test
                    self.assertIs(shot.proof.protection.source_request.selected_skill,skill)
                    self.assertEqual((test.trace.base_dice,test.trace.rolled_dice,
                        test.trace.threshold,test.trace.pool_cap),(dice,dice,threshold if skill is Skill.MELEE else 3,cap))
                    self.assertEqual(test.trace.regular_dice_delta,0)
                    self.assertEqual(CLOSE_RANGED_MELEE_RULE_ID in shot.proof.protection.applied_rule_ids,
                        skill is Skill.MELEE)
                    self.assertEqual(shot.source.enemy(actor).definition,source.enemy(actor).definition)
                    self.assertEqual(result.state.participant('pc1').injury.wounds,())
                    self.assertEqual(result.executed_actions,2 if brute else 1)

    def test_modified_athletics_caps_follow_characteristic_without_second_armour_penalty(self):
        for profile,dice,cap in ((PcBookNpcProfile.DWARF_MINER_PICKAXE,1,4),
                (PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,3,8)):
            state = prepared(special_scene(profile,Skill.ATHLETICS))
            _,protection = build_pc_melee_attack(state)
            test = protection.options[0].test
            self.assertEqual(test.dice_modifiers,())
            result = resolve_test(replace(test,dice_modifiers=(DiceModifier('fixture:explicit-bonus',8),)),
                SequenceRandom([1]*cap))
            self.assertEqual((result.trace.base_dice,result.trace.pool_cap,result.trace.rolled_dice),
                (dice,cap,cap))

    def test_miner_melee_grudge_applies_to_focus_but_distracted_penalizes_other_pc(self):
        source = special_scene(PcBookNpcProfile.DWARF_MINER_PICKAXE,pc_count=2,grudge_focus='pc2')
        result = execute(source,[10]*3+[1]*3+[10]*3+[1]*5+[10]*3+[1]*3)
        other,focus = shots(result)
        self.assertEqual((raw(other).defender_test.trace.rolled_dice,
            raw(focus).defender_test.trace.rolled_dice),(3,5))
        self.assertEqual(other.proof.request.kernel_request.attack.defender_test.dice_modifiers,
            (DiceModifier(DISTRACTED_TEST_RULE_ID,-1),))
        self.assertEqual(focus.proof.request.kernel_request.attack.defender_test.dice_modifiers,
            (DiceModifier(GRUDGES_TO_SETTLE_RULE_ID,1),))
        self.assertEqual(result.executed_actions,3)

    def test_miner_athletics_never_receives_grudge_melee_bonus(self):
        source = special_scene(PcBookNpcProfile.DWARF_MINER_PICKAXE,Skill.ATHLETICS,
            pc_count=2,grudge_focus='pc2')
        result = execute(source,[10]*3+[1]+[10]*3+[1]+[10]*3+[1]*3)
        other,focus = shots(result)
        self.assertEqual((raw(other).defender_test.trace.regular_dice_delta,
            raw(focus).defender_test.trace.regular_dice_delta),(-1,0))
        self.assertEqual((raw(other).defender_test.trace.threshold,raw(focus).defender_test.trace.threshold),(1,3))
        self.assertEqual(focus.proof.request.kernel_request.attack.defender_test.dice_modifiers,())

    def test_drained_filters_positive_grudge_but_keeps_other_pc_penalty_at_preparation_boundary(self):
        for actor,expected in (('pc1',()),('pc2',(DiceModifier(DISTRACTED_TEST_RULE_ID,-1),))):
            state = prepared(special_scene(PcBookNpcProfile.DWARF_MINER_PICKAXE,
                pc_count=2,grudge_focus='pc1'),actor)
            enemy = state.enemy('miner1')
            injury = replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.DRAINED))
            state = replace(state,enemies=(replace(enemy,state=replace(enemy.state,injury=injury)),))
            _,protection = build_pc_melee_attack(state)
            self.assertEqual(protection.options[0].test.dice_modifiers,expected)

    def test_brewguard_wound_focus_penalty_applies_to_both_selected_skills(self):
        for skill,dice in ((Skill.MELEE,4),(Skill.ATHLETICS,2)):
            source = special_scene(PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER,skill,pc_count=2)
            result = execute(source,[1]*3+[10]*dice+[10]*3+[1]*(dice-1)+[10]*4+[1]*3)
            first,other = shots(result)
            self.assertEqual(raw(first).defender_test.trace.rolled_dice,dice)
            self.assertEqual(raw(other).defender_test.trace.rolled_dice,dice-1)
            self.assertEqual(other.proof.request.kernel_request.attack.defender_test.dice_modifiers,
                (DiceModifier(DISTRACTED_TEST_RULE_ID,-1),))
            self.assertEqual(result.state.npc_distractions[0].focus_actor_id,'pc1')
            self.assertEqual(incoming(result)[0].proof.request.target_id,'pc1')

    def test_confirmed_brewguard_focus_death_expires_before_terminal(self):
        source = special_scene(PcBookNpcProfile.DWARF_BREWGUARD_WARHAMMER,rounds=3)
        result = execute(source,[1]*3+[10]*4+[1]*4+[10]*3+[1]
            +[1]*3+[1]*4+[10]*3+[1,1]
            +[10]*3+[1]*4+[1]*4+[10]*3+[10]*3)
        expiry, = steps(result,PcNpcDistractionExpiredProof)
        self.assertTrue(expiry.source.participant('pc1').injury.dead)
        self.assertFalse(expiry.state.enemy('brewguard1').state.injury.conditions.has(Condition.DISTRACTED))
        self.assertEqual(result.state.npc_distractions,())
        self.assertIs(result.outcome,PcMeleeOutcome.PARTY_DEFEATED)

    def test_mixed_party_keeps_original_defence_against_melee(self):
        source = special_scene(PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,pc_count=2,melee_actor_ids=('pc2',))
        first,second = source.party
        source = replace(source,party=(first,replace(second,pc=replace(second.pc,strength=5))))
        result = execute(source,[1]*3+[10]*4+[1]*3+[10]*4)
        pistol,melee = steps(result,PcAttackProof)
        self.assertIs(pistol.proof.protection.source_request.selected_skill,Skill.MELEE)
        self.assertIs(melee.proof.protection.source_request.selected_skill,Skill.DEFENCE)
        self.assertEqual((raw(pistol).defender_test.trace.threshold,raw(melee).defender_test.trace.threshold),(4,3))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_bestigor_defence_never_acquires_rage_or_consumes_next_attack_glorious(self):
        source = special_scene(PcBookNpcProfile.BESTIGOR_MASSIVE_AXE,
            rounds=3,pc_count=2,voluntary_rage=True)
        result = execute(source,[1]*3+[10]*4+[10]*3+[1]*4+[10]*8+[1]*3
            +[1]*3+[1]*3+[10]*4+[1]*3
            +[10]*3+[1]*4+[1]*3+[10]*4)
        shot1,shot2,shot3,shot4 = shots(result)
        self.assertIsNotNone(pc_bestigor_glorious_source(shot2.source,'bestigor1'))
        self.assertIsNotNone(pc_bestigor_glorious_source(shot2.state,'bestigor1'))
        self.assertFalse(shot2.source.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))
        self.assertTrue(shot3.source.enemy('bestigor1').state.injury.conditions.has(Condition.STAGGERED))
        for shot in (shot1,shot2,shot3,shot4):
            trace = raw(shot).defender_test.trace
            self.assertEqual((trace.base_dice,trace.regular_dice_delta,trace.rolled_dice,trace.pool_cap),(4,0,4,8))
            self.assertIs(trace.quality,TestQuality.NORMAL)
            self.assertEqual(shot.proof.request.kernel_request.attack.defender_test.dice_modifiers,())
        first,second = incoming(result)
        self.assertIs(raw(first).attacker_test.trace.quality,TestQuality.GLORIOUS)
        self.assertIsNotNone(first.proof.npc_glorious_source)
        self.assertIs(raw(second).attacker_test.trace.quality,TestQuality.NORMAL)
        self.assertIsNone(second.proof.npc_glorious_source)
        self.assertEqual((raw(first).attacker_test.trace.base_dice,raw(first).attacker_test.trace.rolled_dice),(3,4))
        self.assertEqual(first.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier(BLOOD_RAGE_RULE_ID,1),))
        self.assertEqual(len(steps(result,PcNpcBloodRageProof)),1)
        self.assertEqual(len(steps(result,PcRangedReloadProof)),2)
        self.assertEqual(result.executed_actions,8)

    def test_canonical_policy_and_actual_defender_profile_reject_replay_or_forgery(self):
        result = execute(special_scene(PcBookNpcProfile.DWARF_MINER_PICKAXE),[1]*3+[10]*4)
        shot, = shots(result)
        self.assertEqual(apply_pc_melee_step(shot.source,shot),shot.state)
        with self.assertRaises((TypeError,ValueError)):
            apply_pc_melee_step(shot.state,shot)
        for kind in ('policy','cap'):
            forged = deepcopy(shot)
            if kind=='policy':
                object.__setattr__(forged.source.source.npc_close_shooting_protection_policies[0],'skill',Skill.ATHLETICS)
            else:
                object.__setattr__(forged.proof.protection.source_request.options[0].test.profile,'pool_cap',4)
            with self.subTest(kind=kind),self.assertRaises((TypeError,ValueError)):
                apply_pc_melee_step(forged.source,forged)


if __name__ == '__main__':
    unittest.main()
