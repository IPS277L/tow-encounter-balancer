"""Official's resolved profile Wound remains distinct from a future unresolved Broken turn."""
from copy import deepcopy
from dataclasses import replace
from enum import Enum
from fractions import Fraction
import json
from random import Random
import unittest
from unittest.mock import patch

from tests.support.pc_book_npc_scenarios import book_pc_scenario
from tests.unit.test_m9_pc_melee_json import document
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request,encode_pc_melee_simulation_result
from towr.application.pc_melee_balance import evaluate_pc_melee_balance
from towr.application.pc_melee_balance_models import PcMeleeBalanceRequest,PcMeleeCompositionGroup
from towr.balance.ranged_assessment_models import ObjectiveRateWindow
from towr.domain.condition_models import Condition
from towr.domain.pc_melee_result_models import PcMeleeOutcome,PcProfileWoundProof
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.domain.pc_npc_wound_models import PcNpcBrokenTurnUnsupported
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def source(*,officials=1,footpads=0):
    return book_pc_scenario(officials=officials,footpads=footpads,townsfolk=0,max_rounds=3)


class PcOfficialIntegrationTests(unittest.TestCase):
    def test_actual_trials_and_process_keep_broken_turn_stops_separate_from_second_wound_defeat(self):
        request=PcMeleeSimulationRequest(source(),42,4)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        stops=victories=0
        for record in sequential.records:
            native=run_pc_melee_scenario(request.scenario,Random(record.seed))
            self.assertEqual(record.outcome,native.outcome)
            self.assertEqual(record.executed_actions,native.executed_actions)
            if isinstance(native.unsupported,PcNpcBrokenTurnUnsupported):
                stops+=1
                cause=native.unsupported
                injury=native.state.enemy(cause.actor_id).state.injury
                self.assertEqual(injury.wounds,1)
                self.assertFalse(injury.defeated)
                self.assertTrue(injury.conditions.has(Condition.BROKEN))
                self.assertFalse(native.state.pending)
                self.assertIsNone(native.state.pending_wound)
                self.assertIsNone(native.state.round_state.active_turn)
                self.assertEqual(cause.profile_change.current_wounds,1)
                self.assertTrue(any(isinstance(s.proof,PcProfileWoundProof)
                    and s.proof.source==cause.profile_change for s in native.steps))
            elif native.outcome is PcMeleeOutcome.OBJECTIVE_ACHIEVED:
                victories+=1
                self.assertTrue(native.state.enemy('official1').state.injury.defeated)
        self.assertGreater(stops,0)
        self.assertGreater(victories,0)
        summary=summarize_pc_melee_simulation(sequential)
        self.assertEqual(summary.outcome_counts.unsupported_path,stops)
        self.assertEqual(summary.outcome_counts.objective_achieved,victories)
        self.assertEqual(summarize_pc_melee_simulation(process),summary)

    def test_actual_summary_json_preserves_full_brute_definition_with_existing_schema(self):
        raw=document()
        raw['scenario']=scenario_document(source())
        command=parse_pc_melee_simulation_request(json.dumps(raw))
        summary=summarize_pc_melee_simulation(run_pc_melee_simulation(command.request))
        encoded=json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(encoded['request'],raw)
        definition=encoded['request']['scenario']['enemies'][0]['definition']
        self.assertEqual((definition['injury_policy'],definition['wound_limit']),('brute',2))
        self.assertEqual(definition['protection']['test_profile'],{'dice':3,'threshold':3,'pool_cap':None})

    def test_count_search_preserves_book_bands_and_disqualifies_observed_unsupported(self):
        scenario=source(officials=2,footpads=1)
        request=PcMeleeBalanceRequest(scenario,(
            PcMeleeCompositionGroup('officials',('official1','official2'),1,2),
            PcMeleeCompositionGroup('footpads',('footpad1',),0,1)),scenario.facts,42,2,4,8,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result=evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,8)
        unsupported=[]
        for candidate in result.candidates:
            for member,original in zip(candidate.source_request.scenario.party,scenario.party,strict=True):
                self.assertEqual(replace(member,target_priority=original.target_priority,
                    defeat_decisions=original.defeat_decisions),original)
            for enemy in candidate.source_request.scenario.enemies:
                validate_pc_book_npc_definition(enemy.definition)
            if candidate.summary.outcome_counts.unsupported_path:
                unsupported.append(candidate.candidate_id)
            self.assertFalse(hasattr(candidate.summary,'records'))
        self.assertTrue(unsupported)
        self.assertFalse(set(unsupported)&set(result.selected_candidate_ids))

    def test_cached_equal_actor_alias_in_new_stop_cannot_become_an_observation(self):
        request=PcMeleeSimulationRequest(source(),42,2)
        native=run_pc_melee_scenario(request.scenario,Random(request.seed_for(1)))
        self.assertIsInstance(native.unsupported,PcNpcBrokenTurnUnsupported)
        forged=deepcopy(native)
        object.__setattr__(forged.unsupported,'actor_id',
            Enum('OtherActor',{'OFFICIAL':'official1'},type=str).OFFICIAL)
        self.assertEqual(forged,native)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,1)


if __name__=='__main__':
    unittest.main()
