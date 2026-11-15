"""Loopback-only UI adapter over the existing dynamic JSON contract."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from dataclasses import dataclass, field
from threading import Event, Lock

from towr.adapters._local_ui_page import PAGE
from towr.adapters.dynamic_encounter_json import (
    DynamicEncounterInputError, DynamicEncounterExecutionError,
    parse_dynamic_encounter_request, execute_dynamic_encounter,
    encode_dynamic_encounter_result, encode_dynamic_encounter_error,
)
from towr.application.dynamic_encounter import DynamicEncounterCancelled


@dataclass
class _ActiveGeneration:
    token: str
    cancel: Event = field(default_factory=Event)
    finished: bool = False


class LocalUiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=8765, initial_request=b'{}', *, manual=False):
        self.initial_request = initial_request
        self.manual = manual
        self.generation_lock = Lock()
        self.state_lock = Lock()
        self.active_generation = None
        self.early_cancels = {}
        super().__init__(('127.0.0.1', port), LocalUiHandler)


class LocalUiHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _respond(self, status, body, content_type='application/json; charset=utf-8', *, headers=None):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
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
            self._respond(200, self.server.initial_request,
                headers={'X-TOWR-UI-Mode': 'manual' if self.server.manual else 'auto'})
        else:
            self._error(404, 'Not found')

    def do_POST(self):
        if not self._local_request():
            self._error(403, 'Local requests only')
            return
        if self.path not in ('/api/generate', '/api/cancel'):
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
        token = self.headers.get('X-TOWR-Run-ID', '')
        if not token.strip() or len(token) > 128:
            self._error(400, 'X-TOWR-Run-ID required')
            return
        if self.path == '/api/cancel':
            self.connection.settimeout(30)
            try:
                if len(self.rfile.read(length)) != length:
                    self._error(400, 'Incomplete request')
                    return
            except (TimeoutError, ConnectionError):
                self._error(408, 'Request interrupted')
                return
            with self.server.state_lock:
                active = self.server.active_generation
                mismatch = active is not None and active.token != token
                accepted = not mismatch and (active is None or not active.finished)
                if active is not None and accepted:
                    active.cancel.set()
                elif active is None:
                    # A click can reach us before the generation POST registers.
                    self.server.early_cancels[token] = None
                    if len(self.server.early_cancels) > 128:
                        self.server.early_cancels.pop(next(iter(self.server.early_cancels)))
            if mismatch:
                self._error(409, 'Этот расчёт уже не активен.')
                return
            self._respond(202 if accepted else 200, json.dumps({'cancel_requested': accepted}))
            return
        if not self.server.generation_lock.acquire(blocking=False):
            self._error(409, 'Расчёт уже выполняется. Дождитесь его завершения.')
            return
        active = _ActiveGeneration(token)
        with self.server.state_lock:
            if token in self.server.early_cancels:
                active.cancel.set()
                self.server.early_cancels.pop(token)
            self.server.active_generation = active
        try:
            self.connection.settimeout(30)
            raw = self.rfile.read(length)
            if len(raw) != length:
                self._error(400, 'Incomplete request')
                return
            try:
                if active.cancel.is_set():
                    raise DynamicEncounterCancelled()
                command = parse_dynamic_encounter_request(raw)
                result = execute_dynamic_encounter(command, cancel_requested=active.cancel.is_set)
                output = encode_dynamic_encounter_result(command, result)
                status = 200
            except DynamicEncounterCancelled:
                active.cancel.set()
                status, output = 200, ''
            except DynamicEncounterInputError as error:
                status, output = 400, encode_dynamic_encounter_error(error)
            except DynamicEncounterExecutionError as error:
                status, output = 500, encode_dynamic_encounter_error(error)
            with self.server.state_lock:
                if active.cancel.is_set():
                    status, output = 200, json.dumps({'kind': 'dynamic_encounter_cancelled'})
                active.finished = True
            self._respond(status, output)
        except (TimeoutError, ConnectionError):
            self._error(408, 'Request interrupted')
        except Exception:
            # No traceback or partial result is sent to the browser.
            self._error(500, 'Не удалось завершить расчёт.')
        finally:
            with self.server.state_lock:
                if self.server.active_generation is active:
                    self.server.active_generation = None
            self.server.generation_lock.release()


def serve_local_ui(*, port=8765, request_path=None):
    if request_path is None:
        example = Path('docs/examples/dynamic/ui.request.json')
        initial = example.read_bytes() if example.is_file() else b'{}'
    else:
        initial = Path(request_path).read_bytes()
    with LocalUiServer(port, initial, manual=request_path is not None) as server:
        print(f'TOWR UI: http://127.0.0.1:{server.server_port}/ (Ctrl+C to stop)', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0
