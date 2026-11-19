# ABOUTME: Grows Regina's directory database: seeds it, searches for new sites and saves what she reads.
# ABOUTME: Sites stay out of the submission queue until their rules are read and their status is active.
from __future__ import annotations

import json
from urllib.parse import urlsplit

from .gateway import PublisherError, StopWork, call
from .records import Records, jsonish
from .seeds import DIRECTORIES

QUERIES = ['directory of MCP servers submit your server', 'list your MCP server marketplace',
           'awesome list of model context protocol servers', 'remote MCP server catalog add server']
ROUTES = ('registry', 'form', 'github_list', 'docker_registry', 'email', 'unknown')
STATUSES = ('active', 'paused', 'rules_unread', 'candidate', 'not_a_target', 'needs_access')


def seed(records: Records) -> None:
    for row in DIRECTORIES:
        records.q("""INSERT INTO directory (key, name, route, site_url, fee_usd, status, source_url, rules)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                     ON CONFLICT (key) DO UPDATE SET rules = EXCLUDED.rules, fee_usd = EXCLUDED.fee_usd
                     WHERE EXCLUDED.rules <> '{}'::jsonb""",
                  [row['key'], row['name'], row['route'], row['site_url'], row['fee_usd'], row['status'],
                   row['source_url'], json.dumps(row['rules'])])


def _host(url: str) -> str:
    return (urlsplit(url).hostname or '').removeprefix('www.')


def discover(records: Records, _args: dict) -> dict:
    seed(records)
    known = {_host(row['site_url']) for row in records.q('SELECT site_url FROM directory')}
    found: dict[str, dict] = {}
    for query in QUERIES:
        hits = []
        try:
            hits += call('exa', 'POST', '/search', body={'query': query, 'numResults': 10}).get('results', [])
            hits += call('firecrawl', 'POST', '/v2/search', body={'query': query, 'limit': 10}).get('data', {}).get('web', [])
        except PublisherError:
            continue
        for hit in hits:
            host = _host(hit.get('url', ''))
            if host and host not in known:
                found.setdefault(host, {'url': hit['url'], 'title': hit.get('title')})
    recheck = records.q("""SELECT key, name, site_url, status FROM directory
                           WHERE status IN ('rules_unread', 'candidate')
                              OR (status = 'paused' AND rules_read_at < now() - interval '7 days') ORDER BY key LIMIT 10""")
    return {'new_sites': list(found.values())[:20], 'recheck': recheck}


def read_page(_records: Records, args: dict) -> dict:
    page = call('firecrawl', 'POST', '/v2/scrape', body={'url': args['url'], 'formats': ['markdown'], 'onlyMainContent': True, 'maxAge': 0})
    return {'url': args['url'], 'text': page.get('data', {}).get('markdown', '')[:30000]}


def save(records: Records, args: dict) -> dict:
    row = args['input']
    if row['route'] not in ROUTES or row['status'] not in STATUSES:
        raise StopWork('directory_invalid', 'route or status is not one of the allowed values')
    saved = records.one("""INSERT INTO directory (key, name, route, site_url, fee_usd, status, source_url, rules)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                           ON CONFLICT (key) DO UPDATE SET name = EXCLUDED.name, route = EXCLUDED.route, site_url = EXCLUDED.site_url,
                             fee_usd = EXCLUDED.fee_usd, status = EXCLUDED.status, source_url = EXCLUDED.source_url,
                             rules = EXCLUDED.rules, rules_read_at = now()
                           RETURNING id""",
                        [row['key'], row['name'], row['route'], row['site_url'], row.get('fee_usd', 0), row['status'],
                         row['source_url'], json.dumps(row.get('rules', {}))])
    return {'directory_id': saved['id']}


def list_directories(records: Records, _args: dict) -> dict:
    rows = records.q('SELECT key, name, route, fee_usd, status, site_url, rules FROM directory ORDER BY status, key')
    return {'directories': [{**row, 'rules': jsonish(row['rules'])} for row in rows]}


COMMANDS = {'discover': discover, 'read-page': read_page, 'save-directory': save, 'list-directories': list_directories}
