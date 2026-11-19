# ABOUTME: Adds or updates an MCP in a GitHub-hosted list by opening a pull request from the hirer's fork.
# ABOUTME: Covers the two awesome lists' README entries and the Docker MCP Registry's server folder.
from __future__ import annotations

import json
import re
import time
from urllib.parse import quote, urlsplit

from .gateway import PublisherError, StopWork, call, post_file
from .sandbox import Sandbox

AGENT_TITLE_MARK = ' 🤖🤖🤖'


def _branch_head(owner: str, repo: str, branch: str) -> tuple[str, str]:
    head = call('github-api', 'GET', f"/repos/{owner}/{repo}/branches/{quote(branch, safe='')}")
    return head['commit']['sha'], head['commit']['commit']['tree']['sha']


def _fork(owner: str, repo: str) -> str:
    full_name = call('github-api', 'POST', f'/repos/{owner}/{repo}/forks', body={'default_branch_only': True})['full_name']
    for _ in range(30):
        try:
            call('github-api', 'GET', f'/repos/{full_name}')
            return full_name
        except PublisherError as error:
            if error.status != 404:
                raise
            time.sleep(10)
    raise StopWork('fork_not_ready', f'GitHub has not finished forking {owner}/{repo}.')


def _commit(fork: str, base_commit: str, base_tree: str, files: dict[str, str], message: str) -> str:
    tree = []
    for index, (path, text) in enumerate(files.items()):
        blob = post_file('github-api', f'/repos/{fork}/git/blobs', {'content': text, 'encoding': 'utf-8'}, f'blob-{index}.json')
        tree.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    new_tree = call('github-api', 'POST', f'/repos/{fork}/git/trees', body={'base_tree': base_tree, 'tree': tree})
    return call('github-api', 'POST', f'/repos/{fork}/git/commits',
                body={'message': message, 'tree': new_tree['sha'], 'parents': [base_commit]})['sha']


def _open_pull(rules: dict, files: dict[str, str], base: tuple[str, str], slug: str, version: str, title: str, body: str) -> dict:
    owner, repo = rules['owner'], rules['repo']
    fork = _fork(owner, repo)
    branch = f'listing/{slug}-{version[:8]}'
    sha = _commit(fork, base[0], base[1], files, title)
    try:
        call('github-api', 'POST', f'/repos/{fork}/git/refs', body={'ref': f'refs/heads/{branch}', 'sha': sha})
    except PublisherError as error:
        if error.status != 422:
            raise
        raise StopWork('branch_exists', f'{branch} already exists, so this version was already submitted.') from None
    pull = call('github-api', 'POST', f'/repos/{owner}/{repo}/pulls', body={
        'title': title + AGENT_TITLE_MARK, 'head': f"{fork.split('/')[0]}:{branch}", 'base': rules['branch'], 'body': body})
    return {'status': 'submitted', 'public_url': pull['html_url'],
            'external': {'pull': {'owner': owner, 'repo': repo, 'number': pull['number']}}}


def slug_of(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40]


def read_upstream(owner: str, repo: str, sha: str, path: str = 'README.md') -> str:
    source = f'https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}'
    code = f"import urllib.request\nurllib.request.urlretrieve({source!r}, '/tmp/upstream.md')\nprint('done')"
    with Sandbox() as box:
        box.python(code)
        return box.download('/tmp/upstream.md', f'upstream-{repo}.md').read_text(encoding='utf-8')


def sections(readme: str) -> list[dict]:
    found = re.findall(r'^### .*?<a name="([^"]+)"></a>(.*)$', readme, flags=re.MULTILINE)
    return [{'anchor': anchor, 'title': title.strip()} for anchor, title in found]


