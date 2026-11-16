"""Public-input benchmark cases and accounting of real, bounded searches."""
from copy import deepcopy
import json
import unittest

from tools.benchmark_dynamic import CASES,benchmark_input,measure
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request


class DynamicBenchmarkTests(unittest.TestCase):
    def test_three_distinct_parties_are_admitted_without_shared_mutable_inputs(self):
        documents=[benchmark_input(case,42) for case in CASES]
        for document in documents:
            command=parse_dynamic_encounter_request(json.dumps(document))
            self.assertEqual(command.request.max_total_trials,48)
        self.assertEqual([len(document['party']) for document in documents],[2,2,3])
        self.assertNotIn('ranged',documents[0]['party'][0])
        self.assertIn('ranged',documents[1]['party'][0])
        self.assertIn('magic',documents[2]['party'][-1])
        documents[2]['party'][0]['actor_id']='edited'
        self.assertNotEqual(documents[1]['party'][0]['actor_id'],'edited')
        self.assertNotEqual(benchmark_input('mixed-magic',42)['party'][0]['actor_id'],'edited')

    def test_real_small_search_preserves_source_and_accounts_for_each_measured_batch(self):
        document=benchmark_input('mixed',42,candidates=1,exploration=1,finalists=1,validation=1)
        document['npc_count']=dict(minimum=1,maximum=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        original=deepcopy(document)
        row=measure(document,unsupported_samples=0)
        self.assertEqual(document,original)
        self.assertEqual(row['source_request'],original)
        self.assertEqual(row['result']['source_request'],original)
        self.assertEqual(row['result']['total_trials'],sum(b['trials'] for b in row['batches']))
        self.assertEqual(row['result']['total_trials'],2)
        self.assertGreater(row['search_seconds'],0)
        self.assertGreaterEqual(row['encode_seconds'],0)
        self.assertEqual(row['unsupported_samples'],[])
        self.assertTrue(all(sum(b['outcomes'].values())==b['trials'] for b in row['batches']))


if __name__=='__main__':
    unittest.main()
