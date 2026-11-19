# ABOUTME: Runs a paid directory listing: quotes the price, opens the checkout and hands it to the hirer.
# ABOUTME: Regina never touches the pay button; the hirer finishes the payment in the live window.
from __future__ import annotations

import os
from urllib.parse import quote, urlsplit

from . import forms
from .gateway import StopWork
from .records import Records, jsonish


def _row(records: Records, args: dict) -> dict:
    row = records.one("""SELECT s.id AS submission_id, m.id AS mcp_id, m.pack, m.pack_hash, d.key, d.name, d.fee_usd, d.rules
                         FROM submission s JOIN mcp_server m ON m.id = s.mcp_id JOIN directory d ON d.id = s.directory_id
                         WHERE s.mcp_id = $1 AND d.key = $2""", [int(args['mcp']), args['directory']])
    if not row:
        raise StopWork('listing_not_found', 'That MCP and directory have no submission.')
    return row


def _checkout(row: dict) -> dict:
    checkout = jsonish(row['rules']).get('checkout')
    if not checkout:
        raise StopWork('checkout_not_captured', f"{row['name']}'s checkout has not been set up in this release.")
    return checkout


def quote_listing(records: Records, args: dict) -> dict:
    row = _row(records, args)
    return {'directory': row['name'], 'fee_usd': str(row['fee_usd']), 'ready': bool(jsonish(row['rules']).get('checkout'))}


def card_link(records: Records, args: dict) -> dict:
    checkout = _checkout(_row(records, args))
    hosts = quote(','.join(checkout['card_hosts']), safe=',')
    deployment = os.environ['SEREN_CLOUD_DEPLOYMENT_ID']
    return {'link': f'https://passwords.serendb.com/agents/{deployment}/logins/new?kind=card&alias=listing_card&hosts={hosts}&name=Listing%20card'}


def checkout(records: Records, args: dict) -> dict:
    if not args.get('hirer_said_yes'):
        raise StopWork('needs_yes', 'Quote the price and get the hirer\'s yes first.')
    row = _row(records, args)
    rules, details = jsonish(row['rules']), _checkout(row)
    pack = jsonish(row['pack'])
    answers = pack.get('directory_answers', {}).get(row['key'], {})
    from seren_browser import request_browser_handoff

    with forms.open_page() as page:
        forms.fill(page, rules['form'], pack, answers, chat=True)
        page.click(rules['form']['submit'])
        page.wait_for_url(lambda url: urlsplit(url).hostname in details['card_hosts'], timeout=60000)
        ended = request_browser_handoff(page, 'owner_submit', [forms.origin(page.url)], [details['success_url_prefix']])
    if ended.get('status') != 'completed':
        raise StopWork('payment_not_finished', f"The pay window ended: {ended.get('status')}")
    records.q('INSERT INTO payment (submission_id, amount_usd, receipt_url) VALUES ($1, $2, $3)',
              [row['submission_id'], row['fee_usd'], args.get('receipt')])
    records.set_submission(row['submission_id'], 'submitted', submitted_hash=row['pack_hash'])
    records.event(row['submission_id'], 'paid', f"Paid ${row['fee_usd']} to {row['name']}.")
    return {'paid': True, 'amount_usd': str(row['fee_usd'])}


COMMANDS = {'quote-listing': quote_listing, 'card-link': card_link, 'checkout': checkout}