def entry_lines(rules: dict, pack: dict, answers: dict) -> tuple[list[str], str]:
    sentence = pack['short_description'].rstrip('.') + '.'
    if rules['format'] == 'local':
        link = pack['repository_url'].rstrip('/')
        name = urlsplit(link).path.strip('/')
        return [f"- [{name}]({link}) {answers['markers']} - {sentence}"], f'({link})'
    connector, name, link = answers['connector'], pack['name'], pack['homepage_url']
    marker = {'none': '🔓', 'api_key': '🔑', 'oauth': '🔐'}[pack['auth']]
    return [f"- [{name}]({link}) `{pack['mcp_url']}`",
            f'  [![{name} MCP connector](https://glama.ai/mcp/connectors/{connector}/badges/score.svg)](https://glama.ai/mcp/connectors/{connector})',
            f'  {marker} - {sentence}'], f'({link})'


def upsert_entry(readme: str, anchor: str, lines: list[str], link: str) -> str:
    rows = readme.split('\n')
    for index, row in enumerate(rows):
        if row.startswith('- [') and link in row:
            end = index + 1
            while end < len(rows) and rows[end].startswith('  '):
                end += 1
            del rows[index:end]
            break
    start = next((i for i, row in enumerate(rows) if row.startswith('### ') and f'name="{anchor}"' in row), None)
    if start is None:
        raise StopWork('section_not_found', f'The list has no section named {anchor}.')
    end = next((i for i in range(start + 1, len(rows)) if rows[i].startswith('#')), len(rows))
    key = lines[0][3:].split(']')[0].lower()
    position = None
    for index in range(start + 1, end):
        if rows[index].startswith('- [') and rows[index][3:].split(']')[0].lower() > key:
            position = index
            break
    if position is None:
        position = end
        while position > start + 1 and not rows[position - 1].strip():
            position -= 1
    rows[position:position] = lines
    return '\n'.join(rows)


def submit_list(rules: dict, pack: dict, answers: dict, version: str, updating: bool) -> dict:
    base = _branch_head(rules['owner'], rules['repo'], rules['branch'])
    readme = read_upstream(rules['owner'], rules['repo'], base[0])
    lines, link = entry_lines(rules, pack, answers)
    updated = upsert_entry(readme, answers['section'], lines, link)
    verb = 'Update' if updating else 'Add'
    title = f"{verb} {pack['name']}"
    body = f"{pack['description']}\n\nHomepage: {pack['homepage_url']}\nMCP endpoint: {pack['mcp_url']}"
    return _open_pull(rules, {'README.md': updated}, base, slug_of(pack['name']), version, title, body)


def list_sections(_records, args: dict) -> dict:
    owner, repo, branch = args['owner'], args['repo'], args.get('branch', 'main')
    return {'sections': sections(read_upstream(owner, repo, _branch_head(owner, repo, branch)[0]))}


def docker_files(pack: dict, answers: dict, name: str) -> dict[str, str]:
    host = urlsplit(pack['homepage_url']).hostname
    lines = [f'name: {name}', 'type: remote']
    if pack['auth'] == 'oauth':
        lines += ['dynamic:', '  tools: true']
    lines += ['meta:', f"  category: {answers['docker_category']}", '  tags:', f"    - {answers['docker_category']}", '    - remote',
              'about:', f"  title: {json.dumps(pack['name'])}", f"  description: {json.dumps(pack['short_description'])}",
              f'  icon: https://www.google.com/s2/favicons?domain={host}&sz=64',
              'remote:', f"  transport_type: {pack['transport']}", f"  url: {pack['mcp_url']}"]
    if pack['auth'] == 'oauth':
        env = name.upper().replace('-', '_')
        lines += ['oauth:', f'  - provider: {name}', f'    secret: {name}.personal_access_token', f'    env: {env}_PERSONAL_ACCESS_TOKEN']
    return {f'servers/{name}/server.yaml': '\n'.join(lines) + '\n', f'servers/{name}/tools.json': '[]\n',
            f'servers/{name}/readme.md': f"Docs: {pack['homepage_url']}\n"}


def submit_docker(rules: dict, pack: dict, answers: dict, version: str, updating: bool) -> dict:
    name = slug_of(pack['name'])
    base = _branch_head(rules['owner'], rules['repo'], rules['branch'])
    verb = 'Update' if updating else 'Add'
    title = f"{verb} {pack['name']} remote server"
    return _open_pull(rules, docker_files(pack, answers, name), base, name, version, title, pack['description'])


COMMANDS = {'list-sections': list_sections}
