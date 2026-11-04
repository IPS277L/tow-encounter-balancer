"""Real allied condition changes remain exact through trials/process/search."""
from copy import deepcopy
from enum import Enum
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_ally_recover_scenarios import active_ally_recover_source
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_result_models import PcRecoverProof,PcMeleeScenarioResult
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcAllyRecoverIntegrationTests(unittest.TestCase):
    def test_trial_observations_count_actual_nonself_changes_once_and_preserve_other_resources(self):
        source=active_ally_recover_source()
        request=PcMeleeSimulationRequest(source,42,4)
        batch=run_pc_melee_simulation(request)
        actual_ally_actions=0
        for record in batch.records:
            native=run_pc_melee_scenario(source,Random(record.seed))
            counts={member.actor_id:0 for member in source.party}
            for step in native.steps:
                proof=step.proof
                if not isinstance(proof,PcRecoverProof):
                    continue
                actor=proof.result.source_request.actor_id
                changes=proof.result.resolution.condition_changes
                allied=[change for change in changes if change.entity_id!=actor]
                counts[actor]+=bool(allied)
                actual_ally_actions+=bool(allied)
                for change in allied:
                    self.assertEqual(change.entity_id,source.participant(actor).ally_recover_policy.beneficiary_id)
                    old,new=step.source.participant(change.entity_id),step.state.participant(change.entity_id)
                    self.assertEqual(old.injury.conditions,change.previous_conditions)
                    for condition in change.removed_conditions:
                        self.assertFalse(new.injury.conditions.has(condition))
                    self.assertEqual(new.injury.wounds,old.injury.wounds)
                    self.assertEqual(new.daily_wounds,old.daily_wounds)
                    self.assertEqual(new.fate,old.fate)
                    self.assertEqual(new.weapon_hand,old.weapon_hand)
            self.assertEqual(tuple(count.count for count in record.ally_recover_action_counts),
                tuple(counts[member.actor_id] for member in source.party))
        summary=summarize_pc_melee_simulation(batch)
        self.assertGreater(actual_ally_actions,0)
        self.assertEqual(summary.total_ally_recover_action_count,actual_ally_actions)
        self.assertEqual(summary.ally_recover_action_counts[1].count,0)
        self.assertTrue(all(not member.fate.spends and not member.fate.burns for member in source.party))

    def test_real_process_matches_sequential_recover_and_fate_observations(self):
        request=PcMeleeSimulationRequest(active_ally_recover_source(),42,4)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        summary=summarize_pc_melee_simulation(sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summary)
        self.assertGreater(summary.total_ally_recover_action_count,0)

    def test_cached_equal_but_untyped_target_cannot_become_an_ally_action_count(self):
        request=PcMeleeSimulationRequest(active_ally_recover_source(),42,4)
        native=None
        for index in range(4):
            candidate=run_pc_melee_scenario(request.scenario,Random(request.seed_for(index)))
            if any(isinstance(step.proof,PcRecoverProof) and any(
                change.entity_id!=step.proof.result.source_request.actor_id
                for change in step.proof.result.resolution.condition_changes)
                for step in candidate.steps):
                native=candidate
                break
        self.assertIsNotNone(native)
        forged=deepcopy(native)
        proof=next(step.proof for step in forged.steps if isinstance(step.proof,PcRecoverProof)
            and any(change.entity_id!=step.proof.result.source_request.actor_id
                for change in step.proof.result.resolution.condition_changes))
        change=next(change for change in proof.result.resolution.condition_changes
            if change.entity_id!=proof.result.source_request.actor_id)
        object.__setattr__(change,'entity_id',Enum('ForeignString',{'VALUE':change.entity_id},type=str).VALUE)
        self.assertEqual(forged,native)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)

    def test_result_subclass_cannot_override_actions_after_valid_journal_admission(self):
        request=PcMeleeSimulationRequest(active_ally_recover_source(),42,1)
        native=run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        class AliasResult(PcMeleeScenarioResult):
            @property
            def executed_actions(self):
                return super().executed_actions-1
        forged=AliasResult(native.source,native.steps,native.outcome,native.unsupported)
        self.assertEqual(forged.executed_actions,native.executed_actions-1)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises(TypeError):
                run_pc_melee_trial(request,0)

    def test_count_search_keeps_role_and_beneficiary_without_retaining_battle_owner(self):
        source=active_ally_recover_source()
        request=PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,4,2,8,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result=evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,8)
        for candidate in result.candidates:
            actual=candidate.summary.source_request.scenario
            self.assertEqual(actual.party[0].policy,source.party[0].policy)
            self.assertEqual(actual.party[0].ally_recover_policy,source.party[0].ally_recover_policy)
            self.assertEqual(tuple(m.fate for m in actual.party),tuple(m.fate for m in source.party))
            self.assertFalse(hasattr(candidate.summary,'records'))
        self.assertTrue(any(candidate.summary.total_ally_recover_action_count for candidate in result.candidates))


if __name__=='__main__':
    unittest.main()
