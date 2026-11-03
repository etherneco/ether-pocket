"""Typed adapter for the audited Laravel routes; no publication methods."""
from dataclasses import dataclass
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from security import Rejected

BASE = 'https://autoupddate.etherneco.com'
CHANNELS = ('Stable', 'Beta', 'Nightly', 'Experimental')


class ProviderError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProviderError('Untrusted redirect refused')


@dataclass(frozen=True)
class Release:
    project: str
    channel: str
    version: str
    notes: str
    url: str
    sha256: str
    size: int
    envelope: dict


class Provider:
    def __init__(self, token='', base=BASE):
        if base != BASE: raise Rejected('Only the authoritative AutoUpdate origin is supported')
        self.base, self.token = base, token
        self.opener = urllib.request.build_opener(NoRedirect())
        self.counter = 0

    def open(self, url, data=None, extra=None):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != urllib.parse.urlsplit(self.base).netloc or parsed.username or parsed.fragment:
            raise Rejected('Artifact origin is not trusted')
        # Download links must never carry a credential in the query string.
        if any(k.lower() in ('token', 'api_key', 'apikey', 'access_token') for k, _ in urllib.parse.parse_qsl(parsed.query)):
            raise Rejected('Credential in URL refused')
        headers = {'Accept': 'application/json', 'User-Agent': 'EtherUpdate/0.1 (+https://etherneco.com)'}
        if self.token: headers['Authorization'] = 'Bearer ' + self.token
        if extra: headers.update(extra)
        try:
            return self.opener.open(urllib.request.Request(url, data, headers), timeout=30)
        except urllib.error.HTTPError as e:
            raise ProviderError('Authentication failed' if e.code in (401,403) else 'Project not found' if e.code == 404 else 'Server unavailable (HTTP %d)' % e.code) from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError):
            raise ProviderError('Offline or TLS connection failed') from None

    def json(self, path, data=None):
        with self.open(self.base + path, data, {'Content-Type':'application/json'}) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024: raise ProviderError('Metadata response too large')
            try: return json.loads(raw)
            except ValueError: raise ProviderError('Invalid server metadata') from None

    def projects(self):
        result = []
        # Optional public endpoints silently narrow invalid credentials to the
        # public shelf. Use the protected route when a credential was supplied
        # so an expired/revoked token cannot masquerade as an empty catalog.
        route = '/api/manage/projects' if self.token else '/api/projects'
        for page in range(1, 101):
            data = self.json(route+'?page=' + str(page))
            result.extend({k:p.get(k) for k in ('id','slug','name','platform')} for p in data['data'])
            if page >= data['last_page']: return result
        raise ProviderError('Project pagination exceeded limit')

    def latest(self, project, channel):
        if channel not in CHANNELS: raise Rejected('Unknown channel')
        data = self.json('/api/releases/check?' + urllib.parse.urlencode({'project':project, 'channel':channel}))
        if data.get('latest') is None: return None
        artifact = data.get('artifact') or {}
        return Release(project, channel, str(data['latest']), str(data.get('release_notes') or '')[:32000],
                       data.get('download_url') or '', data.get('sha256') or '', int(artifact.get('size') or 0),
                       (data.get('metadata') or {}).get('etherupdate') or {})

    def mcp_discover(self):
        def rpc(method, params):
            self.counter += 1
            result = self.json('/api/mcp', json.dumps(dict(jsonrpc='2.0', id=self.counter, method=method, params=params)).encode())
            if 'error' in result: raise ProviderError('MCP request rejected')
            return result['result']
        initialized = rpc('initialize', dict(protocolVersion='2024-11-05', capabilities={}, clientInfo=dict(name='EtherUpdate',version='0.1.0')))
        self.json_notification()
        return dict(initialize=initialized, tools=rpc('tools/list', {}), resources=rpc('resources/list', {}))

    def json_notification(self):
        with self.open(self.base+'/api/mcp', json.dumps(dict(jsonrpc='2.0',method='notifications/initialized')).encode(), {'Content-Type':'application/json'}): pass
