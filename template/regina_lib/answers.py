# ABOUTME: Collects directory replies, records what each one means, and sends the replies Regina drafts.
# ABOUTME: Directory text is returned as untrusted information for her to read and classify.
from __future__ import annotations

import json
from urllib.parse import urlsplit

from . import mail
from .gateway import PublisherError, StopWork, call
from .records import Records, jsonish

OUTCOMES = ('accepted', 'needs_info', 'rejected', 'no_answer')


def _pull_items(records: Records, row: dict) -> list[dict]:
    pull = jsonish(row['external']).get('pull')
    if not pull:
        return []
    base = f"/repos/{pull['owner']}/{pull['repo']}"
    state = call('github-api', 'GET', f"{base}/pulls/{pull['number']}")
    if state.get('merged_at'):
        records.set_submission(row['id'], 'listed', public_url=f"https://github.com/{pull['owner']}/{pull['repo']}#readme")
        records.q('UPDATE submission SET last_confirmed_at = now() WHERE id = $1', [row['id']])
        records.event(row['id'], 'answer_accepted', 'The pull request was merged.', state['html_url'], f"merged-{pull['number']}")
        return []
    reviews = call('github-api', 'GET', f"{base}/pulls/{pull['number']}/reviews")
    comments = call('github-api', 'GET', f"{base}/issues/{pull['number']}/comments")
    items = [{'submission_id': row['id'], 'source': 'github', 'external_id': f"review-{item['id']}", 'from': item['user']['login'],
              'text': (item.get('body') or item.get('state') or '')[:4000], 'link': item['html_url']} for item in reviews]
    items += [{'submission_id': row['id'], 'source': 'github', 'external_id': f"comment-{item['id']}", 'from': item['user']['login'],
               'text': (item.get('body') or '')[:4000], 'link': item['html_url']} for item in comments]
    if state.get('state') == 'closed':
        items.append({'submission_id': row['id'], 'source': 'github', 'external_id': f"closed-{pull['number']}", 'from': 'github',
                      'text': 'The pull request was closed without merging.', 'link': state['html_url']})
    return items


def collect(records: Records, _args: dict) -> dict:
    rows = records.q("""SELECT s.id, s.external, d.site_url, d.rules, m.pack FROM submission s
                        JOIN directory d ON d.id = s.directory_id JOIN mcp_server m ON m.id = s.mcp_id
                        WHERE s.status IN ('submitted', 'needs_owner', 'rejected')""")
    items = []
    by_domain: dict[str, dict] = {}
    for row in rows:
        try:
            items += _pull_items(records, row)
        except PublisherError:
            continue
        host = (urlsplit(row['site_url']).hostname or '').removeprefix('www.')
        if host and host != 'github.com':
            by_domain.setdefault(host, row)
    if by_domain:
        for message in mail.recent(sorted(by_domain)):
            domain = message['from'].split('@')[-1].strip('> ').lower()
            row = next((value for key, value in by_domain.items() if domain.endswith(key)), None)
            if row:
                items.append({'submission_id': row['id'], 'source': 'email', 'external_id': f"mail-{message['id']}", 'from': message['from'],
                              'subject': message['subject'], 'text': message['text'],
                              'thread': {'thread': message['thread'], 'message_id': message['message_id']}})
    seen = {row['external_id'] for row in records.q('SELECT external_id FROM submission_event WHERE external_id IS NOT NULL')}
    return {'items': [item for item in items if item['external_id'] not in seen]}


def record(records: Records, args: dict) -> dict:
    item = args['input']
    if item['outcome'] not in OUTCOMES:
        raise StopWork('outcome_invalid', 'Use accepted, needs_info, rejected or no_answer.')
    submission_id = int(item['submission_id'])
    if not records.event(submission_id, f"answer_{item['outcome']}", item['summary'], item.get('link'), item['external_id']):
        return {'already_recorded': True}
    if item['outcome'] == 'accepted':
        records.set_submission(submission_id, 'listed', public_url=item.get('public_url'))
    elif item['outcome'] == 'rejected':
        records.q("UPDATE submission SET status = 'rejected', rejections = rejections + 1, updated_at = now() WHERE id = $1", [submission_id])
    elif item['outcome'] == 'needs_info':
        records.set_submission(submission_id, 'needs_owner')
    count = records.one('SELECT rejections FROM submission WHERE id = $1', [submission_id])['rejections']
    return {'rejections': count, 'stop_and_ask_hirer': count >= 2}


def draft(records: Records, args: dict) -> dict:
    item = args['input']
    if item['channel'] not in ('github', 'email'):
        raise StopWork('channel_invalid', 'Use github or email.')
    row = records.one("""INSERT INTO reply_draft (submission_id, channel, recipient, subject, body, thread)
                         VALUES ($1, $2, $3, $4, $5, $6::jsonb) RETURNING id""",
                      [int(item['submission_id']), item['channel'], item.get('recipient'), item.get('subject'), item['body'],
                       json.dumps(item.get('thread', {}))])
    return {'draft_id': row['id']}


def send(records: Records, args: dict) -> dict:
    row = records.one("SELECT * FROM reply_draft WHERE id = $1 AND status = 'draft'", [int(args['draft'])])
    if not row:
        raise StopWork('draft_not_found', 'That draft was already sent or does not exist.')
    if row['channel'] == 'github':
        pull = jsonish(records.one('SELECT external FROM submission WHERE id = $1', [row['submission_id']])['external'])['pull']
        call('github-api', 'POST', f"/repos/{pull['owner']}/{pull['repo']}/issues/{pull['number']}/comments", body={'body': row['body']})
    else:
        mail.send(row['id'], row['recipient'], row['subject'], row['body'], jsonish(row['thread']))
    records.q("UPDATE reply_draft SET status = 'sent' WHERE id = $1", [row['id']])
    records.q("""UPDATE submission SET status = 'submitted', updated_at = now(),
                 submitted_hash = (SELECT pack_hash FROM mcp_server WHERE mcp_server.id = submission.mcp_id)
                 WHERE id = $1 AND status = 'needs_owner'""", [row['submission_id']])
    records.event(row['submission_id'], 'reply_sent', f"Replied by {row['channel']}.")
    return {'sent': True}


COMMANDS = {'collect': collect, 'record-answer': record, 'draft-reply': draft, 'send-reply': send}
