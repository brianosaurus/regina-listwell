# ABOUTME: Regina's records in the hire's own Seren database: MCPs, directories, submissions and reports.
# ABOUTME: Rows are never deleted, because Core refuses DELETE; retired rows carry retired_at.
from __future__ import annotations

import json

from .gateway import call

DATABASE = 'mcp_listings'

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS mcp_server (id bigserial PRIMARY KEY, mcp_url text NOT NULL UNIQUE, repository_url text,
       pack jsonb NOT NULL DEFAULT '{}', pack_hash text, pack_approved_hash text, retired_at timestamptz,
       created_at timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS directory (id bigserial PRIMARY KEY, key text NOT NULL UNIQUE, name text NOT NULL,
       route text NOT NULL, site_url text NOT NULL, fee_usd numeric NOT NULL DEFAULT 0, status text NOT NULL,
       rules jsonb NOT NULL DEFAULT '{}', source_url text, rules_read_at timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS submission (id bigserial PRIMARY KEY, mcp_id bigint NOT NULL, directory_id bigint NOT NULL,
       status text NOT NULL DEFAULT 'queued', submitted_hash text, public_url text, external jsonb NOT NULL DEFAULT '{}',
       rejections integer NOT NULL DEFAULT 0, last_confirmed_at timestamptz, updated_at timestamptz NOT NULL DEFAULT now(),
       UNIQUE (mcp_id, directory_id))""",
    """CREATE TABLE IF NOT EXISTS submission_event (id bigserial PRIMARY KEY, submission_id bigint NOT NULL, kind text NOT NULL,
       external_id text, summary text NOT NULL, link text, at timestamptz NOT NULL DEFAULT now())""",
    """CREATE UNIQUE INDEX IF NOT EXISTS submission_event_once ON submission_event (submission_id, kind, external_id)
       WHERE external_id IS NOT NULL""",
    """CREATE TABLE IF NOT EXISTS fingerprint (id bigserial PRIMARY KEY, mcp_id bigint NOT NULL, source text NOT NULL,
       digest text NOT NULL, snapshot jsonb NOT NULL DEFAULT '{}', at timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS owner_request (id bigserial PRIMARY KEY, mcp_id bigint NOT NULL, directory_id bigint,
       question text NOT NULL, answer text, status text NOT NULL DEFAULT 'open', at timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS reply_draft (id bigserial PRIMARY KEY, submission_id bigint NOT NULL, channel text NOT NULL,
       recipient text, subject text, body text NOT NULL, thread jsonb NOT NULL DEFAULT '{}', status text NOT NULL DEFAULT 'draft',
       at timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS payment (id bigserial PRIMARY KEY, submission_id bigint NOT NULL, amount_usd numeric NOT NULL,
       receipt_url text, paid_at timestamptz NOT NULL DEFAULT now())""",
    """CREATE TABLE IF NOT EXISTS daily_report (id bigserial PRIMARY KEY, local_date date NOT NULL UNIQUE, body text NOT NULL,
       sent_at timestamptz)""",
]


def jsonish(value):
    """A jsonb column can come back parsed or as text."""
    return json.loads(value) if isinstance(value, str) else (value if value is not None else {})


class Records:
    def open(self) -> 'Records':
        call('seren-db', 'POST', '/databases', body={'name': DATABASE})
        for statement in SCHEMA:
            self.q(statement)
        return self

    def q(self, sql: str, params: list | None = None) -> list[dict]:
        body = {'managed_agent_database': DATABASE, 'query': sql}
        if params:
            body['params'] = params
        result = call('seren-db', 'POST', '/query', body=body)
        columns, rows = result.get('columns') or [], result.get('rows') or []
        return [dict(zip(columns, row)) for row in rows]

    def one(self, sql: str, params: list | None = None) -> dict | None:
        rows = self.q(sql, params)
        return rows[0] if rows else None

    def event(self, submission_id: int, kind: str, summary: str, link: str | None = None, external_id: str | None = None) -> bool:
        """Records one event. Returns False when this external item was already recorded."""
        rows = self.q("""INSERT INTO submission_event (submission_id, kind, summary, link, external_id) VALUES ($1, $2, $3, $4, $5)
                         ON CONFLICT DO NOTHING RETURNING id""", [submission_id, kind, summary, link, external_id])
        return bool(rows)

    def ask(self, mcp_id: int, directory_id: int | None, question: str) -> None:
        """Adds one open question for the hirer, once."""
        if not self.one("SELECT id FROM owner_request WHERE mcp_id = $1 AND question = $2 AND status = 'open'", [mcp_id, question]):
            self.q('INSERT INTO owner_request (mcp_id, directory_id, question) VALUES ($1, $2, $3)', [mcp_id, directory_id, question])

    def set_submission(self, submission_id: int, status: str, submitted_hash: str | None = None,
                       public_url: str | None = None, external: dict | None = None) -> None:
        self.q("""UPDATE submission SET status = $2, submitted_hash = COALESCE($3, submitted_hash),
                  public_url = COALESCE($4, public_url), external = COALESCE($5::jsonb, external), updated_at = now()
                  WHERE id = $1""", [submission_id, status, submitted_hash, public_url,
                                     json.dumps(external) if external is not None else None])
