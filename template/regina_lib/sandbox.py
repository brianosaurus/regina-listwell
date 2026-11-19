# ABOUTME: Runs short Python programs and background commands in a Daytona sandbox.
# ABOUTME: Her scripts reach the open internet only through a sandbox like this one.
from __future__ import annotations

import json
from pathlib import Path

from .gateway import PublisherError, StopWork, call, download

MARK = '<<<REGINA-JSON>>>'


class Sandbox:
    def __init__(self, sandbox_id: str | None = None, minutes: int = 10):
        self.id, self.minutes = sandbox_id, minutes

    def __enter__(self) -> 'Sandbox':
        return self.start()

    def __exit__(self, *_) -> None:
        self.delete()

    def start(self) -> 'Sandbox':
        if not self.id:
            self.id = call('daytona', 'POST', '/sandbox', body={
                'language': 'python', 'autoStopInterval': self.minutes, 'autoDeleteInterval': 0,
                'labels': {'employee': 'regina-listwell'}})['id']
        return self

    def delete(self) -> None:
        try:
            call('daytona', 'DELETE', f'/sandbox/{self.id}')
        except PublisherError:
            pass  # autoDeleteInterval removes a stopped sandbox.

    def python(self, code: str, timeout: int = 120) -> str:
        result = call('daytona', 'POST', f'/sandbox/{self.id}/code/run',
                      body={'language': 'python', 'timeout': timeout, 'code': code})
        if result.get('exitCode'):
            raise StopWork('sandbox_failed', str(result.get('result'))[:500])
        return result.get('result') or ''

    def json(self, code: str, timeout: int = 120):
        """Runs a program that ends with print(MARK + json.dumps(result))."""
        text = self.python(code, timeout)
        return json.loads(text[text.rindex(MARK) + len(MARK):])

    def download(self, path: str, name: str) -> Path:
        return download('daytona', f'/sandbox/{self.id}/files/download', name, {'path': path})

    def start_command(self, session: str, command: str) -> str:
        call('daytona', 'POST', f'/sandbox/{self.id}/process/session', body={'sessionId': session})
        return call('daytona', 'POST', f'/sandbox/{self.id}/process/session/{session}/exec',
                    body={'command': command, 'runAsync': True})['cmdId']

    def logs(self, session: str, command_id: str) -> str:
        result = call('daytona', 'GET', f'/sandbox/{self.id}/process/session/{session}/command/{command_id}/logs')
        return result if isinstance(result, str) else json.dumps(result)
