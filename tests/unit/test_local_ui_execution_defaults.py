"""CPU-aware defaults apply only to newly created UI requests."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from towr.adapters.local_ui import _default_dynamic_request, serve_local_ui


class LocalUiExecutionDefaultsTests(unittest.TestCase):
    def test_new_requests_reserve_one_cpu_and_cap_processes_at_four(self):
        original = json.loads(Path('docs/examples/dynamic/ui.request.json').read_bytes())
        for cpus, expected in (
                (None, {'mode': 'sequential'}),
                (1, {'mode': 'sequential'}),
                (2, {'mode': 'sequential'}),
                (3, {'mode': 'process', 'workers': 2}),
                (4, {'mode': 'process', 'workers': 3}),
                (5, {'mode': 'process', 'workers': 4}),
                (16, {'mode': 'process', 'workers': 4})):
            with self.subTest(cpus=cpus), patch('towr.adapters.local_ui.os.cpu_count', return_value=cpus):
                source = json.loads(_default_dynamic_request())
                self.assertEqual(source.pop('execution'), expected)
                self.assertEqual(source, {key: value for key, value in original.items() if key != 'execution'})

    def test_explicit_file_keeps_exact_bytes_and_execution(self):
        for execution in ({'mode': 'sequential'}, {'mode': 'process', 'workers': 7}):
            raw = json.dumps({'execution': execution}, indent=3).encode('utf-8')
            with self.subTest(execution=execution), \
                    patch('towr.adapters.local_ui.Path.read_bytes', return_value=raw), \
                    patch('towr.adapters.local_ui._default_dynamic_request') as default, \
                    patch('towr.adapters.local_ui.LocalUiServer') as server, patch('builtins.print'):
                server.return_value.__enter__.return_value.server_port = 8765
                self.assertEqual(serve_local_ui(request_path='loaded.json'), 0)
                default.assert_not_called()
                self.assertEqual(server.call_args.args[1], raw)
                self.assertTrue(server.call_args.kwargs['manual'])

    def test_missing_repository_example_keeps_existing_empty_fallback(self):
        with patch('towr.adapters.local_ui.Path.is_file', return_value=False):
            self.assertEqual(_default_dynamic_request(), b'{}')


if __name__ == '__main__':
    unittest.main()
