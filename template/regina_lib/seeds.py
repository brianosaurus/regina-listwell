# ABOUTME: The directories Regina starts with, as read from each site on 2026-11-18.
# ABOUTME: Each hire copies these into its own database and keeps growing the list from there.
from __future__ import annotations

_CATEGORIES = ['development', 'productivity', 'database', 'search', 'web-scraping', 'file-system', 'version-control',
               'communication', 'cloud-service', 'cloud-storage', 'marketing', 'finance', 'design', 'memory', 'other']
_SECTION = {'key': 'section', 'question': 'Which section of the list fits this MCP? Give the anchor name from `list-sections`.'}


def _unread(key: str, name: str, site_url: str, status: str = 'rules_unread') -> dict:
    return {'key': key, 'name': name, 'route': 'unknown', 'site_url': site_url, 'fee_usd': 0, 'status': status,
            'source_url': site_url, 'rules': {}}


DIRECTORIES = [
    {'key': 'official-registry', 'name': 'Official MCP Registry', 'route': 'registry',
     'site_url': 'https://registry.modelcontextprotocol.io', 'fee_usd': 0, 'status': 'active',
     'source_url': 'https://modelcontextprotocol.io/registry/quickstart', 'rules': {}},
    {'key': 'mcpservers-org', 'name': 'mcpservers.org', 'route': 'form', 'site_url': 'https://mcpservers.org',
     'fee_usd': 0, 'status': 'active', 'source_url': 'https://mcpservers.org/submit', 'rules': {
         'asks': [{'key': 'category', 'question': 'Which mcpservers.org category fits this MCP?', 'choices': _CATEGORIES}],
         'update': {'kind': 'email', 'to': 'contact@mcpservers.org'},
         'form': {'url': 'https://mcpservers.org/submit', 'submit': 'form button[type=submit]', 'fields': [
             {'selector': '#server-name', 'kind': 'fill', 'from': 'name'},
             {'selector': '#server-category', 'kind': 'select', 'from': 'answers.category'},
             {'selector': '#server-description', 'kind': 'fill', 'from': 'short_description'},
             {'selector': '#server-url', 'kind': 'fill', 'from': 'homepage_url'},
             {'selector': 'label[for="has-remote"]', 'kind': 'click'},
             {'selector': '#contact-email', 'kind': 'fill', 'from': 'contact_email'}]}}},
    {'key': 'mcp-so', 'name': 'mcp.so', 'route': 'form', 'site_url': 'https://mcp.so', 'fee_usd': 39, 'status': 'active',
     'source_url': 'https://mcp.so/submit', 'rules': {
         'paid': True, 'requires_repository': True,
         'form': {'url': 'https://mcp.so/submit', 'submit': 'form button[type=submit]', 'fields': [
             {'selector': 'form input[type=url]', 'kind': 'fill', 'from': 'repository_url'},
             {'selector': 'form input[placeholder="Project name"]', 'kind': 'fill', 'from': 'name'}]}}},
    {'key': 'awesome-mcp-servers', 'name': 'awesome-mcp-servers', 'route': 'github_list',
     'site_url': 'https://github.com/punkpeye/awesome-mcp-servers', 'fee_usd': 0, 'status': 'active',
     'source_url': 'https://github.com/punkpeye/awesome-mcp-servers/blob/main/CONTRIBUTING.md', 'rules': {
         'owner': 'punkpeye', 'repo': 'awesome-mcp-servers', 'branch': 'main', 'format': 'local', 'requires_repository': True,
         'asks': [_SECTION, {'key': 'markers', 'question': 'Which legend icons describe this MCP, such as the language and cloud icons?'}]}},
    {'key': 'awesome-remote-mcp-servers', 'name': 'awesome-remote-mcp-servers', 'route': 'github_list',
     'site_url': 'https://github.com/punkpeye/awesome-remote-mcp-servers', 'fee_usd': 0, 'status': 'active',
     'source_url': 'https://github.com/punkpeye/awesome-remote-mcp-servers/blob/main/CONTRIBUTING.md', 'rules': {
         'owner': 'punkpeye', 'repo': 'awesome-remote-mcp-servers', 'branch': 'main', 'format': 'remote', 'requires_open_endpoint': True,
         'asks': [_SECTION,
                  {'key': 'connector', 'question': 'What is this MCP\'s Glama connector identifier, such as io.example/name? List it at glama.ai/mcp/connectors first.'},
                  {'key': 'starred', 'question': 'Please star github.com/punkpeye/awesome-remote-mcp-servers from your connected GitHub account, then tell me when it\'s done. The list only merges pull requests from accounts that starred it.'}]}},
    {'key': 'docker-mcp-registry', 'name': 'Docker MCP Registry', 'route': 'docker_registry',
     'site_url': 'https://github.com/docker/mcp-registry', 'fee_usd': 0, 'status': 'active',
     'source_url': 'https://github.com/docker/mcp-registry/blob/main/CONTRIBUTING.md', 'rules': {
         'owner': 'docker', 'repo': 'mcp-registry', 'branch': 'main',
         'asks': [{'key': 'docker_category', 'question': 'Which one-word Docker category fits this MCP, such as productivity or documentation?'}]}},
    _unread('pulsemcp', 'PulseMCP', 'https://www.pulsemcp.com/submit', 'paused'),
    _unread('modelcontextprotocol-servers', 'modelcontextprotocol/servers', 'https://github.com/modelcontextprotocol/servers', 'not_a_target'),
    _unread('glama', 'Glama', 'https://glama.ai/mcp/servers'),
    _unread('smithery', 'Smithery', 'https://smithery.ai'),
    _unread('cursor-directory', 'cursor.directory', 'https://cursor.directory/mcp/new'),
    _unread('mcp-market', 'MCP Market', 'https://mcpmarket.com/submit', 'candidate'),
    _unread('mcp-catalog', 'MCP Catalog', 'https://mcpcatalog.dev/about', 'candidate'),
    _unread('mcp-directory', 'mcp.directory', 'https://mcp.directory', 'candidate'),
    _unread('cline-marketplace', 'Cline MCP Marketplace', 'https://github.com/cline/mcp-marketplace', 'candidate'),
    _unread('lobehub', 'LobeHub MCP', 'https://lobehub.com/mcp', 'candidate'),
    _unread('claudepluginhub', 'Claude Plugin Hub', 'https://claudepluginhub.com', 'candidate'),
    _unread('cursor-marketplace', 'Cursor Marketplace', 'https://cursor.com/marketplace', 'candidate'),
    _unread('gemini-extensions', 'Gemini CLI Extensions', 'https://geminicli.com/extensions', 'candidate'),
]
