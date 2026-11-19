# ABOUTME: Walks the submission queue and sends each MCP to each directory by that directory's route.
# ABOUTME: Anything that needs the hirer becomes one open question instead of a failed run.
from __future__ import annotations

from . import forms, github_lists
from .gateway import PublisherError, StopWork
from .listing import ensure_submissions
from .records import Records, jsonish


def _missing(rules: dict, pack: dict, answers: dict, open_endpoint: bool) -> list[tuple[str, str]]:
    missing = [(ask['key'], ask['question']) for ask in rules.get('asks', []) if not answers.get(ask['key'])]
    if rules.get('requires_repository') and not pack.get('repository_url'):
        missing.append(('repository', 'This directory needs a public GitHub repository for this MCP. Is there one?'))
    if rules.get('requires_open_endpoint') and not open_endpoint:
        missing.append(('endpoint', 'This directory checks that the MCP answers without signing in, and this one requires sign-in.'))
    return missing


def _open_endpoint(records: Records, mcp_id: int) -> bool:
    row = records.one("SELECT snapshot FROM fingerprint WHERE mcp_id = $1 AND source = 'mcp_tools' ORDER BY id DESC LIMIT 1", [mcp_id])
    return bool(row) and jsonish(row['snapshot']).get('status') == 'ok'


def _send(records: Records, row: dict, pack: dict, rules: dict, answers: dict, updating: bool, chat: bool) -> dict:
    route, version = row['route'], row['pack_hash']
    if route == 'github_list':
        return github_lists.submit_list(rules, pack, answers, version, updating)
    if route == 'docker_registry':
        return github_lists.submit_docker(rules, pack, answers, version, updating)
    if route == 'form' and not updating:
        page = forms.submit_free(rules['form'], pack, answers, chat)
        return {'status': 'submitted', 'public_url': None, 'external': {'page': page['url']}, 'page_text': page['text']}
    raise StopWork('no_route', f'No way to send {route} here.')


def _work_one(records: Records, row: dict, chat: bool) -> dict:
    submission_id, mcp_id = row['submission_id'], row['mcp_id']
    pack, rules = jsonish(row['pack']), jsonish(row['rules'])
    answers = pack.get('directory_answers', {}).get(row['key'], {})
    updating = row['submission_status'] == 'stale'
    missing = _missing(rules, pack, answers, _open_endpoint(records, mcp_id))
    if missing:
        for _, question in missing:
            records.ask(mcp_id, row['id'], f"{row['name']}: {question}")
        records.set_submission(submission_id, 'needs_owner')
        return {'result': 'needs_owner', 'questions': [question for _, question in missing]}
    if row['route'] == 'registry':
        records.ask(mcp_id, row['id'], f"{row['name']}: I need you for one minute to approve a GitHub sign-in code. Tell me when you're ready.")
        records.set_submission(submission_id, 'needs_owner')
        return {'result': 'needs_owner', 'next': 'registry-start in a chat'}
    if rules.get('paid') and not updating:
        records.ask(mcp_id, row['id'], f"{row['name']}: listing costs ${row['fee_usd']}. Do you want it?")
        records.set_submission(submission_id, 'needs_owner')
        return {'result': 'needs_owner', 'next': 'paid-listing'}
    if row['route'] == 'form' and updating:
        update = rules.get('update') or {}
        if update.get('kind') != 'email':
            records.event(submission_id, 'no_update_path', f"{row['name']} has no way to update a listing.")
            records.set_submission(submission_id, 'listed', submitted_hash=row['pack_hash'])
            return {'result': 'no_update_path'}
        records.set_submission(submission_id, 'needs_owner')
        return {'result': 'draft_update_email', 'to': update['to']}
    sent = _send(records, row, pack, rules, answers, updating, chat)
    records.set_submission(submission_id, sent['status'], submitted_hash=row['pack_hash'], public_url=sent.get('public_url'), external=sent['external'])
    records.event(submission_id, 'updated' if updating else 'submitted', f"Sent to {row['name']}.", sent.get('public_url'))
    return {'result': sent['status'], 'link': sent.get('public_url'), 'page_text': sent.get('page_text')}


def submit_work(records: Records, args: dict) -> dict:
    ensure_submissions(records)
    rows = records.q("""SELECT s.id AS submission_id, s.status AS submission_status, m.id AS mcp_id, m.pack, m.pack_hash,
                               d.id, d.key, d.name, d.route, d.fee_usd, d.rules
                        FROM submission s JOIN mcp_server m ON m.id = s.mcp_id JOIN directory d ON d.id = s.directory_id
                        WHERE s.status IN ('queued', 'stale') AND d.status = 'active' AND m.retired_at IS NULL
                          AND m.pack_approved_hash = m.pack_hash ORDER BY s.id LIMIT $1""", [int(args.get('limit', 20))])
    results = []
    for row in rows:
        entry = {'submission_id': row['submission_id'], 'directory': row['name']}
        try:
            entry.update(_work_one(records, row, bool(args.get('chat'))))
        except StopWork as stop:
            records.event(row['submission_id'], 'blocked', str(stop))
            entry.update({'result': 'blocked', 'code': stop.code, 'message': str(stop)})
        except PublisherError as error:
            entry.update({'result': 'failed', 'code': error.code, 'publisher': error.publisher})
        results.append(entry)
    return {'results': results}


COMMANDS = {'submit-work': submit_work, **github_lists.COMMANDS}
