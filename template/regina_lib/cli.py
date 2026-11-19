# ABOUTME: Runs one named command and prints one JSON object for Regina to read.
# ABOUTME: Each command is a function taking her records and the parsed arguments.
from __future__ import annotations

import importlib
import json
import sys

from .gateway import PublisherError, StopWork
from .records import Records

COMMANDS = {}


def _load() -> None:
    for name in ('listing', 'directories', 'routes', 'registry', 'fingerprints', 'answers', 'paid', 'report'):
        COMMANDS.update(importlib.import_module(f'regina_lib.{name}').COMMANDS)


def _parse(argv: list[str]) -> dict:
    args, index = {}, 0
    while index < len(argv):
        key = argv[index].removeprefix('--').replace('-', '_')
        if index + 1 < len(argv) and not argv[index + 1].startswith('--'):
            args[key], index = argv[index + 1], index + 2
        else:
            args[key], index = True, index + 1
    return args


def main(argv: list[str]) -> int:
    command, args = argv[0], _parse(argv[1:])
    try:
        _load()
        if args.pop('stdin', False):
            args['input'] = json.load(sys.stdin)
        if args.pop('stdin_text', False):
            args['text'] = sys.stdin.read()
        result = COMMANDS[command](Records().open(), args)
    except StopWork as stop:
        print(json.dumps({'ok': False, 'code': stop.code, 'message': str(stop)}))
        return 0
    except PublisherError as error:
        print(json.dumps({'ok': False, 'code': error.code, 'publisher': error.publisher, 'status': error.status}))
        return 1
    print(json.dumps({'ok': True, **result}, default=str))
    return 0
