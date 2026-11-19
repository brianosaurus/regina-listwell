#!/usr/bin/env python3
# ABOUTME: Packs template/ into Core's agent bundle and writes the release request beside it.
# ABOUTME: Writes out/bundle.json and out/release.json, and refuses a dirty checkout unless told otherwise.
from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'template'
OUT = ROOT / 'out'
SLUG = 'regina-listwell'
DISPLAY_NAME = 'Regina Listwell'
PERSONA = {'IDENTITY.md': 'identity', 'SOUL.md': 'soul', 'AGENTS.md': 'agents', 'HEARTBEAT.md': 'heartbeat'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def instruction(kind: str, path: str, source: Path, skill_name: str | None = None) -> dict:
    text = source.read_text(encoding='utf-8')
    entry = {'kind': kind, 'path': path, 'content': text, 'sha256': digest(text.encode('utf-8'))}
    if skill_name:
        entry['skill_name'] = skill_name
    return entry


def asset(path: str, source: Path, purpose: str, content_type: str) -> dict:
    data = source.read_bytes()
    return {'path': path, 'content_base64': base64.b64encode(data).decode('ascii'), 'sha256': digest(data),
            'purpose': purpose, 'content_type': content_type}


def bundle() -> dict:
    instructions = [instruction('skill', 'SKILL.md', TEMPLATE / 'SKILL.md', 'template')]
    instructions += [instruction(kind, f'persona/{name}', TEMPLATE / 'persona' / name) for name, kind in PERSONA.items()]
    assets = [asset('skill.spec.yaml', TEMPLATE / 'skill.spec.yaml', 'resource', 'application/yaml')]
    assets += [asset(f'regina_lib/{path.name}', path, 'script', 'text/x-python')
               for path in sorted((TEMPLATE / 'regina_lib').glob('*.py'))]
    for skill in sorted(path for path in (TEMPLATE / 'skills').iterdir() if path.is_dir()):
        instructions.append(instruction('skill', f'.skills/{skill.name}/SKILL.md', skill / 'SKILL.md', skill.name))
        assets.append(asset(f'.skills/{skill.name}/scripts/run.py', skill / 'scripts' / 'run.py', 'script', 'text/x-python'))
    return {'instructions': instructions, 'assets': assets}


def requirements() -> str:
    """Core needs each package and all its hashes on one line, with no comments."""
    joined = re.sub(r'\s*\\\n\s*', ' ', (ROOT / 'requirements.lock').read_text(encoding='utf-8'))
    lines = [line.strip() for line in joined.splitlines() if line.strip() and not line.strip().startswith('#')]
    return '\n'.join(lines) + '\n'


def git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    if git('status', '--porcelain') and '--allow-dirty' not in sys.argv:
        print('Commit your work first. A release must match one commit.', file=sys.stderr)
        return 1
    OUT.mkdir(exist_ok=True)
    artifact = json.dumps(bundle(), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    (OUT / 'bundle.json').write_bytes(artifact)
    defaults = yaml.safe_load((ROOT / 'deploy-defaults.yaml').read_text(encoding='utf-8'))
    defaults['requirements_txt'] = requirements()
    release = {'display_name': DISPLAY_NAME, 'source_bundle_id': None, 'source_commit_sha': git('rev-parse', 'HEAD'),
               'deploy_defaults': defaults, 'listed': True}
    (OUT / 'release.json').write_text(json.dumps(release, indent=2), encoding='utf-8')
    print(json.dumps({'slug': SLUG, 'sha256': digest(artifact), 'size_bytes': len(artifact)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
