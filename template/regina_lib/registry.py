# ABOUTME: Publishes an MCP to the official MCP Registry with mcp-publisher inside a sandbox.
# ABOUTME: The hirer approves a GitHub device code between registry-start and registry-finish.
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .gateway import StopWork, call
from .records import Records, jsonish
from .sandbox import MARK, Sandbox

WORK = '/tmp/registry'
SESSION = 'registry'
_INSTALL = r'''
import io, json, os, platform, subprocess, tarfile, urllib.request
os.makedirs(__WORK__, exist_ok=True)
os.chdir(__WORK__)
arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}[platform.machine()]
url = f'https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_linux_{arch}.tar.gz'
tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen(url, timeout=60).read())).extract('mcp-publisher', '.')
os.chmod('mcp-publisher', 0o755)
json.dump(__SERVER__, open('server.json', 'w'))
done = subprocess.run(['./mcp-publisher', 'validate'], capture_output=True, text=True, timeout=30)
print(__MARK__ + json.dumps({'valid': done.returncode == 0, 'output': (done.stdout + done.stderr)[:800]}))
'''
_PUBLISH = r'''
import json, os, subprocess
os.chdir(__WORK__)
done = subprocess.run(['./mcp-publisher', 'publish'], capture_output=True, text=True, timeout=60)
print(__MARK__ + json.dumps({'published': done.returncode == 0, 'output': (done.stdout + done.stderr)[:800]}))
'''


def _submission(records: Records, mcp_id: int) -> dict:
    row = records.one("""SELECT s.id, s.external, m.pack, m.pack_hash, d.id AS directory_id FROM submission s
                         JOIN mcp_server m ON m.id = s.mcp_id JOIN directory d ON d.id = s.directory_id
                         WHERE s.mcp_id = $1 AND d.key = 'official-registry'""", [mcp_id])
    if not row:
        raise StopWork('registry_not_queued', 'Approve the listing pack first.')
    return row


def _server_json(pack: dict, login: str, version: str) -> dict:
    slug = re.sub(r'[^a-z0-9-]+', '-', pack['name'].lower()).strip('-')
    server = {'$schema': 'https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json',
              'name': f'io.github.{login}/{slug}', 'title': pack['name'], 'description': pack['short_description'],
              'version': version, 'remotes': [{'type': pack['transport'], 'url': pack['mcp_url']}]}
    if pack.get('repository_url'):
        server['repository'] = {'url': pack['repository_url'], 'source': 'github'}
    return server


def start(records: Records, args: dict) -> dict:
    row = _submission(records, int(args['mcp']))
    pack = jsonish(row['pack'])
    login = call('github-api', 'GET', '/user')['login']
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    count = records.one("SELECT count(*) AS n FROM submission_event WHERE submission_id = $1 AND kind = 'registry_published'", [row['id']])['n']
    server = _server_json(pack, login, f'1.{today}.{int(count) + 1}')
    box = Sandbox(minutes=30).start()
    code = (_INSTALL.replace('__WORK__', json.dumps(WORK)).replace('__MARK__', json.dumps(MARK))
            .replace('__SERVER__', repr(server)))
    checked = box.json(code)
    if not checked['valid']:
        box.delete()
        raise StopWork('registry_invalid', checked['output'])
    command_id = box.start_command(SESSION, f'cd {WORK} && ./mcp-publisher login github')
    for _ in range(10):
        found = re.search(r'\b[A-Z0-9]{4}-[A-Z0-9]{4}\b', box.logs(SESSION, command_id))
        if found:
            break
        box.python('import time; time.sleep(2)')
    else:
        box.delete()
        raise StopWork('registry_no_code', 'mcp-publisher did not print a sign-in code.')
    records.set_submission(row['id'], 'needs_owner', external={'sandbox': box.id, 'command': command_id, 'server': server['name']})
    return {'go_to': 'https://github.com/login/device', 'code': found.group(0), 'server_name': server['name']}


def finish(records: Records, args: dict) -> dict:
    row = _submission(records, int(args['mcp']))
    external = jsonish(row['external'])
    box = Sandbox(external['sandbox'])
    if 'Successfully' not in box.logs(SESSION, external['command']):
        raise StopWork('registry_waiting', 'The hirer has not approved the GitHub code yet.')
    result = box.json(_PUBLISH.replace('__WORK__', json.dumps(WORK)).replace('__MARK__', json.dumps(MARK)))
    box.delete()
    if not result['published']:
        raise StopWork('registry_refused', result['output'])
    link = f"https://registry.modelcontextprotocol.io/v0.1/servers?search={external['server']}"
    records.set_submission(row['id'], 'listed', submitted_hash=row['pack_hash'], public_url=link, external={'server': external['server']})
    records.event(row['id'], 'registry_published', f"Published {external['server']} to the official registry.", link)
    return {'published': True, 'link': link}


COMMANDS = {'registry-start': start, 'registry-finish': finish}
