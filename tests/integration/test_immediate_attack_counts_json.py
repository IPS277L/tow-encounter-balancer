"""Current counter codecs from explicit aggregate fixtures, without game RNG."""
from copy import deepcopy
from dataclasses import replace
import json
from random import Random
import unittest

from jsonschema.exceptions import ValidationError

from tests.unit.test_immediate_attack_statistics import prepared_observations
from towr.adapters._pc_melee_scenario_json import scenario_document
from towr.adapters.pc_melee_json import (
    encode_pc_melee_simulation_result, parse_pc_melee_simulation_request,
)
from towr.adapters.pc_melee_json_schema import validate_pc_melee_simulation_document
from towr.simulation.pc_immediate_attack_statistics import PcImmediateAttackCount
from towr.simulation.pc_melee_summary import summarize_pc_melee_simulation


def command(request):
    raw = dict(schema_version='1', kind='pc_melee_simulation', request_id='bash:counters',
        ruleset='towr-pg1.4-gmg1.1', scenario=scenario_document(request.scenario),
        simulation=dict(master_seed=str(request.master_seed), trials=request.trials),
        execution=dict(mode='sequential'))
    parsed = parse_pc_melee_simulation_request(json.dumps(raw))
    if parsed.request != request:
        raise AssertionError('counter fixture source did not round-trip through the current request')
    return parsed


