"""Actual public source, compact observations and JSON1, with literal dice."""
from copy import deepcopy
from dataclasses import replace
import json
from unittest import TestCase, main

from jsonschema.exceptions import ValidationError

from tests.integration.test_companion_departure_native import mounted_rider_defeat_source
from tests.integration.test_immediate_attack_counts_json import command
from tests.support.pc_melee_scripted import ScriptedD10
from towr.adapters.pc_melee_json import encode_pc_melee_simulation_result
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document
from towr.domain import talent_actor_models
from towr.domain.talent_catalog import TalentId
from towr.simulation.pc_companion_statistics import PcCompanionCount
from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def literal_factory(seed):
    """Picklable deterministic RNG factory for the actual spawn boundary."""
    return ScriptedD10([1]*5+[10]*4)


class CompanionCountJsonTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request=PcMeleeSimulationRequest(mounted_rider_defeat_source(),42,2)
        cls.batch=run_pc_melee_simulation(cls.request,rng_factory=literal_factory)
        cls.summary=summarize_pc_melee_simulation(cls.batch)

    def test_actual_process_trials_preserve_public_talent_admission_and_body_observations(self):
        from towr.simulation.pc_melee_parallel import run_pc_melee_simulation_parallel
        self.assertIn(TalentId.BACK_IN_THE_SADDLE,talent_actor_models.PC_EXECUTABLE_TALENTS)
        self.assertIn(TalentId.BACK_IN_THE_SADDLE,talent_actor_models.NPC_EXECUTABLE_TALENTS)
        self.assertIn(TalentId.BACK_IN_THE_SADDLE,talent_actor_models.GENERATED_TALENT_POOL)
        parallel=run_pc_melee_simulation_parallel(self.request,workers=2,batch_size=1,rng_factory=literal_factory)
        self.assertEqual(parallel,self.batch)
        self.assertEqual(summarize_pc_melee_simulation(parallel),self.summary)

    def test_actual_departures_stay_separate_from_original_npc_defeats_actions_and_hp(self):
        for record in self.batch.records:
            self.assertEqual(record.executed_actions,1)
            self.assertEqual(record.companion_counts,(PcCompanionCount('minion1:mount','minion1',departures=1),))
            self.assertEqual(sum(row.count for row in record.npc_recover_action_counts),0)
        self.assertEqual(self.summary.total_action_count,2)
        self.assertEqual(self.summary.companion_counts,(PcCompanionCount('minion1:mount','minion1',departures=2),))
        self.assertEqual(self.summary.companion_counts[0].defeats,0)
        with self.assertRaises((TypeError,ValueError)): replace(self.summary,companion_counts=None)
        with self.assertRaises(ValueError): replace(self.batch.records[0],companion_counts=(
            replace(self.batch.records[0].companion_counts[0],eligible_turns=0,started_turns=1),))

    def test_current_simulation_json_requires_source_bound_counter_rows_and_no_body_fate(self):
        document=json.loads(encode_pc_melee_simulation_result(command(self.request),self.summary))
        counts=document['summary']['companion_counts']
        self.assertEqual(counts[0]['departures'],2)
        self.assertEqual(counts[0]['rider_id'],'minion1')
        self.assertNotIn('fate',counts[0])
        validate_pc_melee_simulation_document(document,'result')
        for change in ('missing','foreign_field','bool_count','empty'):
            bad=deepcopy(document)
            if change=='missing': del bad['summary']['companion_counts']
            elif change=='foreign_field': bad['summary']['companion_counts'][0]['fate']=1
            elif change=='bool_count': bad['summary']['companion_counts'][0]['departures']=True
            else: bad['summary']['companion_counts']=[]
            with self.subTest(change=change), self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(bad,'result')

    def test_public_dynamic_candidate_keeps_zero_rows_for_an_ordinary_generated_mount(self):
        from random import Random
        from tests.integration.test_generated_talents_json import talent_request
        from towr.adapters.dynamic_encounter_json import _validator, candidate_document, parse_dynamic_encounter_request
        from towr.application.dynamic_encounter import GeneratedCandidate
        raw=talent_request()
        raw['search_space'].update(mount=['horse'],allowed_talents=[])
        parsed=parse_dynamic_encounter_request(json.dumps(raw))
        npc=parsed.request.space.sample(Random(0))
        self.assertTrue(parsed.request.space.contains(npc))
        scenario=parsed.request.scenario((npc,),'companion:dynamic-counts')
        batch=run_pc_melee_simulation(PcMeleeSimulationRequest(scenario,42,1))
        candidate=GeneratedCandidate((npc,),summarize_pc_melee_simulation(batch))
        document=json.loads(json.dumps(candidate_document(parsed.request,candidate)))
        validator=_validator('result').evolve(schema={'$ref':'urn:towr:dynamic-encounter:common:1#/$defs/candidate'})
        validator.validate(document)
        self.assertEqual(document['companion_counts'][0]['actor_id'],'generated-npc:1:mount')
        self.assertEqual(document['companion_counts'][0]['started_turns'],0)
        self.assertEqual(document['companion_counts'][0]['defeats'],0)
        bad=deepcopy(document); del bad['companion_counts']
        with self.assertRaises(ValidationError): validator.validate(bad)

    def test_balance_summary_preserves_its_actual_companion_counter_source(self):
        from towr.adapters._pc_melee_scenario_json import scenario_document
        from towr.adapters.pc_melee_json import encode_pc_melee_balance_result, parse_pc_melee_balance_request
        from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document
        from towr.application.pc_melee_balance_models import PcMeleeBalanceResult, PcMeleeCandidateResult, project_pc_melee_candidate
        from towr.balance.pc_melee_assessment import PcMeleeCandidateAssessment
        template=scenario_document(self.request.scenario)
        raw=dict(schema_version='1',kind='pc_melee_balance',request_id='companion:balance-counts',
            ruleset='towr-pg1.4-gmg1.1',template=template,
            generation=dict(groups=[dict(group_id='rider',actor_ids=['minion1'],minimum_count=1,maximum_count=1)],
                facts=template['facts'],max_candidates=1),
            evaluation=dict(master_seed='42',trials_per_candidate=1,max_total_trials=1,top_k=1,
                window=dict(minimum=dict(numerator=0,denominator=1),target=dict(numerator=1,denominator=2),
                    maximum=dict(numerator=1,denominator=1))),execution=dict(mode='sequential'))
        parsed=parse_pc_melee_balance_request(json.dumps(raw))
        request=project_pc_melee_candidate(parsed.request,(1,))
        batch=run_pc_melee_simulation(request,rng_factory=lambda seed:ScriptedD10([1]*5+[10]*4))
        summary=summarize_pc_melee_simulation(batch)
        candidate=PcMeleeCandidateResult(request.scenario.id,(1,),request,summary,
            PcMeleeCandidateAssessment(request,summary,parsed.request.window))
        report=PcMeleeBalanceResult(parsed.request,(candidate,),(candidate.candidate_id,))
        document=json.loads(encode_pc_melee_balance_result(parsed,report))
        self.assertEqual(document['candidates'][0]['summary']['companion_counts'][0]['departures'],1)
        bad=deepcopy(document); del bad['candidates'][0]['summary']['companion_counts']
        with self.assertRaises(ValidationError): validate_pc_melee_balance_document(bad,'result')


if __name__=='__main__': main()
