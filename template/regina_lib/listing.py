# ABOUTME: Holds each MCP's listing pack, the approved facts every submission is built from.
# ABOUTME: A change to the pack's facts marks that MCP's live submissions as needing an update.
from __future__ import annotations

import json

from .directories import seed
from .gateway import StopWork
from .mcp_probe import digest, read_mcp
from .records import Records, jsonish

REQUIRED = ('name', 'short_description', 'description', 'homepage_url', 'mcp_url', 'transport', 'auth', 'contact_email')
TRANSPORTS = ('streamable-http', 'sse')
AUTH = ('none', 'api_key', 'oauth')


def pack_hash(pack: dict) -> str:
    return digest({key: value for key, value in pack.items() if key != 'directory_answers'})


def _check(pack: dict) -> None:
    missing = [key for key in REQUIRED if not pack.get(key)]
    if missing:
        raise StopWork('pack_incomplete', 'The listing pack is missing: ' + ', '.join(missing))
    if len(pack['short_description']) > 100:
        raise StopWork('pack_invalid', 'short_description must be at most 100 characters')
    if pack['transport'] not in TRANSPORTS or pack['auth'] not in AUTH:
        raise StopWork('pack_invalid', 'transport or auth is not one of the allowed values')


def ensure_submissions(records: Records) -> None:
    records.q("""INSERT INTO submission (mcp_id, directory_id)
                 SELECT m.id, d.id FROM mcp_server m CROSS JOIN directory d
                 WHERE m.pack_approved_hash IS NOT NULL AND m.retired_at IS NULL AND d.status = 'active'
                 ON CONFLICT (mcp_id, directory_id) DO NOTHING""")


def add(records: Records, args: dict) -> dict:
    seed(records)
    row = records.one("""INSERT INTO mcp_server (mcp_url, repository_url) VALUES ($1, $2)
                         ON CONFLICT (mcp_url) DO UPDATE SET repository_url = COALESCE(EXCLUDED.repository_url, mcp_server.repository_url)
                         RETURNING id""", [args['url'].strip(), args.get('repository')])
    return {'mcp_id': row['id'], 'probe': read_mcp(args['url'].strip())}


def save_pack(records: Records, args: dict) -> dict:
    mcp_id, pack = int(args['input']['mcp_id']), args['input']['pack']
    _check(pack)
    current = records.one('SELECT pack FROM mcp_server WHERE id = $1', [mcp_id])
    pack['directory_answers'] = jsonish(current['pack']).get('directory_answers', {})
    value = pack_hash(pack)
    records.q('UPDATE mcp_server SET pack = $2::jsonb, pack_hash = $3 WHERE id = $1', [mcp_id, json.dumps(pack), value])
    if args.get('from_change'):
        records.q('UPDATE mcp_server SET pack_approved_hash = $2 WHERE id = $1', [mcp_id, value])
        records.q("""UPDATE submission SET status = 'stale', updated_at = now()
                     WHERE mcp_id = $1 AND status IN ('submitted', 'listed') AND submitted_hash IS DISTINCT FROM $2::text""", [mcp_id, value])
    return {'mcp_id': mcp_id, 'pack_hash': value}


def approve_pack(records: Records, args: dict) -> dict:
    mcp_id = int(args['mcp'])
    records.q('UPDATE mcp_server SET pack_approved_hash = pack_hash WHERE id = $1 AND pack_hash IS NOT NULL', [mcp_id])
    ensure_submissions(records)
    return {'mcp_id': mcp_id, 'approved': True}


def save_answers(records: Records, args: dict) -> dict:
    """Stores a directory's special facts. They don't change the pack's hash."""
    mcp_id, key, answers = int(args['input']['mcp_id']), args['input']['directory_key'], args['input']['answers']
    pack = jsonish(records.one('SELECT pack FROM mcp_server WHERE id = $1', [mcp_id])['pack'])
    pack.setdefault('directory_answers', {}).setdefault(key, {}).update(answers)
    records.q('UPDATE mcp_server SET pack = $2::jsonb WHERE id = $1', [mcp_id, json.dumps(pack)])
    directory = records.one('SELECT id FROM directory WHERE key = $1', [key])
    records.q("UPDATE owner_request SET status = 'answered' WHERE mcp_id = $1 AND directory_id = $2 AND status = 'open'", [mcp_id, directory['id']])
    records.q("UPDATE submission SET status = 'queued', updated_at = now() WHERE mcp_id = $1 AND directory_id = $2 AND status = 'needs_owner'",
              [mcp_id, directory['id']])
    return {'mcp_id': mcp_id, 'directory_key': key}


def list_mcps(records: Records, _args: dict) -> dict:
    rows = records.q('SELECT id, mcp_url, repository_url, pack, pack_hash, pack_approved_hash FROM mcp_server WHERE retired_at IS NULL ORDER BY id')
    open_requests = records.q("SELECT id, mcp_id, directory_id, question FROM owner_request WHERE status = 'open' ORDER BY id")
    return {'mcps': [{**row, 'pack': jsonish(row['pack'])} for row in rows], 'open_requests': open_requests}


COMMANDS = {'add-mcp': add, 'save-pack': save_pack, 'approve-pack': approve_pack, 'save-answers': save_answers, 'list-mcps': list_mcps}
