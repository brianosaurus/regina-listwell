#!/usr/bin/env python3
# ABOUTME: Opens a real browser, records one checkout you complete by hand, and prints its addresses.
# ABOUTME: Its output fills in guarded_submissions, network_egress and the directory's checkout rules.
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main() -> int:
    url, har = sys.argv[1], Path('out/checkout.har')
    har.parent.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(record_har_path=str(har))
        context.new_page().goto(url)
        input('Fill the form, pay in the browser, wait for the success page, then press Enter here. ')
        pages = [page.url for page in context.pages]
        context.close()
        browser.close()
    entries = [entry for entry in json.loads(har.read_text(encoding='utf-8'))['log']['entries']
               if entry['request']['url'].startswith('http')]
    posts = sorted({(urlsplit(e['request']['url']).hostname, urlsplit(e['request']['url']).path)
                    for e in entries if e['request']['method'] == 'POST'})
    hosts = sorted({urlsplit(e['request']['url']).hostname for e in entries})
    print(json.dumps({'final_pages': pages, 'hosts': hosts, 'posts': posts}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
