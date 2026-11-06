"""Profile Conditions are acknowledged once; each creature keeps its own attacks."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from tests.unit.test_m28_pc_beast_orc_modifiers import pure_active
from towr.domain.condition_models import Condition,ConditionState,StaggerChoice,StaggerRequest
from towr.domain.injury_models import ProfileInjuryState,ProfileNpcType,ProfileStateChangeRequest
from towr.domain.pc_melee_models import PcMeleeWeapon
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcMeleeOutcome,PcMeleeStep,PcProfileWoundProof,build_pc_melee_attack,
)
from towr.domain.pc_npc_ability_models import pc_npc_allows_give_ground
from towr.domain.pc_npc_catalog import PcBookNpcProfile,get_pc_book_npc_entry
from towr.domain.pc_npc_wound_models import pc_npc_prone_profile_wound_state
from towr.domain.test_models import DiceModifier
from towr.engine.pc_melee_runner import apply_pc_melee_step,run_pc_melee_scenario
from towr.rules.stagger_resolution import resolve_stagger


def scene(*,pcs=1,axe=False,rounds=1,**counts):
    source=book_pc_scenario(footpads=0,townsfolk=0,pc_count=pcs,max_rounds=rounds,**counts)
    return replace(source,facts=replace(source.facts,outnumbering_bonus_approved=False),
        party=tuple(replace(member,pc=replace(member.pc,weapon=PcMeleeWeapon.AXE))
            if axe else member for member in source.party))


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def incoming(result,actor):
    return tuple(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id==actor)


class PcCreatureExecutionTests(unittest.TestCase):
    def test_centigor_first_wound_adds_prone_after_ack_and_its_attack_still_executes(self):
        result=execute(scene(centigors=1,axe=True),[1]*3+[10]*4+[1]*4+[10]*3+[1])
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertFalse(ack.source.enemy('centigor1').state.injury.conditions.has(Condition.PRONE))
        self.assertTrue(ack.state.enemy('centigor1').state.injury.conditions.has(Condition.PRONE))
        self.assertFalse(ack.state.enemy('centigor1').state.injury.conditions.has(Condition.DRAINED))
        attack,=incoming(result,'centigor1')
        self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertEqual(attack.proof.execution.resolution.attack.impact_spec.damage.base,4)
        self.assertTrue(attack.source.enemy('centigor1').state.holds_shield)
        self.assertTrue(result.state.enemy('centigor1').state.injury.conditions.has(Condition.PRONE))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)

    def test_next_pc_receives_higher_ground_and_second_wound_defeats_centigor(self):
        result=execute(scene(centigors=1,pcs=2,axe=True),[1]*3+[10]*4+[1]*4+[10]*4)
        acks=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(tuple((s.proof.source.current_wounds,s.proof.source.defeated) for s in acks),((1,False),(2,True)))
        second=next(s for s in result.steps if type(s.proof) is PcAttackProof and s.proof.request.actor_id=='pc2')
        self.assertEqual(second.proof.request.kernel_request.attack.attacker_test.dice_modifiers,
            (DiceModifier('RULE-COMBAT-007:higher-ground',1),))
        self.assertEqual(second.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertFalse(incoming(result,'centigor1'))
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_repeated_stagger_wound_removes_old_stagger_before_adding_profile_prone(self):
        tied=[1,10,10,1,10,10,10]
        result=execute(scene(centigors=1,pcs=3),tied*2
            +[1,10,10,10,1,10,10,10]+[1]*4+[10]*3+[1])
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        self.assertEqual(ack.state.enemy('centigor1').state.injury.conditions.conditions,frozenset({Condition.PRONE}))
        self.assertEqual(ack.state.enemy('centigor1').state.injury.wounds,1)
        self.assertEqual(result.state.enemy('centigor1').state.injury.wounds,1)

    def test_prone_centigor_cannot_give_ground_or_fall_prone_again(self):
        definition=get_pc_book_npc_entry(PcBookNpcProfile.CENTIGOR_SPEAR).definition
        injury=pc_npc_prone_profile_wound_state(definition,
            ProfileInjuryState(1,2,ConditionState(frozenset({Condition.STAGGERED}))),
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False))
        result=resolve_stagger(StaggerRequest('repeated',injury.conditions,True,False))
        self.assertEqual(result.allowed_choices,(StaggerChoice.SUFFER_WOUND,))
        self.assertTrue(result.wound_requested)

    def test_prone_ack_is_exact_first_band_preserves_other_conditions_and_rejects_forged_source(self):
        definition=get_pc_book_npc_entry(PcBookNpcProfile.CENTIGOR_SPEAR).definition
        injury=ProfileInjuryState(1,2,ConditionState(frozenset({Condition.DRAINED})))
        change=ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False)
        actual=pc_npc_prone_profile_wound_state(definition,injury,change)
        self.assertEqual(actual.conditions.conditions,frozenset({Condition.DRAINED,Condition.PRONE}))
        self.assertIs(pc_npc_prone_profile_wound_state(definition,actual,
            ProfileStateChangeRequest(ProfileNpcType.BRUTE,1,2,True)),actual)
        with self.assertRaises(ValueError):
            pc_npc_prone_profile_wound_state(definition,ProfileInjuryState(0,2),change)
        with self.assertRaises(ValueError):
            pc_npc_prone_profile_wound_state(replace(definition,wound_limit=3),injury,change)

    def test_demigryph_and_claws_wolf_apply_drained_on_first_wound_only(self):
        for counts,actor,dice in (({'demigryphs':1},'demigryph1',4),
                                  ({'white_wolf_claws':1},'white_wolf_claws1',3)):
            with self.subTest(actor=actor):
                result=execute(scene(axe=True,**counts),[1]*3+[10]*4+[1]*dice+[10]*3+[1])
                ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
                self.assertTrue(ack.state.enemy(actor).state.injury.conditions.has(Condition.DRAINED))
                attack,=incoming(result,actor)
                self.assertEqual(attack.proof.execution.resolution.attack.attacker_test.trace.rolled_dice,dice)
                self.assertEqual(attack.proof.request.slot_index,1)
                self.assertEqual(attack.proof.npc_help_applications,())
                self.assertEqual(result.executed_actions,2)

    def test_rending_claws_allow_give_ground_and_do_not_inherit_clamping_jaws_or_bear_grant(self):
        source=scene(white_wolf_claws=1)
        source=replace(source,facts=replace(source.facts,can_leave_zone=True))
        kernel=build_pc_melee_attack(pure_active(source,'white_wolf_claws1'))[0].kernel_request
        self.assertTrue(kernel.can_target_leave_zone)
        self.assertEqual(kernel.attack.impact_spec.damage.base,6)
        self.assertTrue(pc_npc_allows_give_ground(source.enemies[0].definition))
        self.assertFalse(pc_npc_allows_give_ground(get_pc_book_npc_entry(PcBookNpcProfile.WHITE_WOLF_CLAMPING_JAWS).definition))
        with self.assertRaises(ValueError):
            replace(source,npc_extra_attack_actor_ids=('white_wolf_claws1',))
        with self.assertRaises(ValueError):
            replace(scene(demigryphs=1),npc_extra_attack_actor_ids=('demigryph1',))

    def test_native_wound_prefix_cannot_skip_or_forge_profile_prone(self):
        result=execute(scene(centigors=1,axe=True),[1]*3+[10]*4+[1]*4+[10]*3+[1])
        ack=next(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        forged=deepcopy(ack.proof)
        object.__setattr__(forged.source,'current_wounds',True)
        with self.assertRaises((TypeError,ValueError)):
            PcMeleeStep(ack.source,forged)
        self.assertTrue(ack.source.pending)


if __name__=='__main__':
    unittest.main()
