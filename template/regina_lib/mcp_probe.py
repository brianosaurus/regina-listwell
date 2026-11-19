# ABOUTME: Reads an MCP server's tool list, or its public Seren catalog entry, from inside a sandbox.
# ABOUTME: A digest of what it finds shows later whether the MCP changed.
from __future__ import annotations

import hashlib
import json

from .sandbox import MARK, Sandbox

_PROBE = r'''
import json, urllib.error, urllib.request
URL = __URL__
MARK = __MARK__
CATALOG = 'https://api.serendb.com/publishers/seren-agent/templates?limit=200'
HEADERS = {'content-type': 'application/json', 'accept': 'application/json, text/event-stream', 'user-agent': 'curl/8.7.1 (regina-listwell)'}

def post(body, session=None):
    headers = dict(HEADERS)
    if session:
        headers['mcp-session-id'] = session
    request = urllib.request.Request(URL, json.dumps(body).encode(), headers, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return response.status, response.headers.get('mcp-session-id'), response.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as error:
        return error.code, None, error.read().decode('utf-8', 'replace')
    except OSError:
        return 0, None, ''

def message(text):
    for line in text.splitlines():
        if line.startswith('data:'):
            return json.loads(line[5:].strip())
    return json.loads(text) if text.strip() else {}

def catalog():
    try:
        with urllib.request.urlopen(urllib.request.Request(CATALOG, headers={'user-agent': HEADERS['user-agent']}), timeout=25) as response:
            data = json.load(response)
    except OSError:
        return None
    rows = data.get('data', data)
    rows = rows if isinstance(rows, list) else rows.get('templates', [])
    for row in rows:
        if row.get('mcp_url') == URL:
            return {key: row.get(key) for key in ('mcp_url', 'mcp_tools', 'tagline', 'description', 'capabilities', 'published_at', 'display_name')}
    return None

result = {'status': 'unreachable', 'tools': [], 'server': {}, 'catalog': catalog()}
status, session, text = post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'regina-listwell', 'version': '1.0'}}})
if status in (401, 403):
    result['status'] = 'sign_in_required'
elif status == 200:
    result['server'] = message(text).get('result', {}).get('serverInfo', {})
    post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, session)
    status, _, text = post({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}, session)
    if status == 200:
        result['status'] = 'ok'
        result['tools'] = message(text).get('result', {}).get('tools', [])
print(MARK + json.dumps(result))
'''


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def read_mcp(url: str) -> dict:
    code = _PROBE.replace('__URL__', json.dumps(url)).replace('__MARK__', json.dumps(MARK))
    with Sandbox() as box:
        result = box.json(code)
    result['tools'] = sorted(({key: tool.get(key) for key in ('name', 'description', 'inputSchema')} for tool in result['tools']),
                             key=lambda tool: tool['name'] or '')
    return result
