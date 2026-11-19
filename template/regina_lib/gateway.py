# ABOUTME: Calls Seren publishers from skill scripts and unwraps Seren's response envelope.
# ABOUTME: Large request and response bodies travel as files in the run workspace.
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GATEWAY = 'https://api.serendb.com/publishers'
USER_AGENT = 'curl/8.7.1 (regina-listwell)'
BODY_FILE_HEADER = 'X-Seren-Request-Body-File'
RESPONSE_FILE_HEADER = 'X-Seren-Response-File'
RETRY_STATUSES = (0, 429, 500, 502, 503, 504)


class PublisherError(RuntimeError):
    def __init__(self, publisher: str, status: int, code: str):
        super().__init__(f'{publisher} refused the request (HTTP {status}, {code})')
        self.publisher, self.status, self.code = publisher, status, code


class StopWork(RuntimeError):
    """A known reason this piece of work can't continue; the code tells the skill what to do next."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def workspace() -> Path:
    return Path(os.environ['SEREN_RUN_WORKSPACE'])


def _error_code(raw: bytes) -> str:
    try:
        body = json.loads(raw)
    except ValueError:
        return 'unknown'
    if not isinstance(body, dict):
        return 'unknown'
    error = body.get('error')
    if isinstance(error, dict):
        return str(error.get('code') or 'unknown')
    return str(error or body.get('code') or 'unknown')


def _once(publisher: str, url: str, method: str, payload: bytes | None, headers: dict, timeout: int):
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
        error.close()
        raise PublisherError(publisher, status, _error_code(raw)) from None
    except OSError:
        raise PublisherError(publisher, 0, 'transport') from None
    decoded = json.loads(raw) if raw else {}
    inner = decoded['data'] if isinstance(decoded, dict) and set(decoded) == {'data'} else decoded
    if isinstance(inner, dict) and type(inner.get('status')) is int and not 200 <= inner['status'] < 300:
        raise PublisherError(publisher, inner['status'], _error_code(json.dumps(inner.get('body')).encode('utf-8')))
    if isinstance(inner, dict) and 'status' in inner and 'body' in inner:
        return inner['body']
    return inner


def call(publisher: str, method: str = 'GET', path: str = '', query: dict | None = None, body=None,
         headers: dict | None = None, timeout: int = 140):
    url = f'{GATEWAY}/{publisher}{path}'
    if query:
        url += '?' + urllib.parse.urlencode({key: value for key, value in query.items() if value is not None})
    payload = json.dumps(body).encode('utf-8') if body is not None else None
    sent = {'Authorization': f"Bearer {os.environ['SEREN_API_KEY']}", 'User-Agent': USER_AGENT,
            'Accept': 'application/json', **(headers or {})}
    if payload is not None:
        sent['Content-Type'] = 'application/json'
    waits = (0, 3, 9) if method == 'GET' else (0,)
    for attempt, wait in enumerate(waits):
        time.sleep(wait)
        try:
            return _once(publisher, url, method, payload, sent, timeout)
        except PublisherError as error:
            if attempt == len(waits) - 1 or error.status not in RETRY_STATUSES:
                raise
    raise AssertionError('unreachable')


def post_file(publisher: str, path: str, body: dict, name: str, headers: dict | None = None):
    """Sends a JSON body from a run workspace file, for bodies over 1 MiB and approved sends."""
    (workspace() / name).write_text(json.dumps(body), encoding='utf-8')
    return call(publisher, 'POST', path, headers={**(headers or {}), BODY_FILE_HEADER: name})


def download(publisher: str, path: str, name: str, query: dict | None = None) -> Path:
    """Saves a response of any size up to 20 MiB into the run workspace."""
    call(publisher, 'GET', path, query=query, headers={RESPONSE_FILE_HEADER: name})
    return workspace() / name
