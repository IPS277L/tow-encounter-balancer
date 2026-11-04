"""Brigand ability receipts survive full source codecs, process trials and count search."""
from copy import deepcopy
from dataclasses import replace
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
from towr.domain.pc_melee_result_models import PcAttackProof
from towr.domain.pc_npc_ability_models import CRAVEN_OPPORTUNIST_RULE_ID
from towr.domain.pc_npc_catalog import validate_pc_book_npc_definition
from towr.engine.pc_melee_runner import run_pc_melee_scenario
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation,run_pc_melee_trial
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def source():
    return book_pc_scenario(brigands=2,footpads=1,townsfolk=0,pc_count=1,max_rounds=3)


class PcBrigandIntegrationTests(unittest.TestCase):
    def test_actual_ability_trials_match_process_and_keep_source_bound_observations(self):
        request=PcMeleeSimulationRequest(source(),42,3)
        sequential=run_pc_melee_simulation(request)
        process=run_pc_melee_simulation_parallel(request,workers=2,batch_size=1)
        self.assertEqual(process,sequential)
        observed=0
        for record in sequential.records:
            native=run_pc_melee_scenario(request.scenario,Random(record.seed))
            self.assertEqual(record.outcome,native.outcome)
            self.assertEqual(record.executed_actions,native.executed_actions)
            for step in native.steps:
                if not isinstance(step.proof,PcAttackProof):
                    continue
                for modifier in step.proof.request.kernel_request.attack.attacker_test.dice_modifiers:
                    if modifier.rule_id==CRAVEN_OPPORTUNIST_RULE_ID:
                        observed+=1
                        self.assertEqual(modifier.amount,2)
                        validate_pc_book_npc_definition(step.source.enemy(step.proof.request.actor_id).definition)
        self.assertGreater(observed,0)
        self.assertEqual(summarize_pc_melee_simulation(process),summarize_pc_melee_simulation(sequential))

    def test_actual_summary_json_preserves_exact_brigand_loadout_without_new_wire_fields(self):
        raw=document()
        raw['scenario']=scenario_document(source())
        command=parse_pc_melee_simulation_request(json.dumps(raw))
        summary=summarize_pc_melee_simulation(run_pc_melee_simulation(command.request))
        encoded=json.loads(encode_pc_melee_simulation_result(command,summary))
        self.assertEqual(encoded['request'],raw)
        self.assertEqual(encoded['request']['scenario']['enemies'][0]['definition']['attack']['id'],'axe')
        self.assertEqual(encoded['request']['scenario']['enemies'][0]['definition']['resilience'],{'toughness':3,'bonus':1})

    def test_count_search_fixes_canonical_definitions_and_existing_party_policies(self):
        scenario=source()
        request=PcMeleeBalanceRequest(scenario,(
            PcMeleeCompositionGroup('brigands',('brigand1','brigand2'),1,2),
            PcMeleeCompositionGroup('footpads',('footpad1',),1,1)),scenario.facts,42,2,2,4,
            ObjectiveRateWindow(Fraction(0),Fraction(1,2),Fraction(1)),2)
        result=evaluate_pc_melee_balance(request,
            lambda trial:summarize_pc_melee_simulation(run_pc_melee_simulation(trial)))
        self.assertEqual(result.total_trials,4)
        for candidate in result.candidates:
            for member,original in zip(candidate.source_request.scenario.party,scenario.party,strict=True):
                self.assertEqual(replace(member,target_priority=original.target_priority,
                    defeat_decisions=original.defeat_decisions),original)
            for enemy in candidate.source_request.scenario.enemies:
                validate_pc_book_npc_definition(enemy.definition)
            self.assertFalse(hasattr(candidate.summary,'records'))

    def test_cached_extra_bonus_cannot_become_trial_observation(self):
        request=PcMeleeSimulationRequest(source(),42,1)
        native=run_pc_melee_scenario(request.scenario,Random(request.seed_for(0)))
        forged=deepcopy(native)
        target=next(step for step in forged.steps if isinstance(step.proof,PcAttackProof)
            and any(modifier.rule_id==CRAVEN_OPPORTUNIST_RULE_ID
                for modifier in step.proof.request.kernel_request.attack.attacker_test.dice_modifiers))
        modifier=next(modifier for modifier in target.proof.request.kernel_request.attack.attacker_test.dice_modifiers
            if modifier.rule_id==CRAVEN_OPPORTUNIST_RULE_ID)
        object.__setattr__(modifier,'amount',3)
        with patch('towr.simulation.pc_melee_simulation.run_pc_melee_scenario',return_value=forged):
            with self.assertRaises((TypeError,ValueError)):
                run_pc_melee_trial(request,0)


if __name__=='__main__':
    unittest.main()
