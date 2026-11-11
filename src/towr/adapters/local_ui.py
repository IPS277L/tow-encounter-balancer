"""Loopback-only UI adapter over the existing dynamic JSON contract."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Lock

from towr.adapters._local_ui_page import PAGE
from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, DynamicEncounterExecutionError,
    parse_dynamic_encounter_request, execute_dynamic_encounter,
    encode_dynamic_encounter_result, encode_dynamic_encounter_error,
)


class LocalUiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=8765, initial_request=b'{}'):
        self.initial_request = initial_request
        self.generation_lock = Lock()
        super().__init__(('127.0.0.1', port), LocalUiHandler)


class LocalUiHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _respond(self, status, body, content_type='application/json; charset=utf-8'):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def _error(self, status, message):
        self._respond(status, json.dumps({'error': {'message': message}}, ensure_ascii=False))

    def _local_request(self):
        port = self.server.server_port
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        origin = self.headers.get('Origin')
        return (self.headers.get('Host') in hosts
            and (origin is None or origin in {f'http://{host}' for host in hosts}))

    def do_GET(self):
        if not self._local_request():
            self._error(403, 'Local requests only')
        elif self.path == '/':
            self._respond(200, PAGE, 'text/html; charset=utf-8')
        elif self.path == '/api/request':
            self._respond(200, self.server.initial_request)
        else:
            self._error(404, 'Not found')

    def do_POST(self):
        if not self._local_request():
            self._error(403, 'Local requests only')
            return
        if self.path != '/api/generate':
            self._error(404, 'Not found')
            return
        if self.headers.get_content_type() != 'application/json':
            self._error(415, 'Expected application/json')
            return
        try:
            length = int(self.headers.get('Content-Length', ''))
        except ValueError:
            self._error(411, 'Content-Length required')
            return
        if not 0 <= length <= 2*1024*1024:
            self._error(413, 'Request exceeds 2 MiB')
            return
        if not self.server.generation_lock.acquire(blocking=False):
            self._error(409, 'Расчёт уже выполняется. Дождитесь его завершения.')
            return
        try:
            self.connection.settimeout(30)
            raw = self.rfile.read(length)
            if len(raw) != length:
                self._error(400, 'Incomplete request')
                return
            try:
                command = parse_dynamic_encounter_request(raw)
                result = execute_dynamic_encounter(command)
                output = encode_dynamic_encounter_result(command, result)
            except DynamicEncounterInputError as error:
                self._respond(400, encode_dynamic_encounter_error(error))
            except DynamicEncounterExecutionError as error:
                self._respond(500, encode_dynamic_encounter_error(error))
            else:
                self._respond(200, output)
        except (TimeoutError, ConnectionError):
            self._error(408, 'Request interrupted')
        except Exception:
            # No traceback or partial result is sent to the browser.
            self._error(500, 'Не удалось завершить расчёт.')
        finally:
            self.server.generation_lock.release()


def serve_local_ui(*, port=8765, request_path=None):
    if request_path is None:
        example = Path('docs/examples/dynamic/search.request.json')
        initial = example.read_bytes() if example.is_file() else b'{}'
    else:
        initial = Path(request_path).read_bytes()
    with LocalUiServer(port, initial) as server:
        print(f'TOWR UI: http://127.0.0.1:{server.server_port}/ (Ctrl+C to stop)', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0
