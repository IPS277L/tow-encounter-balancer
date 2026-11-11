import http.client
import json
from pathlib import Path
from threading import Event, Thread
import unittest
from unittest.mock import patch

from towr.adapters.local_ui import LocalUiServer
from towr.adapters.dynamic_encounter_json import DynamicEncounterExecutionError, validate_dynamic_encounter_document
from towr import cli


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
        return self.request('POST', '/api/generate', body, headers or {'Content-Type': 'application/json'})

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

        def blocked(command):
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

    def test_ui_cli_dispatches_without_requiring_generator_input(self):
        with patch('towr.adapters.local_ui.serve_local_ui', return_value=0) as serve:
            self.assertEqual(cli.main(['ui', '--port', '8877', '--request', 'my-request.json']), 0)
            serve.assert_called_once_with(port=8877, request_path='my-request.json')


if __name__ == '__main__':
    unittest.main()
