# ABOUTME: Reads directory replies from the hirer's Gmail or Outlook and sends messages the hirer approves.
# ABOUTME: Each send is byte-for-byte repeatable, because Seren restarts the script after the hirer approves.
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote

from .gateway import call, post_file

CONNECTION_HEADER = 'X-Seren-OAuth-Connection-Id'
APPROVAL_HEADER = 'X-Seren-Approval-Review'


def context() -> dict:
    request = urllib.request.Request(os.environ['SEREN_PUBLISHER_PROXY_URL'].rstrip('/') + '/managed-agent/context')
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def _review(to: str, subject: str) -> str:
    review = {'to': [to], 'cc': [], 'bcc': [], 'subject': subject, 'attachments': [],
              'consequences': ['The email is sent from your mailbox and cannot be recalled.']}
    return base64.urlsafe_b64encode(json.dumps(review, sort_keys=True, separators=(',', ':')).encode('utf-8')).decode('ascii')


def _gmail_text(part: dict) -> str:
    data = part.get('body', {}).get('data')
    if part.get('mimeType') == 'text/plain' and data:
        return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', 'replace')
    return ''.join(_gmail_text(child) for child in part.get('parts', []))


def recent(domains: list[str], days: int = 3) -> list[dict]:
    """Messages from the given domains, as plain dictionaries."""
    info = context()
    headers = {CONNECTION_HEADER: info['oauth_connection_id']}
    since = datetime.now(timezone.utc) - timedelta(days=days)
    wanted = tuple(f'@{domain}' for domain in domains)
    if info['mail_provider'] == 'gmail':
        terms = ' OR '.join(f'from:{domain}' for domain in domains)
        listing = call('gmail', 'GET', '/messages', query={'q': f'after:{int(since.timestamp())} ({terms})', 'maxResults': 50}, headers=headers)
        found = []
        for item in listing.get('messages') or []:
            full = call('gmail', 'GET', f"/messages/{item['id']}", query={'format': 'full'}, headers=headers)
            fields = {h['name'].lower(): h['value'] for h in full.get('payload', {}).get('headers', [])}
            found.append({'id': item['id'], 'thread': full.get('threadId'), 'from': fields.get('from', ''), 'subject': fields.get('subject', ''),
                          'message_id': fields.get('message-id'), 'text': _gmail_text(full.get('payload', {}))[:4000]})
        return found
    stamp = since.strftime('%Y-%m-%dT%H:%M:%SZ')
    path = f"/me/messages?$filter={quote('receivedDateTime ge ' + stamp)}&$select=id,conversationId,subject,from,bodyPreview,internetMessageId&$top=50"
    listing = call('microsoft-outlook', 'GET', path, headers=headers)
    found = []
    for item in listing.get('value') or []:
        sender = item.get('from', {}).get('emailAddress', {}).get('address', '').lower()
        if sender.endswith(wanted):
            found.append({'id': item['id'], 'thread': item.get('conversationId'), 'from': sender, 'subject': item.get('subject', ''),
                          'message_id': item.get('internetMessageId'), 'text': item.get('bodyPreview', '')})
    return found


def send(draft_id: int, to: str, subject: str, text: str, thread: dict) -> None:
    info = context()
    headers = {CONNECTION_HEADER: info['oauth_connection_id'], APPROVAL_HEADER: _review(to, subject)}
    name = f'reply-{draft_id}.json'
    if info['mail_provider'] == 'gmail':
        mime = EmailMessage()
        mime['To'], mime['Subject'] = to, subject
        mime['Message-ID'] = f"<{hashlib.sha256(f'{draft_id}:{subject}'.encode('utf-8')).hexdigest()[:40]}@serendb.com>"
        if thread.get('message_id'):
            mime['In-Reply-To'] = mime['References'] = thread['message_id']
        mime.set_content(text)
        body = {'raw': base64.urlsafe_b64encode(mime.as_bytes()).decode('ascii')}
        if thread.get('thread'):
            body['threadId'] = thread['thread']
        post_file('gmail', '/messages/send', body, name, headers)
        return
    body = {'message': {'subject': subject, 'body': {'contentType': 'Text', 'content': text},
                        'toRecipients': [{'emailAddress': {'address': to}}], 'ccRecipients': [], 'attachments': []},
            'saveToSentItems': True}
    post_file('microsoft-outlook', '/me/sendMail', body, name, headers)
