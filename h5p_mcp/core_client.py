"""Experimental F3 IPC client; the production MCP continues to use Python/Node."""
import json
import os
import queue
import signal
import subprocess
import threading
import time
from uuid import uuid4

from h5p_mcp.jobs import check_cancelled
from h5p_mcp.limits import limit


class CoreClient:
    def __init__(self, command, env=None):
        self._lock = threading.Lock()
        self._replies = queue.Queue(maxsize=2)
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env, start_new_session=os.name != 'nt',
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(limit('OUTPUT_BYTES', 33554432) + 1)
                if not line:
                    raise RuntimeError('Core closed its output')
                if len(line) > limit('OUTPUT_BYTES', 33554432):
                    raise RuntimeError('Core output budget exceeded')
                self._replies.put(json.loads(line))
        except Exception as error:
            self._replies.put(error)

    def call(self, request, deadline=None):
        from h5p_mcp.lumi_backend import BackendError
        with self._lock:
            identifier = uuid4().hex
            encoded = json.dumps({'id': identifier, 'request': request}, ensure_ascii=False).encode() + b'\n'
            if len(encoded) > limit('JSON_BYTES', 16777216):
                raise BackendError('Input budget exceeded', 'INPUT_TOO_LARGE')
            deadline = deadline or time.monotonic() + limit('SECONDS', 300)
            self.process.stdin.write(encoded)
            self.process.stdin.flush()
            try:
                while True:
                    check_cancelled()
                    if time.monotonic() >= deadline:
                        raise BackendError('Core deadline exceeded', 'BACKEND_TIMEOUT')
                    try:
                        reply = self._replies.get(timeout=.05)
                        break
                    except queue.Empty:
                        continue
            except BaseException:
                self.process.stdin.write(json.dumps({'cancel': identifier}).encode() + b'\n')
                self.process.stdin.flush()
                try:
                    self._replies.get(timeout=5)
                except queue.Empty:
                    self.close()
                raise
            if isinstance(reply, Exception):
                raise reply
            if reply.get('id') != identifier:
                raise BackendError('IPC correlation mismatch')
            if not reply['ok']:
                raise BackendError('; '.join(reply.get('errors', [])), reply.get('code'), reply.get('details'))
            return reply['result']

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
