"""Consented IP estimates. No default endpoint, keys, observations or GNSS claims."""
import json
import math
import time
import urllib.request
from urllib.parse import urlsplit
from core import Rejected, atomic, number, disclose
from maps import NoRedirect


def endpoint(value):
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.fragment:
        raise Rejected('Configure a direct HTTPS IP provider URL without credentials')
    return value


def disclose_ip(result, precision, grid):
    if precision!='approximate':return dict(result)
    unknown=result.get('accuracy') is None
    out=disclose(dict(result,accuracy=result.get('accuracy') or 0.01),precision,grid)
    if unknown:out['accuracy']=None
    return out


class IpProvider:
    """JSON contract: latitude, longitude, optional accuracy metres/city/region/country.

    Cache for one hour, at most one request per 15 minutes including failures.
    State is persisted so restarting the application cannot defeat the limit.
    """
    def __init__(self, path):
        self.path = path

    def lookup(self, url, consent=False, now=None):
        if not consent:
            raise Rejected('Explicit external IP geolocation consent required')
        endpoint(url)
        now = time.time() if now is None else now
        try:
            cache = json.loads(self.path.read_text())
        except (OSError, ValueError):
            cache = {}
        p = cache.get('position') if cache.get('url') == url else None
        if cache.get('url') == url:
            if p and 0 <= now-p['timestamp'] < 3600:
                return dict(p, cached=True, age=now-p['timestamp'])
            if now-cache.get('attempt', 0) < 900:
                if p and 0<=now-p['timestamp']<=7*86400:return dict(p,cached=True,stale=True,age=now-p['timestamp'])
                raise Rejected('IP provider rate limited; retry after 15 minutes')
        cache = dict(url=url, attempt=now, **({'position':p} if p else {}))
        atomic(self.path, cache)
        request = urllib.request.Request(url, headers={'User-Agent': 'EtherMAP/0.1 (Etherneco LTD)', 'Accept': 'application/json'})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
                raw = response.read(65537)
        except OSError:
            if p and 0<=now-p['timestamp']<=7*86400:return dict(p,cached=True,stale=True,age=now-p['timestamp'])
            raise
        if len(raw) > 65536:
            raise Rejected('IP response too large')
        row = json.loads(raw)
        p = dict(latitude=number(row['latitude'], -90, 90), longitude=number(row['longitude'], -180, 180),
                 timestamp=now, provider='ip', kind='approximate-region', precision='approximate',
                 service=urlsplit(url).hostname, accuracy=None)
        if row.get('accuracy') is not None:
            p['accuracy'] = number(row['accuracy'], 1, 10000000)
        for key in ('city', 'region', 'country'):
            if isinstance(row.get(key), str):
                p[key] = row[key][:120]
        atomic(self.path, dict(cache, position=p))
        return p
