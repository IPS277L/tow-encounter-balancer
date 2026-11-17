"""Public-input benchmark cases and accounting of real, bounded searches."""
from copy import deepcopy
from contextlib import redirect_stderr,redirect_stdout
import io
import json
from pathlib import Path
from random import Random
import tempfile
import unittest
from unittest.mock import patch

import tools.benchmark_dynamic as benchmark
from tools.benchmark_dynamic import CASES,benchmark_input,measure,main
from towr.adapters.dynamic_encounter_json import parse_dynamic_encounter_request,encode_dynamic_encounter_result
import towr.application.dynamic_encounter as app
from towr.adapters.pc_melee_json import parse_pc_melee_simulation_request
from towr.simulation.pc_melee_simulation import run_pc_melee_trial


class DynamicBenchmarkTests(unittest.TestCase):
    def test_joint_diagnostics_pair_full_sources_and_keep_unsupported_separate(self):
        def candidate(name,status,win=True,rounds=True):
            return dict(npcs=[dict(weapon=name,stats=[3,4])],replay=dict(scenario=dict(id=name)),
                target_assessment=dict(status=status,win_rate_in_range=win,started_rounds_in_range=rounds),
                win_rate=.5,mean_started_rounds=5)
        a=candidate('a','within_targets')
        b=candidate('b','outside_targets',True,False)
        c=candidate('c','outside_targets',False,True)
        d=candidate('d','outside_targets',False,False)
        e=candidate('e','unsupported')
        report=dict(explored=[a,b,c,d,e],validations=[dict(deepcopy(c),target_assessment=dict(
            status='within_targets',win_rate_in_range=True,started_rounds_in_range=True)),
            dict(deepcopy(a),target_assessment=dict(status='unsupported',win_rate_in_range=True,started_rounds_in_range=True)),deepcopy(b)],
            target_match_found=True)
        original=deepcopy(report)
        metrics=benchmark._joint_target_statistics(report)
        self.assertEqual(metrics['explored'],dict(candidates=5,both=1,win_only=1,rounds_only=1,neither=1,unsupported=1))
        self.assertEqual(metrics['validations'],dict(candidates=3,both=1,win_only=1,rounds_only=0,neither=0,unsupported=1))
        self.assertEqual(metrics['screening_matches_revalidated'],1)
        self.assertEqual(metrics['retained_matches'],0)
        self.assertEqual(metrics['newly_observed_validation_matches'],1)
        self.assertEqual([t['exploration_id'] for t in metrics['transitions']],['c','a','b'])
        self.assertEqual(report,original)
        malformed=deepcopy(report);malformed['validations'][0]['npcs'][0]['stats']=[3,5]
        with self.assertRaisesRegex(ValueError,'complete matching'):
            benchmark._joint_target_statistics(malformed)
        malformed=deepcopy(report);malformed['target_match_found']=False
        with self.assertRaisesRegex(ValueError,'match flag'):
            benchmark._joint_target_statistics(malformed)

    def test_joint_diagnostics_empty_validation_is_not_an_execution_failure(self):
        report=dict(explored=[],validations=[],target_match_found=False)
        metrics=benchmark._joint_target_statistics(report)
        self.assertFalse(metrics['target_match_found'])
        self.assertEqual(metrics['validations']['candidates'],0)
        self.assertEqual(metrics['transitions'],[])

    def test_proposal_statistics_counts_attempts_duplicates_and_fallbacks_without_mutation(self):
        events=[dict(attempt=1,requested='restart',applied='restart',npc_count=3,duplicate=False),
            dict(attempt=2,requested='count',applied='component',npc_count=3,duplicate=False),
            dict(attempt=3,requested='component',applied='component',npc_count=3,duplicate=True),
            dict(attempt=4,requested='count',applied='component',npc_count=3,duplicate=True),
            dict(attempt=5,requested='component',applied='restart',npc_count=2,duplicate=False)]
        original=deepcopy(events)
        self.assertEqual(benchmark._proposal_statistics(events),dict(attempts=5,accepted=3,duplicates=2,
            requested=dict(count=2,component=2,restart=1),
            applied=dict(count=0,component=3,restart=2),fallbacks=3,
            fallback_paths={'component->restart':1,'count->component':2}))
        self.assertEqual(events,original)
        self.assertEqual(benchmark._proposal_statistics([]),dict(attempts=0,accepted=0,duplicates=0,
            requested=dict(count=0,component=0,restart=0),
            applied=dict(count=0,component=0,restart=0),fallbacks=0,fallback_paths={}))

    def test_proposal_capture_preserves_result_identity_rng_and_exact_call_arguments(self):
        npc=app.NpcSearchSpace().sample(Random(12))
        operation=app._ProposalOperation
        proposals=(app._Proposal(operation.RESTART,operation.RESTART,(npc,)),
            app._Proposal(operation.COUNT,operation.COMPONENT,(npc,)),
            app._Proposal(operation.COMPONENT,operation.COMPONENT,(npc,npc)))
        request,explored=object(),[]
        rng=Random(42);state=rng.getstate()
        with patch.object(app,'_propose',side_effect=proposals) as original:
            with benchmark._capture_proposals() as events:
                for proposal in proposals:
                    self.assertIs(app._propose(request,explored,rng,proposal.requested),proposal)
                self.assertEqual(rng.getstate(),state)
            self.assertIs(app._propose,original)
        self.assertEqual([call.args for call in original.call_args_list],
            [(request,explored,rng,proposal.requested) for proposal in proposals])
        self.assertEqual(events,[
            dict(attempt=1,requested='restart',applied='restart',npc_count=1,duplicate=False),
            dict(attempt=2,requested='count',applied='component',npc_count=1,duplicate=True),
            dict(attempt=3,requested='component',applied='component',npc_count=2,duplicate=False)])
        self.assertEqual(benchmark._proposal_statistics(events)['fallbacks'],1)

    def test_proposal_capture_restores_private_helper_when_search_raises(self):
        with patch.object(app,'_propose',side_effect=RuntimeError('proposal failed')) as original:
            with self.assertRaisesRegex(RuntimeError,'proposal failed'):
                with benchmark._capture_proposals() as events:
                    app._propose(object(),[],Random(42),app._ProposalOperation.RESTART)
            self.assertIs(app._propose,original)
            self.assertEqual(events,[])

    def test_native_trace_preserves_complete_untraced_public_result(self):
        document=benchmark_input('melee',42,candidates=2,exploration=1,finalists=1,validation=1,
            minimum_npcs=1,maximum_npcs=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        command=parse_dynamic_encounter_request(json.dumps(document))
        native=app.search_dynamic_encounter(command.request)
        expected=json.loads(encode_dynamic_encounter_result(command,native))
        traced=measure(document,unsupported_samples=0)
        self.assertEqual(traced['result'],expected)
        self.assertNotIn('proposal_metrics',traced['result'])
        self.assertNotIn('joint_target_metrics',traced['result'])
        self.assertEqual(traced['joint_target_metrics']['target_match_found'],native.target_match_found)
        self.assertEqual(traced['joint_target_metrics']['explored']['candidates'],len(native.explored))
        metrics=traced['proposal_metrics']
        self.assertEqual(metrics['attempts'],native.proposal_attempts)
        self.assertEqual(metrics['accepted'],len(native.explored))
        self.assertEqual(metrics['duplicates'],native.proposal_attempts-len(native.explored))
        self.assertEqual(len(metrics['events']),metrics['attempts'])
        self.assertEqual(metrics['events'][0]['requested'],'restart')
        self.assertEqual(sum(metrics['requested'].values()),metrics['attempts'])
        self.assertEqual(sum(metrics['applied'].values()),metrics['attempts'])

    def test_proposal_accounting_mismatch_is_rejected_before_public_encoding(self):
        document=benchmark_input('mixed',42,candidates=1,exploration=1,finalists=1,validation=1,
            maximum_npcs=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        for wrong in (dict(attempts=0,accepted=1),dict(attempts=1,accepted=0)):
            with self.subTest(wrong=wrong), \
                    patch.object(benchmark,'_proposal_statistics',return_value=wrong), \
                    patch.object(benchmark,'encode_dynamic_encounter_result') as encode:
                with self.assertRaisesRegex(ValueError,'proposal telemetry'):
                    measure(document,unsupported_samples=0)
                encode.assert_not_called()

    def test_equal_budget_alternatives_keep_validation_independent_and_count_range_explicit(self):
        narrow=benchmark_input('mixed',101,candidates=4,exploration=8,
            validation=16,maximum_npcs=10)
        wide=benchmark_input('mixed',101,candidates=8,exploration=4,
            validation=16,maximum_npcs=10)
        for document in (narrow,wide):
            command=parse_dynamic_encounter_request(json.dumps(document))
            self.assertEqual(command.request.max_total_trials,64)
            self.assertEqual((command.request.minimum_npcs,command.request.maximum_npcs),(1,10))
        self.assertEqual(narrow['party'],wide['party'])
        self.assertEqual(narrow['search']['master_seed'],wide['search']['master_seed'])
        self.assertEqual(narrow['search']['finalist_trials'],wide['search']['finalist_trials'])

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

    def test_exported_request_is_measured_without_seed_or_plan_overrides(self):
        document=benchmark_input('mixed',202,candidates=1,exploration=1,finalists=1,validation=1,
            maximum_npcs=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);source=folder/'request.json';output=folder/'report.json'
            source.write_text(json.dumps(document),encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--requests',str(source),'--output',str(output),'--unsupported-samples','0']),0)
            report=json.loads(output.read_text(encoding='utf-8'))['measurements'][0]
        self.assertEqual(report['source_request'],document)
        self.assertEqual(report['result']['source_request'],document)
        self.assertEqual(report['result']['total_trials'],2)
        self.assertEqual(report['unsupported_replay_count'],0)

    def test_exported_requests_reject_overrides_and_admit_entire_series_first(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);source=folder/'request.json';bad=folder/'bad.json';duplicate=folder/'duplicate.json'
            raw=json.dumps(benchmark_input('mixed',42))
            source.write_text(raw,encoding='utf-8')
            bad.write_text('{}',encoding='utf-8')
            duplicate.write_text('{"schema_version":"1",'+raw[1:],encoding='utf-8')
            with patch('tools.benchmark_dynamic.measure') as run:
                for args in (['--requests',str(source),'--seeds','99'],
                        ['--requests',str(source),'--unsupported-samples','-1'],
                        ['--requests',str(source),str(bad)],
                        ['--requests',str(source),str(duplicate)]):
                    with self.subTest(args=args),redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
                        main(args+['--output',str(folder/'out.json')])
                    self.assertEqual(error.exception.code,2)
                run.assert_not_called()

    def test_failure_diagnostic_preserves_exact_trial_source_and_completed_prefix(self):
        document=benchmark_input('mixed',42,candidates=1,exploration=2,finalists=1,validation=1,
            maximum_npcs=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        observed=[]
        def broken(source,*,on_trial_complete):
            observed.append(source)
            on_trial_complete(run_pc_melee_trial(source,0))
            raise RuntimeError('controlled failure after one completed trial')
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'failure.json'
            with patch('tools.benchmark_dynamic.run_pc_melee_simulation',side_effect=broken), \
                    self.assertRaisesRegex(RuntimeError,'controlled failure'):
                measure(document,failure_output=path)
            diagnostic=json.loads(path.read_text(encoding='utf-8'))
        replay=parse_pc_melee_simulation_request(json.dumps(diagnostic['replay'])).request
        self.assertEqual(replay,observed[0])
        self.assertEqual(diagnostic['source_request'],document)
        self.assertEqual(diagnostic['completed_trial_count'],1)
        self.assertEqual(diagnostic['next_trial_seed'],str(replay.seed_for(1)))
        self.assertEqual(diagnostic['completed_batches'],[])

    def test_trial_observer_preserves_complete_result_and_seed_sequence(self):
        document=benchmark_input('mixed',42,candidates=1,exploration=1,finalists=1,validation=1,
            maximum_npcs=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        baseline=measure(document)
        records=[]
        observed=measure(document,on_trial_complete=lambda source,record:records.append((source,record)))
        self.assertEqual(observed['result'],baseline['result'])
        self.assertEqual(len(records),2)
        self.assertNotEqual(records[0][1].seed,records[1][1].seed)

    def test_process_request_uses_reusable_backend_and_counts_arrivals_not_indices(self):
        document=benchmark_input('mixed',42,candidates=1,exploration=2,finalists=1,validation=1,
            maximum_npcs=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        document['execution']=dict(mode='process',workers=2)
        sequential=benchmark.run_pc_melee_simulation
        with patch('tools.benchmark_dynamic.PcMeleeProcessSession') as factory:
            session=factory.return_value.__enter__.return_value
            def run(source,**kwargs):
                result=sequential(source)
                for record in reversed(result.records):
                    kwargs['on_trial_complete'](record)
                return result
            session.run.side_effect=run
            records=[]
            result=measure(document,on_trial_complete=lambda source,record:records.append(record))
            factory.assert_called_once_with(workers=2,batch_size=1)
            self.assertEqual(session.run.call_count,2)
            session.close.assert_called_once()
        self.assertEqual(result['result']['source_request'],document)
        self.assertEqual([r.trial_index for r in records],[1,0,0])
        self.assertEqual(result['result']['total_trials'],3)

    def test_process_failure_diagnostic_tracks_exact_received_indices(self):
        document=benchmark_input('mixed',42,candidates=1,exploration=2,finalists=1,validation=1,
            maximum_npcs=1)
        document['max_rounds']=1
        document['targets']['started_rounds']=dict(numerator=1,denominator=1)
        document['execution']=dict(mode='process',workers=2)
        sequential=benchmark.run_pc_melee_simulation
        def broken(source,*,on_trial_complete):
            on_trial_complete(sequential(source).records[1])
            error=RuntimeError('controlled out-of-order failure')
            error.add_note('worker failure test')
            raise error
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'failure.json'
            with patch('tools.benchmark_dynamic.PcMeleeProcessSession') as factory:
                factory.return_value.__enter__.return_value.run.side_effect=broken
                with self.assertRaisesRegex(RuntimeError,'out-of-order'):
                    measure(document,failure_output=path)
            failure=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(failure['completed_trial_indices'],[1])
        self.assertEqual(failure['completed_trial_count'],1)
        self.assertEqual(failure['next_trial_index'],0)
        self.assertEqual(failure['error_notes'],['worker failure test'])


if __name__=='__main__':
    unittest.main()
