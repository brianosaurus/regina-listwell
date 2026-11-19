# ABOUTME: Detects changes to an MCP, its code and its website, and confirms that listings are still live.
# ABOUTME: Only a changed listing pack starts updates, so a cosmetic website edit never reaches a directory.
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

from .gateway import PublisherError, call
from .mcp_probe import digest, read_mcp
from .records import Records, jsonish


def _repository(url: str) -> dict:
    owner, repo = urlsplit(url).path.strip('/').split('/')[:2]
    commits = call('github-api', 'GET', f'/repos/{owner}/{repo}/commits', query={'per_page': 1})
    releases = call('github-api', 'GET', f'/repos/{owner}/{repo}/releases', query={'per_page': 1})
    return {'commit': commits[0]['sha'] if commits else None, 'release': releases[0]['tag_name'] if releases else None}


def _page_text(url: str) -> str:
    page = call('firecrawl', 'POST', '/v2/scrape', body={'url': url, 'formats': ['markdown'], 'onlyMainContent': True, 'maxAge': 0})
    return page.get('data', {}).get('markdown', '')


def _sources(mcp: dict) -> dict:
    pack = jsonish(mcp['pack'])
    probe = read_mcp(mcp['mcp_url'])
    found = {'mcp_tools': {'status': probe['status'], 'server': probe['server'], 'tools': probe['tools']}}
    if probe.get('catalog'):
        found['seren_catalog'] = probe['catalog']
    try:
        if mcp.get('repository_url'):
            found['repository'] = _repository(mcp['repository_url'])
        if pack.get('homepage_url'):
            found['website'] = {'digest': digest(re.sub(r'\s+', ' ', _page_text(pack['homepage_url'])))}
    except PublisherError:
        pass  # The next run reads this source again.
    return found


def check(records: Records, _args: dict) -> dict:
    changes = []
    for mcp in records.q('SELECT * FROM mcp_server WHERE retired_at IS NULL AND pack_approved_hash IS NOT NULL ORDER BY id'):
        changed = {}
        for source, snapshot in _sources(mcp).items():
            value = digest(snapshot)
            last = records.one('SELECT digest FROM fingerprint WHERE mcp_id = $1 AND source = $2 ORDER BY id DESC LIMIT 1', [mcp['id'], source])
            if last and last['digest'] == value:
                continue
            records.q('INSERT INTO fingerprint (mcp_id, source, digest, snapshot) VALUES ($1, $2, $3, $4::jsonb)',
                      [mcp['id'], source, value, json.dumps(snapshot)])
            if last:
                changed[source] = snapshot
        if changed:
            changes.append({'mcp_id': mcp['id'], 'pack': jsonish(mcp['pack']), 'changed': changed})
    return {'changes': changes}


def confirm_listings(records: Records, _args: dict) -> dict:
    rows = records.q("""SELECT s.id, s.public_url, m.pack FROM submission s JOIN mcp_server m ON m.id = s.mcp_id
                        WHERE s.status = 'listed' AND s.public_url IS NOT NULL AND s.public_url NOT LIKE 'https://github.com/%'
                        ORDER BY s.last_confirmed_at NULLS FIRST LIMIT 30""")
    confirmed, missing = 0, []
    for row in rows:
        try:
            present = jsonish(row['pack'])['name'].lower() in _page_text(row['public_url']).lower()
        except PublisherError:
            continue
        if present:
            records.q('UPDATE submission SET last_confirmed_at = now() WHERE id = $1', [row['id']])
            confirmed += 1
        else:
            missing.append(row['public_url'])
            records.event(row['id'], 'listing_missing', 'The listing page no longer shows this MCP.', row['public_url'])
    return {'confirmed': confirmed, 'missing': missing}


COMMANDS = {'check': check, 'confirm-listings': confirm_listings}
