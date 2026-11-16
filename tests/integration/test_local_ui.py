import http.client
import json
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import patch

from towr.adapters.local_ui import LocalUiServer, serve_local_ui
from towr.adapters.dynamic_encounter_json import DynamicEncounterExecutionError, validate_dynamic_encounter_document, parse_dynamic_encounter_request, execute_dynamic_encounter
from towr import cli
from towr.application.dynamic_encounter import DynamicEncounterCancelled, DynamicEncounterProgress, DynamicProgressPhase


class LocalUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = Path('docs/examples/dynamic/search.request.json').read_bytes()
        cls.server = LocalUiServer(0, cls.raw)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(5)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=30)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()

    def post(self, body, headers=None):
        return self.request('POST', '/api/generate', body,
            {'Content-Type': 'application/json','X-TOWR-Run-ID':'test-run', **(headers or {})})

    def cancel(self, token):
        return self.request('POST','/api/cancel',b'{}',
            {'Content-Type':'application/json','X-TOWR-Run-ID':token})

    def progress(self, token):
        return self.request('GET','/api/progress',headers={'X-TOWR-Run-ID':token})

    def test_character_file_validation_is_stateless_and_does_not_generate(self):
        player = json.loads(self.raw)['party'][0]
        npc = dict(weapon_skill=3, strength=3, toughness=3, agility=3, melee=4,
            athletics=3, defence=4, shield=False, weapon='staff', light_armour=False, abilities=[],talents=[])
        with patch('towr.adapters.local_ui.execute_dynamic_encounter') as execute:
            for kind, document in [('player', player), ('npc', npc)]:
                status, _, body = self.request('POST', '/api/character',
                    json.dumps(dict(kind=kind, document=json.dumps(document))).encode(),
                    {'Content-Type': 'application/json'})
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body), dict(kind=kind, character=document))
            execute.assert_not_called()
        self.assertIsNone(self.server.active_generation)
        self.assertEqual(self.request('GET', '/api/request')[2], self.raw)

    def test_character_file_boundary_rejects_wrong_origin_envelope_and_invalid_profile(self):
        player = json.loads(self.raw)['party'][0]
        raw = json.dumps(dict(kind='player', document=json.dumps(player))).encode()
        self.assertEqual(self.request('POST', '/api/character', raw,
            {'Content-Type': 'application/json', 'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('POST', '/api/character', raw,
            {'Content-Type': 'text/plain'})[0], 415)
        for payload in (b'[]', b'{}', b'{', b'{"kind":"npc","document":"{}"}',
                b'{"kind":"unknown","document":"{}"}', b'{"kind":"player","document":{}}'):
            with self.subTest(payload=payload):
                status, _, body = self.request('POST', '/api/character', payload,
                    {'Content-Type': 'application/json'})
                self.assertEqual(status, 400)
                self.assertIn('message', json.loads(body)['error'])

    def test_live_progress_reports_completed_trial_without_exposing_log(self):
        entered, release = Event(), Event()
        responses, observed = [], []

        def tracked(command, *, cancel_requested, on_progress):
            def forward(progress):
                on_progress(progress)
                if progress.phase is DynamicProgressPhase.SIMULATING and progress.completed_trials == 1 and not entered.is_set():
                    observed.append(progress)
                    entered.set()
                    if not release.wait(15):
                        raise RuntimeError('test did not release progress')
            return execute_dynamic_encounter(command, cancel_requested=cancel_requested, on_progress=forward)

        with patch('towr.adapters.local_ui.execute_dynamic_encounter',side_effect=tracked):
            worker=Thread(target=lambda: responses.append(self.post(self.raw,{'X-TOWR-Run-ID':'progress-live'})),daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(10))
                status, _, body = self.progress('progress-live')
                self.assertEqual(status, 200)
                snapshot=json.loads(body)
                self.assertEqual(snapshot['state'], 'running')
                self.assertGreater(snapshot['sequence'], 0)
                self.assertEqual(snapshot['current']['completed_trials'], 1)
                self.assertEqual(snapshot['current']['total_completed_trials'], 1)
                self.assertEqual(snapshot['current']['wins'], observed[0].wins)
                self.assertEqual(snapshot['current']['win_rate'], observed[0].win_rate)
                self.assertIsNone(snapshot['last_candidate'])
                self.assertNotIn('source_request', snapshot)
                self.assertLess(len(body), 2500)
                self.assertEqual(self.progress('foreign-run')[0], 409)
                self.assertEqual(self.request('GET','/api/progress')[0], 400)
                self.assertEqual(self.request('GET','/api/progress',headers={'X-TOWR-Run-ID':'progress-live','Origin':'http://example.com'})[0], 403)
            finally:
                release.set()
                worker.join(25)
        self.assertFalse(worker.is_alive())
        self.assertEqual(responses[0][0], 200, responses)
        validate_dynamic_encounter_document(json.loads(responses[0][2]), 'result')
        self.assertEqual(json.loads(self.progress('progress-live')[2])['state'], 'waiting')
        self.assertIsNone(self.server.active_generation)

    def test_progress_retains_last_assessment_and_respects_cancellation(self):
        entered, release = Event(), Event()
        responses=[]
        completed=DynamicEncounterProgress(DynamicProgressPhase.CANDIDATE_COMPLETE,'explore',1,3,2,2,2,2,12,1,0)
        next_candidate=DynamicEncounterProgress(DynamicProgressPhase.GENERATING,'explore',2,3,0,0,0,2,12,0,0)

        def tracked(command, *, cancel_requested, on_progress):
            on_progress(completed)
            on_progress(next_candidate)
            entered.set()
            if not release.wait(10):
                raise RuntimeError('test did not release progress')
            if cancel_requested():
                raise DynamicEncounterCancelled()
            raise RuntimeError('test expected cancellation')

        with patch('towr.adapters.local_ui.execute_dynamic_encounter',side_effect=tracked):
            worker=Thread(target=lambda: responses.append(self.post(self.raw,{'X-TOWR-Run-ID':'progress-cancel'})),daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(10))
                snapshot=json.loads(self.progress('progress-cancel')[2])
                self.assertEqual(snapshot['sequence'], 2)
                self.assertEqual(snapshot['current']['candidate_number'], 2)
                self.assertEqual(snapshot['last_candidate']['win_rate'], .5)
                self.assertEqual(self.cancel('progress-cancel')[0], 202)
                self.assertEqual(json.loads(self.progress('progress-cancel')[2])['state'], 'cancelling')
            finally:
                release.set()
                worker.join(15)
        self.assertEqual(json.loads(responses[0][2])['kind'], 'dynamic_encounter_cancelled')
        self.assertIsNone(json.loads(self.progress('progress-cancel')[2])['current'])

    def test_page_and_initial_request_are_served_without_mutation(self):
        status, content_type, body = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('text/html', content_type)
        self.assertIn('<textarea', body.decode('utf-8'))
        self.assertIn('fetch(\'/api/generate\'', body.decode('utf-8'))
        self.assertEqual(self.request('GET', '/api/request')[2], self.raw)

    def test_real_generation_returns_full_current_result(self):
        status, content_type, body = self.post(self.raw)
        self.assertEqual(status, 200, body)
        self.assertIn('application/json', content_type)
        result = json.loads(body)
        validate_dynamic_encounter_document(result, 'result')
        self.assertEqual(result['source_request'], json.loads(self.raw))
        self.assertEqual(result['total_trials'], 12)
        self.assertEqual(len(result['selected']), 2)

    def test_invalid_json_and_values_do_not_execute(self):
        for raw in (b'{', b'{"a":1,"a":2}', b'{}'):
            with self.subTest(raw=raw), patch('towr.adapters.local_ui.execute_dynamic_encounter') as execute:
                status, _, body = self.post(raw)
                self.assertEqual(status, 400)
                validate_dynamic_encounter_document(json.loads(body), 'error')
                execute.assert_not_called()
        self.assertFalse(self.server.generation_lock.locked())

    def test_loopback_origin_and_closed_routes(self):
        self.assertEqual(self.post(self.raw, {'Content-Type': 'application/json', 'Origin': 'http://example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Host': 'example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/other')[0], 404)
        self.assertEqual(self.post(self.raw, {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.post(b'', {'Content-Type': 'application/json', 'Content-Length': '3000000'})[0], 413)

    def test_ui_stays_responsive_and_rejects_duplicate_runs(self):
        entered, release = Event(), Event()
        responses = []

        def blocked(command, **kwargs):
            entered.set()
            if not release.wait(15):
                raise RuntimeError('test did not release execution')
            raise DynamicEncounterExecutionError(command.request_id)

        with patch('towr.adapters.local_ui.execute_dynamic_encounter', side_effect=blocked):
            worker = Thread(target=lambda: responses.append(self.post(self.raw)), daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(self.request('GET', '/')[0], 200)
                self.assertEqual(self.post(self.raw)[0], 409)
            finally:
                release.set()
                worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(responses[0][0], 500)
        validate_dynamic_encounter_document(json.loads(responses[0][2]), 'error')
        self.assertFalse(self.server.generation_lock.locked())

    def test_real_cancel_interrupts_dice_and_releases_worker(self):
        entered, release = Event(), Event()
        responses = []

        def first_roll(*args):
            entered.set()
            if not release.wait(10):
                raise RuntimeError('test did not release dice')
            return 1

        with patch('towr.application.dynamic_encounter.Random.randint',side_effect=first_roll) as roll:
            worker=Thread(target=lambda: responses.append(self.post(self.raw,{'X-TOWR-Run-ID':'cancel-real'})),daemon=True)
            worker.start()
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(self.cancel('old-run')[0],409)
                self.assertEqual(self.cancel('cancel-real')[0],202)
            finally:
                release.set();worker.join(10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(roll.call_count,1)
        self.assertEqual(responses[0][0],200)
        self.assertEqual(json.loads(responses[0][2]),{'kind':'dynamic_encounter_cancelled'})
        self.assertFalse(self.server.generation_lock.locked())
        self.assertIsNone(self.server.active_generation)
        # Same source can run again after cancellation; no flag leaks to it.
        status,_,body=self.post(self.raw,{'X-TOWR-Run-ID':'after-cancel'})
        self.assertEqual(status,200)
        validate_dynamic_encounter_document(json.loads(body),'result')

    def test_cancel_before_generation_arrives_skips_execution(self):
        self.assertEqual(self.cancel('early-run')[0],202)
        with patch('towr.adapters.local_ui.execute_dynamic_encounter') as execute:
            status,_,body=self.post(self.raw,{'X-TOWR-Run-ID':'early-run'})
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['kind'],'dynamic_encounter_cancelled')
            execute.assert_not_called()

    def test_stale_cancel_cannot_cancel_the_next_run(self):
        entered,release=Event(),Event();responses=[]
        def blocked(command, *, cancel_requested, on_progress):
            entered.set();release.wait(10)
            self.assertFalse(cancel_requested())
            raise DynamicEncounterExecutionError(command.request_id)
        with patch('towr.adapters.local_ui.execute_dynamic_encounter',side_effect=blocked):
            worker=Thread(target=lambda:responses.append(self.post(self.raw,{'X-TOWR-Run-ID':'next-run'})),daemon=True);worker.start()
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(self.cancel('previous-run')[0],409)
            finally:
                release.set();worker.join(10)
        self.assertEqual(responses[0][0],500)

    def test_ui_cli_dispatches_without_requiring_generator_input(self):
        with patch('towr.adapters.local_ui.serve_local_ui', return_value=0) as serve:
            self.assertEqual(cli.main(['ui', '--port', '8877', '--request', 'my-request.json']), 0)
            serve.assert_called_once_with(port=8877, request_path='my-request.json')

    def test_startup_uses_working_ui_defaults_and_preserves_explicit_file(self):
        for path, count, maximum, rate, rounds, limit, budget in (
                (None, 24, 10, .5, 5, 15, 800),
                ('docs/examples/dynamic/search.request.json', 3, 2, .6, 3, 3, 12)):
            with self.subTest(path=path), patch('towr.adapters.local_ui.LocalUiServer') as server:
                server.return_value.__enter__.return_value.server_port=8765
                with patch('builtins.print'):
                    self.assertEqual(serve_local_ui(request_path=path),0)
                source=parse_dynamic_encounter_request(server.call_args.args[1]).request
                self.assertEqual(server.call_args.kwargs['manual'],path is not None)
                self.assertEqual((source.max_candidates,source.maximum_npcs,source.target_win_rate,
                    source.target_rounds,source.max_rounds,source.max_total_trials),
                    (count,maximum,rate,rounds,limit,budget))
                if path is None:
                    self.assertEqual((source.minimum_npcs,source.exploration_trials,source.top_k,source.finalist_trials),(1,12,2,256))


if __name__ == '__main__':
    unittest.main()
