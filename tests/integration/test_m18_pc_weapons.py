"""Mixed one-handed weapons keep native observations through process and search."""
from fractions import Fraction
from random import Random
import unittest

from tests.support.pc_weapon_scenarios import varied_weapon_source
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


class PcWeaponIntegrationTests(unittest.TestCase):
    def test_trial_observations_come_from_complete_mixed_weapon_battles(self):
        source=varied_weapon_source()
        request=PcMeleeSimulationRequest(source,42,3)
        batch=run_pc_melee_simulation(request)
        pc_ids=tuple(m.actor_id for m in source.party)
        actors=set()
        for record in batch.records:
            native=run_pc_melee_scenario(source,Random(record.seed))
            self.assertEqual(record.source_scenario,source)
            self.assertEqual(record.outcome,native.outcome)
            self.assertEqual(record.executed_actions,native.executed_actions)
            self.assertEqual(tuple(c.actor_id for c in record.glorious_spend_counts),pc_ids)
            self.assertEqual(sum(c.count for c in record.glorious_spend_counts),
                sum(len(m.fate.spends) for m in native.state.party))
            for step in native.steps:
                if isinstance(step.proof,PcAttackProof):
                    actor=step.proof.request.actor_id
                    if actor in pc_ids:
                        actors.add(actor)
        self.assertEqual(actors,set(pc_ids))
        summary=summarize_pc_melee_simulation(batch)
        self.assertEqual(summary.source_request,request)
        self.assertEqual(summary.total_action_count,sum(r.executed_actions for r in batch.records))

    def test_process_matches_sequential_with_all_new_weapons_and_fate(self):
        request=PcMeleeSimulationRequest(varied_weapon_source(),42,3)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))

    def test_count_search_keeps_each_weapon_resource_and_support_policy(self):
        source=varied_weapon_source()
        request=PcMeleeBalanceRequest(source,(
            PcMeleeCompositionGroup('minions',('minion1',),0,1),
            PcMeleeCompositionGroup('brutes',('brute1',),1,1)),source.facts,42,2,2,4,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result=evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,4)
        for candidate in result.candidates:
            actual=candidate.summary.source_request.scenario
            for member,original in zip(actual.party,source.party,strict=True):
                self.assertEqual(member.pc,original.pc)
                self.assertEqual(member.fate,original.fate)
                self.assertEqual(member.ally_recover_policy,original.ally_recover_policy)
            self.assertFalse(hasattr(candidate.summary,'records'))


if __name__=='__main__':
    unittest.main()
