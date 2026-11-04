"""Actual fallback receipts survive independent trials/process and count search."""
from copy import deepcopy
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_weapon_scenarios import wounded_backup_weapon_source
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_result_models import (
    PcAttackProof,PcRecoverProof,PcHelpProof,PcBackupWeaponDrawProof,
)
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcBackupIntegrationTests(unittest.TestCase):
    def test_trial_observations_come_from_actual_draws_without_extra_standard_action(self):
        request=PcMeleeSimulationRequest(wounded_backup_weapon_source(),42,4)
        batch=run_pc_melee_simulation(request)
        draws=0
        for record in batch.records:
            native=run_pc_melee_scenario(request.scenario,Random(record.seed))
            actual_draws=[s for s in native.steps if isinstance(s.proof,PcBackupWeaponDrawProof)]
            draws+=len(actual_draws)
            self.assertEqual(record.source_scenario,request.scenario)
            self.assertEqual(record.outcome,native.outcome)
            self.assertEqual(record.executed_actions,sum(isinstance(s.proof,
                (PcAttackProof,PcRecoverProof,PcHelpProof)) for s in native.steps))
            self.assertEqual(record.executed_actions,native.executed_actions)
            for step in actual_draws:
                self.assertEqual(step.state.round_state,step.source.round_state)
                self.assertFalse(step.source.participant(step.proof.actor_id).using_backup_weapon)
                self.assertTrue(step.state.participant(step.proof.actor_id).using_backup_weapon)
                self.assertEqual(step.state.source,request.scenario)
        self.assertGreater(draws,0)
        summary=summarize_pc_melee_simulation(batch)
        self.assertEqual(summary.total_action_count,sum(r.executed_actions for r in batch.records))

    def test_real_process_matches_sequential_with_actual_fallbacks(self):
        request=PcMeleeSimulationRequest(wounded_backup_weapon_source(),42,4)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))

    def test_count_search_fixes_primary_backup_preference_and_fate(self):
        source=wounded_backup_weapon_source()
        request=PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',source.enemy_activation_order,2,3),),source.facts,42,3,2,6,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result=evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,6)
        for candidate in result.candidates:
            member=candidate.source_request.scenario.party[0]
            self.assertEqual(member.pc,source.party[0].pc)
            self.assertEqual(member.backup_weapon_policy,source.party[0].backup_weapon_policy)
            self.assertEqual(member.fate,source.party[0].fate)
            self.assertFalse(hasattr(candidate.summary,'records'))

    def test_cached_false_activation_after_draw_cannot_become_trial_observation(self):
        request=PcMeleeSimulationRequest(wounded_backup_weapon_source(),42,1)
        native=run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged=deepcopy(native)
        draw=next(s for s in forged.steps if isinstance(s.proof,PcBackupWeaponDrawProof))
        object.__setattr__(draw.state.party[0],'using_backup_weapon',False)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)


if __name__=='__main__':
    unittest.main()
