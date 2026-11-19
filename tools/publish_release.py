#!/usr/bin/env python3
# ABOUTME: Uploads out/bundle.json to Seren and publishes out/release.json as the next template revision.
# ABOUTME: Reads SEREN_ORG_ID, SEREN_OWNER_KEY and SEREN_PUBLISH_KEY from the environment and never prints them.
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from pathlib import Path

API = 'https://api.serendb.com'
BUNDLES = '/publishers/seren-cloud/deployment-bundles'
OUT = Path(__file__).resolve().parents[1] / 'out'
SLUG = 'regina-listwell'


def call(method: str, path: str, key: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode('utf-8') if payload is not None else b''
    request = urllib.request.Request(API + path, data=body, method=method, headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())['data']


def main() -> int:
    org, owner_key, publish_key = (os.environ[name] for name in ('SEREN_ORG_ID', 'SEREN_OWNER_KEY', 'SEREN_PUBLISH_KEY'))
    artifact = (OUT / 'bundle.json').read_bytes()
    registered = call('POST', BUNDLES, owner_key, {'sha256': hashlib.sha256(artifact).hexdigest(),
                                                   'size_bytes': len(artifact), 'source_kind': 'agent_bundle'})
    bundle_id = registered['deployment_bundle_id']
    if registered.get('upload_required'):
        upload = urllib.request.Request(registered['upload_url'], data=artifact, method='PUT',
                                        headers=registered.get('upload_headers') or {})
        urllib.request.urlopen(upload, timeout=300).close()
    call('POST', f'{BUNDLES}/{bundle_id}/complete', owner_key)
    release = json.loads((OUT / 'release.json').read_text(encoding='utf-8'))
    release['source_bundle_id'] = bundle_id
    published = call('POST', f'/organizations/{org}/templates/{SLUG}/releases', publish_key, release)
    print(json.dumps({'bundle_id': bundle_id, 'revision': published.get('revision'), 'active': published.get('active')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
