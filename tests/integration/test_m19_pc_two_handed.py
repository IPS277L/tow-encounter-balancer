"""Two-handed source, real process trials and observed unsupported candidates."""
from copy import deepcopy
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_weapon_scenarios import two_handed_weapon_source,two_handed_stop_source
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_models import PcWeaponHand,PcTwoHandedGrip
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcTwoHandedIntegrationTests(unittest.TestCase):
    def test_actual_mixed_two_handed_trials_match_process_and_preserve_source(self):
        request=PcMeleeSimulationRequest(two_handed_weapon_source(),42,3)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))
        for record in sequential.records:
            self.assertEqual(record.source_scenario,request.scenario)
            self.assertTrue(all(m.initial_weapon_hand is PcTwoHandedGrip.BOTH for m in record.source_scenario.party))

    def test_actual_stop_observations_preserve_resolved_wound_without_counting_future_actions(self):
        request=PcMeleeSimulationRequest(two_handed_stop_source(),42,4)
        batch=run_pc_melee_simulation(request)
        observed=0
        for record in batch.records:
            native=run_pc_melee_scenario(request.scenario,Random(record.seed))
            self.assertEqual(record.outcome,native.outcome)
            self.assertEqual(record.executed_actions,native.executed_actions)
            if native.unsupported is not None:
                observed+=1
                self.assertEqual(native.unsupported.reason,'two_handed_grip_unavailable')
                self.assertFalse(native.state.pending)
                self.assertIsNone(native.state.pending_wound)
                self.assertTrue(native.state.party[0].injury.wounds[-1].effect_resolved)
                self.assertEqual(native.state.party[0].daily_wounds.wound_count,
                    len(native.state.party[0].injury.wounds))
        summary=summarize_pc_melee_simulation(batch)
        self.assertGreater(observed,0)
        self.assertEqual(summary.outcome_counts.unsupported_path,observed)

    def test_count_search_keeps_grip_and_disqualifies_observed_unsupported(self):
        source=two_handed_stop_source()
        request=PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',source.enemy_activation_order,1,2),),source.facts,42,3,2,6,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result=evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        unsupported=[]
        for candidate in result.candidates:
            member=candidate.source_request.scenario.party[0]
            self.assertEqual(member.pc,source.party[0].pc)
            self.assertIs(member.initial_weapon_hand,PcTwoHandedGrip.BOTH)
            self.assertFalse(hasattr(candidate.summary,'records'))
            if candidate.summary.outcome_counts.unsupported_path:
                unsupported.append(candidate.candidate_id)
        self.assertTrue(unsupported)
        self.assertFalse(set(unsupported)&set(result.selected_candidate_ids))

    def test_cached_single_hand_cannot_become_two_handed_observation(self):
        request=PcMeleeSimulationRequest(two_handed_weapon_source(),42,1)
        native=run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged=deepcopy(native)
        object.__setattr__(forged.steps[-1].state.party[0],'weapon_hand',PcWeaponHand.LEFT)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)


if __name__=='__main__':
    unittest.main()
