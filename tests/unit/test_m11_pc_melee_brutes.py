"""Canonical static Brute Wounds in the shared PC-party owner."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.support.pc_melee_fixtures import (
    make_pc_melee_mixed_scenario, make_pc_melee_scenario,
    replace_pc_melee_member, with_pc_melee_brute,
)
from tests.support.pc_melee_scripted import ScriptedD10
from towr.domain.attack_models import ImpactOutcome
from towr.domain.condition_models import Condition
from towr.domain.injury_models import ProfileInjuryState, ProfileNpcType
from towr.domain.pc_melee_models import validate_pc_melee_scenario_admission
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcMeleeOutcome, PcMeleeStep, PcProfileWoundProof, PcWoundCompletionProof,
)
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.engine.pc_melee_runner import apply_pc_melee_step, run_pc_melee_scenario


def duel_source(*, max_rounds=2):
    return make_pc_melee_mixed_scenario(pc_count=1,minion_count=0,brute_count=1,
        brute_wound_limit=2,max_rounds=max_rounds)


def run_script(source, values):
    rng = ScriptedD10(values)
    result = run_pc_melee_scenario(source,rng)
    rng.assert_exhausted()
    return result


def wounded_then_defeated():
    # PC Wounds; surviving Brute attacks and misses; PC Wounds again.
    return run_script(duel_source(),[1,1,1,10,10, 10,10,1,1,1, 1,1,1,10,10])


class PcMeleeBruteTests(unittest.TestCase):
    def test_nonterminal_wound_is_acknowledged_without_defeat_then_brute_attacks(self):
        result = wounded_then_defeated()
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(result.executed_actions,3)
        changes = [step for step in result.steps if isinstance(step.proof,PcProfileWoundProof)]
        first,last = changes
        self.assertEqual((first.proof.source.npc_type,first.proof.source.previous_wounds,
            first.proof.source.current_wounds,first.proof.source.defeated),
            (ProfileNpcType.BRUTE,0,1,False))
        self.assertIsNone(first.proof.decision)
        self.assertFalse(first.state.enemy('brute1').state.injury.defeated)
        self.assertNotIn('brute1',first.state.round_state.excluded_turn_entity_ids)
        attacks = [step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)]
        self.assertEqual([proof.request.actor_id for proof in attacks],['pc1','brute1','pc1'])
        self.assertEqual(attacks[1].request.kernel_request.target_policy,TargetInjuryPolicy.PLAYER)
        self.assertEqual((last.proof.source.previous_wounds,last.proof.source.current_wounds,last.proof.source.defeated),(1,2,True))
        self.assertEqual(last.proof.decision,result.source.participant('pc1').defeat_decision('brute1'))
        self.assertIn('brute1',last.state.round_state.excluded_turn_entity_ids)
        self.assertEqual(result.state.enemy('brute1').state.injury.wounds,2)
        self.assertEqual(result.state.participant('pc1').daily_wounds.wound_count,0)
        self.assertFalse(any(isinstance(step.proof,PcWoundCompletionProof) for step in result.steps))

    def test_mixed_reserve_retains_wounded_brute_then_retargets_after_exact_final_wound(self):
        source = make_pc_melee_mixed_scenario(brute_wound_limit=2,max_rounds=2)
        party = tuple(replace(member,target_priority=('brute1','minion1'),
            defeat_decisions=(member.defeat_decision('brute1'),member.defeat_decision('minion1')))
            for member in source.party)
        source = replace(source,party=party)
        result = run_script(source,[1,1,1,10,10]*2 + [10,10,1,1,1] + [1,1,1,1,10,10])
        attacks = [step.proof for step in result.steps if isinstance(step.proof,PcAttackProof)]
        self.assertEqual([(p.request.actor_id,p.request.target_id) for p in attacks],
            [('pc1','brute1'),('pc2','brute1'),('minion1','pc1'),('pc1','minion1')])
        self.assertEqual(attacks[-1].execution.resolution.attack.attacker_test.trace.rolled_dice,4)
        self.assertIs(result.outcome,PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        self.assertEqual(tuple(enemy.state.injury.wounds for enemy in result.state.enemies),(1,2))

    def test_repeated_staggered_wounds_live_brute_and_clears_its_condition(self):
        source = duel_source()
        member = source.party[0]
        source = replace_pc_melee_member(source,'pc1',pc=replace(member.pc,strength=1))
        # The weak tied hits first Stagger and then inflict a Wound. No Wounds
        # Table roll is made for the Brute; its own misses use the same stream.
        values = [1,10,10,1,10, 10,10,1,1,1]*2
        result = run_script(source,values)
        attacks = [step for step in result.steps if isinstance(step.proof,PcAttackProof)]
        self.assertIs(attacks[0].proof.execution.resolution.attack.impact,ImpactOutcome.STAGGERED)
        self.assertIs(attacks[2].proof.execution.resolution.attack.impact,ImpactOutcome.STAGGERED)
        wounded = next(step for step in result.steps if isinstance(step.proof,PcProfileWoundProof))
        injury = wounded.state.enemy('brute1').state.injury
        self.assertEqual(injury.wounds,1)
        self.assertFalse(injury.defeated)
        self.assertFalse(injury.conditions.has(Condition.STAGGERED))
        self.assertIs(result.outcome,PcMeleeOutcome.ROUND_LIMIT)

    def test_pc_wound_uses_player_lifecycle_while_brute_wound_does_not(self):
        result = run_script(duel_source(),[1,1,1,10,10, 1,1,10,10,10,6, 1,1,1,10,10])
        completions = [step for step in result.steps if isinstance(step.proof,PcWoundCompletionProof)]
        self.assertEqual(len(completions),1)
        self.assertEqual(completions[0].proof.fate_decline.actor_id,'pc1')
        self.assertEqual(result.state.participant('pc1').daily_wounds.wound_count,1)
        self.assertEqual(result.state.participant('pc1').fate,result.source.participant('pc1').fate)
        self.assertEqual(result.state.enemy('brute1').state.injury.wounds,2)

    def test_wound_acknowledgement_is_source_bound_once_and_cannot_skip_pending_work(self):
        result = wounded_then_defeated()
        index = next(i for i,step in enumerate(result.steps) if isinstance(step.proof,PcProfileWoundProof))
        step = result.steps[index]
        self.assertEqual(apply_pc_melee_step(step.source,step),step.state)
        with self.assertRaises(ValueError):
            apply_pc_melee_step(step.state,step)
        with self.assertRaises(ValueError):
            replace(result,steps=(*result.steps[:index],*result.steps[index+1:]))
        foreign = replace(step.proof,source=replace(step.proof.source,current_wounds=2))
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,foreign)
        with self.assertRaises(ValueError):
            PcMeleeStep(step.source,replace(step.proof,decision=result.source.participant('pc1').defeat_decision('brute1')))
        last = [item for item in result.steps if isinstance(item.proof,PcProfileWoundProof)][-1]
        with self.assertRaises(TypeError):
            PcMeleeStep(last.source,replace(last.proof,decision=None))

    def test_profile_result_cannot_change_npc_type_wound_count_limit_or_defeat(self):
        result = wounded_then_defeated()
        step = next(item for item in result.steps if isinstance(item.proof,PcAttackProof))
        changes = (
            lambda result: object.__setattr__(result.profile_wound.state_change,'npc_type',ProfileNpcType.MINION),
            lambda result: object.__setattr__(result.profile_wound,'wounds_requested',2),
            lambda result: object.__setattr__(result.profile_wound,'wounds_inflicted',True),
            lambda result: object.__setattr__(result.profile_wound.state_change,'defeated',0),
            lambda result: object.__setattr__(result.profile_wound.state,'wound_limit',3),
            lambda result: object.__setattr__(result.profile_wound.state,'defeated',0),
        )
        for change in changes:
            proof = deepcopy(step.proof)
            change(proof.execution.resolution)
            with self.subTest(change=change),self.assertRaises((TypeError,ValueError)):
                PcMeleeStep(step.source,proof)
        ack = next(item for item in result.steps if isinstance(item.proof,PcProfileWoundProof))
        proof = deepcopy(ack.proof)
        object.__setattr__(proof.source,'npc_type','brute')
        with self.assertRaises(TypeError):
            PcMeleeStep(ack.source,proof)

    def test_brute_admission_checks_exact_policy_limit_and_matching_fresh_snapshot_before_rng(self):
        source = duel_source()
        class NoRandom:
            def randint(self,*_):
                raise AssertionError('malformed source consumed RNG')
        corruptions = (
            lambda value: object.__setattr__(value.enemies[0].definition,'injury_policy','brute'),
            lambda value: object.__setattr__(value.enemies[0].definition,'wound_limit',True),
            lambda value: object.__setattr__(value.enemies[0].state.injury,'wound_limit',True),
            lambda value: object.__setattr__(value.enemies[0].definition,'injury_policy',TargetInjuryPolicy.CHAMPION),
            lambda value: object.__setattr__(value.enemies[0].definition,'injury_policy',TargetInjuryPolicy.MONSTROSITY),
            lambda value: object.__setattr__(value.enemies[0].state,'injury',ProfileInjuryState(0,3)),
            lambda value: object.__setattr__(value.enemies[0].state,'injury',ProfileInjuryState(1,2)),
        )
        for mutate in corruptions:
            forged = deepcopy(source)
            mutate(forged)
            with self.subTest(mutate=mutate),self.assertRaises((TypeError,ValueError)):
                run_pc_melee_scenario(forged,NoRandom())
        validate_pc_melee_scenario_admission(source)
        with self.assertRaises(ValueError):
            with_pc_melee_brute(make_pc_melee_scenario(),'minion1',wound_limit=0)


if __name__ == '__main__':
    unittest.main()
