# ABOUTME: Fills a directory's web form in Regina's browser from a saved map of its fields.
# ABOUTME: A human check is handed to the hirer in the live window, and only during a chat.
from __future__ import annotations

import os
from contextlib import contextmanager
from urllib.parse import urlsplit

from .gateway import StopWork

CHALLENGE = 'iframe[src*="challenges.cloudflare.com"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]'


@contextmanager
def open_page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(os.environ['SEREN_PLAYWRIGHT_CDP_URL'], timeout=60000)
        context = browser.contexts[0]
        yield context.pages[0] if context.pages else context.new_page()


def origin(url: str) -> str:
    parts = urlsplit(url)
    return f'{parts.scheme}://{parts.netloc}'


def clear_human_check(page, chat: bool) -> None:
    if not page.locator(CHALLENGE).count():
        return
    if not chat:
        raise StopWork('human_check_needed', 'This site needs a human check. Ask the hirer in chat.')
    from seren_browser import request_browser_handoff

    here = origin(page.url)
    ended = request_browser_handoff(page, 'challenge', [here], [here])
    if ended.get('status') != 'completed':
        raise StopWork('human_check_not_finished', f"The live window ended: {ended.get('status')}")


def _value(field: dict, pack: dict, answers: dict):
    source = field.get('from', '')
    return answers.get(source[8:]) if source.startswith('answers.') else pack.get(source)


def fill(page, form: dict, pack: dict, answers: dict, chat: bool) -> None:
    page.goto(form['url'], wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(3000)
    clear_human_check(page, chat)
    for field in form['fields']:
        value = _value(field, pack, answers)
        if field['kind'] == 'click':
            page.click(field['selector'])
        elif value in (None, ''):
            raise StopWork('form_value_missing', f"No value for {field.get('from')}")
        elif field['kind'] == 'select':
            page.select_option(field['selector'], value=str(value))
        else:
            page.fill(field['selector'], str(value))


def submit_free(form: dict, pack: dict, answers: dict, chat: bool) -> dict:
    with open_page() as page:
        fill(page, form, pack, answers, chat)
        page.click(form['submit'])
        page.wait_for_timeout(8000)
        clear_human_check(page, chat)
        if page.locator('form :invalid').count():
            raise StopWork('form_invalid', 'The site refused the form: ' + page.inner_text('body')[:600])
        return {'url': page.url, 'text': page.inner_text('body')[:1500]}