class ImmediateAttackCountJsonTests(unittest.TestCase):
    def test_balance_candidates_keep_source_ordered_counters_in_current_json(self):
        from towr.adapters.pc_melee_json import encode_pc_melee_balance_result, parse_pc_melee_balance_request
        from towr.adapters.pc_melee_json_schema import validate_pc_melee_balance_document
        from towr.application.pc_melee_balance_models import (
            PcMeleeBalanceResult, PcMeleeCandidateResult, project_pc_melee_candidate,
        )
        from towr.balance.pc_melee_assessment import PcMeleeCandidateAssessment
        base = prepared_observations()
        template = scenario_document(base.source_request.scenario)
        raw = dict(schema_version='1', kind='pc_melee_balance', request_id='bash:balance-counters',
            ruleset='towr-pg1.4-gmg1.1', template=template,
            generation=dict(groups=[dict(group_id='group:'+actor, actor_ids=[actor],
                minimum_count=1, maximum_count=1) for actor in base.source_request.scenario.enemy_activation_order],
                facts=template['facts'], max_candidates=1),
            evaluation=dict(master_seed='42', trials_per_candidate=2, max_total_trials=2, top_k=1,
                window=dict(minimum=dict(numerator=0,denominator=1), target=dict(numerator=1,denominator=2),
                    maximum=dict(numerator=1,denominator=1))), execution=dict(mode='sequential'))
        parsed = parse_pc_melee_balance_request(json.dumps(raw))
        source = project_pc_melee_candidate(parsed.request, (1, 1))
        summary = summarize_pc_melee_simulation(prepared_observations(scenario=source.scenario, trials=source.trials))
        assessment = PcMeleeCandidateAssessment(source, summary, parsed.request.window)
        candidate = PcMeleeCandidateResult(source.scenario.id, (1, 1), source, summary, assessment)
        report = PcMeleeBalanceResult(parsed.request, (candidate,), (candidate.candidate_id,))
        document = json.loads(encode_pc_melee_balance_result(parsed, report))
        observed = document['candidates'][0]['summary']
        self.assertEqual(observed['immediate_attack_counts'],
            [dict(actor_id='pc1', count=2), dict(actor_id='minion1', count=2)])
        self.assertEqual(observed['total_immediate_attack_count'], 4)
        for field in ('immediate_attack_counts', 'total_immediate_attack_count'):
            bad = deepcopy(document)
            del bad['candidates'][0]['summary'][field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_pc_melee_balance_document(bad, 'result')

    def test_dynamic_candidate_projection_preserves_generated_owner_and_requires_counters(self):
        from tests.integration.test_generated_talents_json import talent_request
        from tests.support.talent_sources import paid_talent
        from towr.adapters.dynamic_encounter_json import (
            _validator, candidate_document, parse_dynamic_encounter_request,
        )
        from towr.application.dynamic_encounter import GeneratedCandidate
        from towr.domain.talent_catalog import TalentId
        raw = talent_request()
        raw['search_space'].update(strength=[5], brawn=[4], allowed_talents=['bash_attack'])
        parsed = parse_dynamic_encounter_request(json.dumps(raw))
        npc = replace(parsed.request.space.sample(Random(0)), talents=(paid_talent(TalentId.BASH_ATTACK),))
        self.assertTrue(parsed.request.space.contains(npc))
        scenario = parsed.request.scenario((npc,), 'prepared:dynamic-counters')
        result = prepared_observations(trials=1, scenario=scenario)
        candidate = GeneratedCandidate((npc,), summarize_pc_melee_simulation(result))
        document = json.loads(json.dumps(candidate_document(parsed.request, candidate)))
        validator = _validator('result').evolve(schema={
            '$ref': 'urn:towr:dynamic-encounter:common:1#/$defs/candidate'})
        validator.validate(document)
        actor, = tuple(row.actor_id for row in candidate.summary.immediate_attack_counts)
        self.assertEqual(document['immediate_attack_counts'], [dict(actor_id=actor, count=1)])
        self.assertEqual(document['total_immediate_attack_count'], 1)
        self.assertEqual(document['npcs'][0]['talents'][0]['id'], 'bash_attack')
        for field in ('immediate_attack_counts', 'total_immediate_attack_count'):
            bad = deepcopy(document)
            del bad[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validator.validate(bad)

    def test_actual_native_strike_is_observed_once_without_an_ordinary_action_increment(self):
        from tests.support.pc_melee_scripted import ScriptedD10
        from tests.unit.test_bash_attack_execution import pc_source
        from towr.simulation.pc_melee_models import PcMeleeSimulationRequest
        from towr.simulation.pc_melee_simulation import run_pc_melee_simulation
        request = PcMeleeSimulationRequest(pc_source(), 42, 1)
        parsed = command(request)
        rng = ScriptedD10([1]*5 + [10]*2 + [1]*3 + [10]*2)
        result = run_pc_melee_simulation(parsed.request, rng_factory=lambda seed: rng)
        rng.assert_exhausted()
        record, = result.records
        self.assertEqual(record.immediate_attack_counts, (PcImmediateAttackCount('pc', 1),))
        self.assertEqual(record.executed_actions, 1)
        self.assertEqual(record.total_immediate_attack_count, 1)
        summary = summarize_pc_melee_simulation(result)
        document = json.loads(encode_pc_melee_simulation_result(parsed, summary))
        self.assertEqual(document['summary']['immediate_attack_counts'], [dict(actor_id='pc', count=1)])
        self.assertEqual(document['summary']['total_immediate_attack_count'], 1)
        self.assertEqual(document['summary']['total_action_count'], 1)

    def test_current_json_preserves_both_sources_counts_and_separate_ordinary_action_total(self):
        result = prepared_observations()
        summary = summarize_pc_melee_simulation(result)
        document = json.loads(encode_pc_melee_simulation_result(command(result.source_request), summary))
        self.assertEqual(document['schema_version'], '1')
        self.assertEqual(document['summary']['immediate_attack_counts'],
            [dict(actor_id='pc1', count=2), dict(actor_id='minion1', count=2)])
        self.assertEqual(document['summary']['total_immediate_attack_count'], 4)
        self.assertEqual(document['summary']['total_action_count'], 8)
        self.assertNotIn('fate', document['request']['scenario']['enemies'][0])

    def test_owner_zero_counts_remain_present(self):
        result = prepared_observations()
        summary = summarize_pc_melee_simulation(result)
        zeros = tuple(PcImmediateAttackCount(row.actor_id, 0) for row in summary.immediate_attack_counts)
        summary = replace(summary, immediate_attack_counts=zeros)
        document = json.loads(encode_pc_melee_simulation_result(command(result.source_request), summary))
        self.assertEqual(document['summary']['total_immediate_attack_count'], 0)
        self.assertEqual(document['summary']['immediate_attack_counts'],
            [dict(actor_id='pc1', count=0), dict(actor_id='minion1', count=0)])

    def test_source_without_owners_omits_both_fields(self):
        without = prepared_observations(owners=False)
        document = json.loads(encode_pc_melee_simulation_result(command(without.source_request),
            summarize_pc_melee_simulation(without)))
        self.assertNotIn('immediate_attack_counts', document['summary'])
        self.assertNotIn('total_immediate_attack_count', document['summary'])

    def test_schema_requires_owner_counts_and_their_total_together(self):
        result = prepared_observations()
        document = json.loads(encode_pc_melee_simulation_result(command(result.source_request),
            summarize_pc_melee_simulation(result)))
        for field in ('immediate_attack_counts', 'total_immediate_attack_count'):
            bad = deepcopy(document)
            del bad['summary'][field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(bad, 'result')
        for count in (True, -1, 1.5):
            bad = deepcopy(document)
            bad['summary']['immediate_attack_counts'][0]['count'] = count
            with self.subTest(count=count), self.assertRaises(ValidationError):
                validate_pc_melee_simulation_document(bad, 'result')


if __name__ == '__main__':
    unittest.main()
