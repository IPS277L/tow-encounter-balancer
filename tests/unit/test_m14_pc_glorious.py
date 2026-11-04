"""Literal dice prove PC session Fate is selected before its rerolls/outcome."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
import unittest

from tests.support.pc_melee_fixtures import make_pc_melee_scenario, make_pc_melee_party_scenario
from tests.support.pc_melee_scripted import ScriptedD10, first_wound_script
from tests.support.pc_heavy_scenarios import critical_encounter_source, critical_prefix
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendRequest
from towr.domain.pc_melee_models import PcFatePolicy, PcGloriousPolicy, PcNearMissPolicy
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcEnduranceProof, PcFateDecline, PcMeleeOutcome, PcMeleeStep,
    PcWoundCompletionProof, PcTurnEndProof, PcIncapacitatedTurnEndProof,
)
from towr.domain.test_models import Skill, TestQuality, TestRequest
from towr.engine.pc_melee_runner import run_pc_melee_scenario, apply_pc_melee_step
from towr.rules.fate_resolution import spend_fate_for_glorious


def active(source, skills=(Skill.MELEE,), maximum=0, reserve=0):
    return replace(source,party=tuple(replace(member,fate_policy=PcFatePolicy.CONFIGURED,
        glorious_policy=PcGloriousPolicy(skills,maximum,reserve)) for member in source.party))


def execute(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def spent_attacks(result):
    return tuple(step for step in result.steps
        if isinstance(step.proof,PcAttackProof) and step.proof.glorious is not None)


class PcGloriousTests(unittest.TestCase):
    def test_normal_attack_rolls_initial_pool_once_and_rerolls_all_failures(self):
        source = active(make_pc_melee_scenario(max_rounds=1))
        result = execute(source,[10,10,10,1,1,1,10,10])
        step, = spent_attacks(result)
        proof = step.proof
        test = proof.execution.resolution.attack.attacker_test
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual((test.trace.initial_values,test.trace.final_values),((10,10,10),(1,1,1)))
        self.assertEqual(tuple(r.index for r in test.trace.rerolls),(0,1,2))
        self.assertIs(test.trace.quality,TestQuality.GLORIOUS)
        self.assertIsNone(proof.fate_decline)
        self.assertEqual(proof.glorious.source_request.initial_roll.initial_values,(10,10,10))
        self.assertEqual(proof.glorious.source_request.test,proof.request.kernel_request.attack.attacker_test)
        self.assertEqual((result.state.party[0].fate.rating,result.state.party[0].fate.remaining_spends),(3,2))
        self.assertEqual(source.party[0].fate.spends,())

    def test_threshold_is_inclusive_and_does_not_spend_on_all_successes(self):
        source = active(make_pc_melee_scenario(max_rounds=1),maximum=1)
        spent = execute(source,[1,10,10,1,1,10,10])
        self.assertEqual(len(spent_attacks(spent)),1)
        declined = execute(active(source,maximum=0),[1,10,10,10,10])
        all_success = execute(active(source,maximum=99),[1,1,1,10,10])
        self.assertFalse(spent_attacks(declined))
        self.assertFalse(spent_attacks(all_success))

    def test_natural_single_die_uses_actual_skill_and_can_reroll_once(self):
        source = active(make_pc_melee_scenario(max_rounds=1))
        member = source.party[0]
        source = replace(source,party=(replace(member,pc=replace(member.pc,weapon_skill=1)),))
        result = execute(source,[10,1,10,10])
        test = spent_attacks(result)[0].proof.execution.resolution.attack.attacker_test
        self.assertEqual((test.trace.rolled_dice,test.trace.threshold),(1,5))
        self.assertEqual(tuple(r.index for r in test.trace.rerolls),(0,))
        self.assertFalse(spent_attacks(execute(source,[4,10,10])))

    def test_unselected_skill_reserve_and_exhausted_session_decline_without_extra_rng(self):
        for source in (active(make_pc_melee_scenario(max_rounds=1),skills=(Skill.ENDURANCE,)),
            active(make_pc_melee_scenario(max_rounds=1),reserve=3),
            active(make_pc_melee_scenario(max_rounds=1),reserve=4)):
            with self.subTest(policy=source.party[0].glorious_policy):
                result = execute(source,first_wound_script(1))
                self.assertEqual(result.state.party[0].fate,source.party[0].fate)
        source = active(make_pc_melee_scenario(max_rounds=1))
        member = source.party[0]
        old = member.fate
        for index in range(3):
            old = spend_fate_for_glorious(FateGloriousSpendRequest(f'old-{index}',old,
                TestRequest(f'old-test-{index}',member.pc.melee_profile))).state
        source = replace(source,party=(replace(member,fate=old),))
        result = execute(source,first_wound_script(1))
        self.assertEqual(result.state.party[0].fate,old)

    def test_protection_choice_does_not_observe_the_other_test_outcome(self):
        source = active(make_pc_melee_scenario(max_rounds=1),skills=(Skill.DEFENCE,))
        proofs = []
        for attacker in ([10,10],[1,1]):
            values = [10,10,10,1,1] + attacker + [10,10,10,1,1,1]
            # Successful 2-die NPC attack loses against all3 rerolled PC successes.
            result = execute(source,values)
            proof, = spent_attacks(result)
            self.assertEqual(proof.proof.request.actor_id,'minion1')
            proofs.append(proof.proof.glorious)
        self.assertEqual(proofs[0],proofs[1])

    def test_grim_cancellation_then_near_miss_uses_the_actual_post_spend_fate(self):
        source = active(make_pc_melee_scenario(enemy_count=2,max_rounds=1),
            skills=(Skill.DEFENCE,),maximum=1)
        source = replace(source,party=(replace(source.party[0],near_miss_policy=PcNearMissPolicy(20,0)),))
        result = execute(source,[10,10,10,1,1]
            + [1,1,1,1,1,10,10]
            + [1,1,1,1,10,10,10,10])
        step, = spent_attacks(result)
        test = step.proof.execution.resolution.attack.defender_test
        self.assertEqual(test.trace.initial_values,(1,10,10))
        self.assertEqual(test.trace.rerolls,())
        self.assertIs(test.trace.quality,TestQuality.NORMAL)
        completion = next(s.proof.completion for s in result.steps
            if isinstance(s.proof,PcWoundCompletionProof) and s.proof.completion.fate_burn is not None)
        self.assertEqual(completion.fate_burn.previous_state,step.proof.glorious.state)
        self.assertEqual((result.state.party[0].fate.rating,result.state.party[0].fate.remaining_spends),(2,1))
        self.assertEqual(tuple(w.table_total for w in result.state.party[0].injury.wounds),(10,))

    def test_wound_endurance_spend_precedes_random_drop_consequence(self):
        source = active(make_pc_melee_scenario(max_rounds=1),skills=(Skill.ENDURANCE,))
        result = execute(source,first_wound_script(4)[:11]+[10,10,10,1,10,10])
        proof = next(s.proof for s in result.steps if isinstance(s.proof,PcEnduranceProof))
        self.assertIsNotNone(proof.glorious)
        self.assertTrue(proof.test.succeeded)
        self.assertFalse(result.state.party[0].body_facts)
        self.assertIsNotNone(result.state.party[0].weapon_hand)

    def test_dropped_weapon_selects_actual_athletics_protection(self):
        source = active(make_pc_melee_scenario(enemy_count=2,max_rounds=1),skills=(Skill.ATHLETICS,))
        result = execute(source,[10,10,10,1,1]
            + [1,1,1,10,10,10,8,1]
            + [1,1,1,10,10,10,1,1,1])
        step, = spent_attacks(result)
        self.assertIs(step.proof.protection.source_request.selected_skill,Skill.ATHLETICS)
        self.assertEqual(step.proof.glorious.source_request.test.profile,source.party[0].pc.athletics_profile)
        self.assertIsNone(result.state.party[0].weapon_hand)

    def test_grim_zero_initial_successes_is_not_a_beneficial_spend(self):
        source = active(make_pc_melee_scenario(enemy_count=2,max_rounds=1),skills=(Skill.DEFENCE,))
        result = execute(source,[10,10,10,1,1]
            + [1,1,1,1,1,10,10]
            + [1,1,1,10,10,10,1,1])
        self.assertFalse(spent_attacks(result))
        proof = next(s.proof for s in result.steps
            if isinstance(s.proof,PcAttackProof) and s.proof.request.actor_id == 'minion2')
        self.assertIs(proof.execution.resolution.attack.defender_test.trace.quality,TestQuality.GRIM)
        self.assertEqual(result.state.party[0].fate,source.party[0].fate)

    def test_critical_end_phase_uses_actual_glorious_endurance(self):
        source = active(replace(critical_encounter_source(),max_rounds=2),skills=(Skill.ENDURANCE,))
        result = execute(source,critical_prefix()+[1,1,1,10,10]
            + [10,10,10,10,1,10,10,10]+[10,10,10,1,1,1]*2)
        proof = next(s.proof.critical for s in result.steps
            if isinstance(s.proof,PcTurnEndProof) and s.proof.critical is not None)
        self.assertIsNotNone(proof.glorious)
        self.assertTrue(proof.result.test.succeeded)
        self.assertFalse(result.state.party[0].injury.conditions.has(Condition.DEFENCELESS))

    def test_actionless_defenceless_critical_test_can_spend_without_an_action(self):
        source = active(critical_encounter_source(),skills=(Skill.ENDURANCE,))
        result = execute(source,critical_prefix()+[10,10,10,1,1]
            + [10]*8+[10,10,10]*3+[10]*4+[1,10,10,10]+[10,10,10]*3)
        proof = next(s.proof for s in result.steps if isinstance(s.proof,PcIncapacitatedTurnEndProof))
        self.assertIsNotNone(proof.critical.glorious)
        self.assertTrue(proof.critical.result.test.succeeded)
        self.assertFalse(result.state.party[0].injury.dead)
        self.assertEqual(len(result.state.party[0].fate.spends),2)

    def test_party_spends_only_the_current_actor_resource(self):
        for order in (('pc1','pc2'),('pc2','pc1')):
            source = active(make_pc_melee_party_scenario(pc_count=2,enemy_count=1,max_rounds=1))
            source = replace(source,pc_activation_order=order)
            result = execute(source,[10]*4+[1]*4+[10,10])
            spent,other = (result.state.participant(actor) for actor in order)
            self.assertEqual(len(spent.fate.spends),1)
            self.assertEqual(other.fate,source.participant(other.actor_id).fate)

    def test_previous_history_and_colliding_spend_id_are_preserved(self):
        source = active(make_pc_melee_scenario(max_rounds=1))
        baseline = execute(source,[10]*3+[1]*3+[10,10])
        base_id = spent_attacks(baseline)[0].proof.glorious.request_id
        member = source.party[0]
        old = spend_fate_for_glorious(FateGloriousSpendRequest(base_id,member.fate,
            TestRequest('previous-battle-test',member.pc.melee_profile))).state
        source = replace(source,party=(replace(member,fate=old),))
        result = execute(source,[10]*3+[1]*3+[10,10])
        self.assertEqual(result.state.party[0].fate.spends[:-1],old.spends)
        self.assertEqual(result.state.party[0].fate.spends[-1].id,base_id+':1')
        self.assertEqual(result.state.party[0].fate.remaining_spends,1)

    def test_forged_decline_roll_source_and_equal_nested_types_are_rejected(self):
        result = execute(active(make_pc_melee_scenario(max_rounds=1)),[10]*3+[1]*3+[10,10])
        step, = spent_attacks(result)
        for changes in ({'glorious':None}, {'fate_decline':PcFateDecline('pc',
                step.proof.glorious.source_request.test.id,'test',PcFatePolicy.CONFIGURED)}):
            with self.subTest(changes=changes),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(step.source,replace(step.proof,**changes))
        for field in ('request_id','rule_id','applied_rule_ids'):
            proof = deepcopy(step.proof)
            value = getattr(proof.glorious,field)
            text = value[0] if type(value) is tuple else value
            alias = Enum('Foreign',{'VALUE':text},type=str).VALUE
            object.__setattr__(proof.glorious,field,(alias,*value[1:]) if type(value) is tuple else alias)
            self.assertEqual(proof,step.proof)
            with self.assertRaises(TypeError):
                PcMeleeStep(step.source,proof)
        proof = deepcopy(step.proof)
        object.__setattr__(proof.glorious.source_request.initial_roll,'initial_values',(9,10,10))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,proof)
        self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)

    def test_equal_tuple_subclasses_do_not_replace_actual_reroll_trace_collections(self):
        class ForeignTuple(tuple):
            pass
        result = execute(active(make_pc_melee_scenario(max_rounds=1)),[10]*3+[1]*3+[10,10])
        step, = spent_attacks(result)
        for field in ('initial_values','final_values','rerolls','applied_rule_ids'):
            with self.subTest(field=field):
                proof = deepcopy(step.proof)
                trace = proof.execution.resolution.attack.attacker_test.trace
                object.__setattr__(trace,field,ForeignTuple(getattr(trace,field)))
                self.assertEqual(proof,step.proof)
                with self.assertRaises(TypeError):
                    PcMeleeStep(step.source,proof)


if __name__ == '__main__':
    unittest.main()
