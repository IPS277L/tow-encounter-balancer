"""GM101/116/158–159: actual W1 Drained, ordinary turn, W2 defeat and bound replay."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.condition_models import Condition,ConditionState
from towr.domain.injury_models import ProfileInjuryState,ProfileNpcType,ProfileStateChangeRequest
from towr.domain.pc_melee_result_models import PcAttackProof,PcProfileWoundProof,PcMeleeStep,PcMeleeOutcome
from towr.domain.pc_npc_catalog import PcBookNpcProfile,get_pc_book_npc_entry
from towr.domain.pc_npc_wound_models import pc_npc_drained_profile_wound_state
from towr.engine.pc_melee_runner import run_pc_melee_scenario,apply_pc_melee_step


CASES=(('empire_knights','empire_knight',4,4,4),
       ('wolf_knights','wolf_knight',4,4,5),('big_uns','big_un',3,3,5))


def scene(keyword,*,pcs=1,enemies=1):
    return book_pc_scenario(**{keyword:enemies},footpads=0,townsfolk=0,pc_count=pcs,max_rounds=1)


def execute(source,values):
    rng=ScriptedD10(values)
    result=run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


class PcBruteWoundTests(unittest.TestCase):
    def test_first_wound_ack_adds_drained_then_actual_own_turn_filters_only_wounded_bonus(self):
        for keyword,prefix,pdice,adice,damage in CASES:
            with self.subTest(profile=keyword):
                source=scene(keyword,enemies=2)
                result=execute(source,[1]*3+[10]*pdice+[10]*adice+[1]*3
                    +[10]*(adice+1)+[1]*3)
                ack,=tuple(step for step in result.steps if type(step.proof) is PcProfileWoundProof)
                self.assertFalse(ack.source.enemy(prefix+'1').state.injury.conditions.has(Condition.DRAINED))
                self.assertEqual(ack.state.enemy(prefix+'1').state.injury.conditions.conditions,
                    frozenset({Condition.DRAINED}))
                self.assertEqual(ack.state.enemy(prefix+'1').state.injury.wounds,1)
                self.assertFalse(ack.state.enemy(prefix+'2').state.injury.conditions.has(Condition.DRAINED))
                incoming=tuple(step.proof for step in result.steps if type(step.proof) is PcAttackProof
                    and step.proof.request.actor_id.startswith(prefix))
                self.assertEqual(tuple(p.request.actor_id for p in incoming),(prefix+'1',prefix+'2'))
                self.assertEqual(tuple(p.execution.resolution.attack.attacker_test.trace.rolled_dice
                    for p in incoming),(adice,adice+1))
                self.assertEqual(tuple(p.execution.resolution.attack.impact_spec.damage.base
                    for p in incoming),(damage,damage))
                self.assertTrue(all(not p.request.kernel_request.attack.secondary_effects for p in incoming))
                self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)
                self.assertIsNone(result.unsupported)
                self.assertEqual(result.exited_npc_ids,())

    def test_second_wound_defeats_before_npc_turn_with_actual_disposition(self):
        for keyword,prefix,pdice,*_ in CASES:
            with self.subTest(profile=keyword):
                result=execute(scene(keyword,pcs=2),([1]*4+[10]*pdice)*2)
                acks=tuple(step for step in result.steps if type(step.proof) is PcProfileWoundProof)
                self.assertEqual(tuple((s.proof.source.previous_wounds,s.proof.source.current_wounds,
                    s.proof.source.defeated) for s in acks),((0,1,False),(1,2,True)))
                self.assertIsNone(acks[0].proof.decision)
                self.assertIsNotNone(acks[1].proof.decision)
                self.assertTrue(acks[0].state.enemy(prefix+'1').state.injury.conditions.has(Condition.DRAINED))
                self.assertTrue(result.state.enemy(prefix+'1').state.injury.defeated)
                self.assertFalse(any(type(s.proof) is PcAttackProof and
                    s.proof.request.actor_id==prefix+'1' for s in result.steps))
                self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)

    def test_repeated_stagger_wound_also_uses_same_first_wound_band(self):
        for keyword,prefix,pdice,adice,_ in CASES:
            with self.subTest(profile=keyword):
                # Staff Damage5 equals Resilience5: two independent Staggers make W1.
                result=execute(scene(keyword,pcs=2),([1,1,10,10]+[10]*pdice)*2
                    +[10]*adice+[1]*3)
                ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
                injury=ack.state.enemy(prefix+'1').state.injury
                self.assertEqual((injury.wounds,injury.defeated,injury.conditions.conditions),
                    (1,False,frozenset({Condition.DRAINED})))
                self.assertIsNone(result.unsupported)

    def test_first_wound_helper_preserves_other_conditions_and_does_not_reapply_later_band(self):
        for profile in (PcBookNpcProfile.EMPIRE_KNIGHT_LANCE,
                PcBookNpcProfile.KNIGHT_WHITE_WOLF_HAMMER,PcBookNpcProfile.BIG_UN_CHOPPAS):
            definition=get_pc_book_npc_entry(profile).definition
            injury=ProfileInjuryState(1,2,ConditionState(frozenset({Condition.PRONE})))
            change=ProfileStateChangeRequest(ProfileNpcType.BRUTE,0,1,False)
            actual=pc_npc_drained_profile_wound_state(definition,injury,change)
            self.assertEqual(actual.conditions.conditions,frozenset({Condition.PRONE,Condition.DRAINED}))
            later=replace(injury,wounds=2,defeated=True)
            self.assertIs(pc_npc_drained_profile_wound_state(definition,later,
                replace(change,previous_wounds=1,current_wounds=2,defeated=True)),later)
            for value in (True,1):
                wrong=replace(change,previous_wounds=value)
                self.assertIs(pc_npc_drained_profile_wound_state(definition,injury,wrong),injury)
        unrelated=get_pc_book_npc_entry(PcBookNpcProfile.EMPIRE_OFFICIAL_DAGGER).definition
        self.assertIs(pc_npc_drained_profile_wound_state(unrelated,injury,change),injury)

    def test_ack_receipt_replay_and_cached_missing_drained_are_rejected(self):
        result=execute(scene('empire_knights'),[1]*3+[10]*4+[10]*4+[1]*3)
        ack,=tuple(s for s in result.steps if type(s.proof) is PcProfileWoundProof)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(ack.state,ack)
        for field,value in (('previous_wounds',1),('current_wounds',2),('npc_type','brute')):
            with self.subTest(field=field),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(ack.source,replace(ack.proof,source=replace(ack.proof.source,**{field:value})))
        forged=deepcopy(result)
        step=next(s for s in forged.steps if type(s.proof) is PcProfileWoundProof)
        enemy=step.state.enemy('empire_knight1')
        object.__setattr__(step.state,'enemies',(replace(enemy,state=replace(enemy.state,
            injury=replace(enemy.state.injury,conditions=ConditionState()))),))
        with self.assertRaises(ValueError):
            replace(forged)


if __name__=='__main__':
    unittest.main()
