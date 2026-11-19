# ABOUTME: Builds Regina's one daily report and records it after Seren confirms delivery.
# ABOUTME: Wording comes only from this file, so the report stays consistent from day to day.
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .records import Records, jsonish

LIMIT = 20000


def _lines(rows: list[dict], render) -> list[str]:
    return [render(row) for row in rows] or ['- Nothing today.']


def build(records: Records, args: dict) -> dict:
    today = datetime.now(ZoneInfo(args['timezone'])).date().isoformat()
    if records.one('SELECT id FROM daily_report WHERE local_date = $1::date AND sent_at IS NOT NULL', [today]):
        return {'already_sent': True}
    listed = records.q("""SELECT m.pack, d.name, s.status, s.public_url, s.last_confirmed_at FROM submission s
                          JOIN mcp_server m ON m.id = s.mcp_id JOIN directory d ON d.id = s.directory_id
                          WHERE s.status IN ('listed', 'submitted') ORDER BY m.id, d.name""")
    events = records.q("""SELECT e.kind, e.summary, e.link, d.name FROM submission_event e JOIN submission s ON s.id = e.submission_id
                          JOIN directory d ON d.id = s.directory_id WHERE e.at > now() - interval '24 hours' ORDER BY e.id""")
    questions = records.q("SELECT question FROM owner_request WHERE status = 'open' ORDER BY id")
    found = records.q("SELECT name, status FROM directory WHERE rules_read_at > now() - interval '24 hours' ORDER BY name")
    paid = records.q("SELECT p.amount_usd, d.name FROM payment p JOIN submission s ON s.id = p.submission_id JOIN directory d ON d.id = s.directory_id WHERE p.paid_at > now() - interval '24 hours'")
    delivered = [e for e in events if e['kind'] in ('submitted', 'updated', 'registry_published', 'paid')]
    replies = [e for e in events if e['kind'].startswith('answer_') or e['kind'] == 'reply_sent']
    sections = [
        ('Where you\'re listed', _lines(listed, lambda r: f"- {jsonish(r['pack']).get('name')} on {r['name']}: {r['status']}, {r['public_url'] or 'link pending'}, last confirmed {r['last_confirmed_at'] or 'not yet'}")),
        ('Delivered today', _lines(delivered, lambda e: f"- {e['name']}: {e['summary']} {e['link'] or ''}".rstrip())),
        ('Rejections and replies', _lines(replies, lambda e: f"- {e['name']}: {e['summary']} {e['link'] or ''}".rstrip())),
        ('Waiting on you', _lines(questions, lambda q: f"- {q['question']}")),
        ('New directories found', _lines(found, lambda d: f"- {d['name']} ({d['status']})")),
        ('Spending', _lines(paid, lambda p: f"- ${p['amount_usd']} to {p['name']}")),
    ]
    body = '\n\n'.join(title + '\n' + '\n'.join(lines) for title, lines in sections)[:LIMIT]
    records.q("""INSERT INTO daily_report (local_date, body) VALUES ($1::date, $2)
                 ON CONFLICT (local_date) DO UPDATE SET body = EXCLUDED.body""", [today, body])
    subject = f'Your MCP listings: {len(listed)} live or submitted, {len(delivered)} delivered today'
    return {'subject': subject, 'report': body, 'local_date': today}


def record(records: Records, args: dict) -> dict:
    today = datetime.now(ZoneInfo(args['timezone'])).date().isoformat()
    row = records.one('SELECT body FROM daily_report WHERE local_date = $1::date', [today])
    matches = bool(row) and row['body'] == args.get('text')
    records.q('UPDATE daily_report SET sent_at = now() WHERE local_date = $1::date', [today])
    return {'recorded': True, 'matches_built': matches}


COMMANDS = {'build-report': build, 'record-report': record}
