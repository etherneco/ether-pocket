"""Explicit submit only geocoding and profile-specific OSRM routing adapters."""
import hashlib
import json
import time
import urllib.request
from urllib.parse import urlencode, urlsplit
from core import Rejected, atomic, number
from ip_provider import endpoint
from maps import NoRedirect
from domain import coordinates


class Providers:
    def __init__(self, root):
        self.root=root
        self.last=0

    def request(self, url, consent):
        if consent is not True:raise Rejected('External search/routing consent required; queries disclose locations to the configured server')
        endpoint(url)
        now=time.monotonic()
        if now-self.last<1.1:raise Rejected('Wait at least one second between requests')
        self.last=now
        req=urllib.request.Request(url,headers={'User-Agent':'EtherMAP/0.1 (Etherneco LTD)','Accept':'application/json'})
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=15) as response:raw=response.read(2*1024**2+1)
        if len(raw)>2*1024**2:raise Rejected('Provider response too large')
        return json.loads(raw)

    def search(self, query, url, consent):
        if not 2<=len(query)<=200:raise Rejected('Enter 2–200 search characters')
        endpoint(url)
        if consent is not True:raise Rejected('External geocoder consent required')
        key=hashlib.sha256((url+'\n'+query).encode()).hexdigest()
        cache=self.root/(key+'.json')
        try:
            data=json.loads(cache.read_text())
            if 0<=time.time()-data['time']<86400:return data['results']
        except (OSError,ValueError,KeyError):pass
        rows=self.request(url+('&' if '?' in url else '?')+urlencode({'q':query,'format':'jsonv2','limit':8}),consent)
        if not isinstance(rows,list):raise Rejected('Expected Nominatim-compatible results')
        results=[dict(coordinates(p['lat'],p['lon']),name=str(p['display_name'])[:300],source='geocoder') for p in rows[:8]]
        atomic(cache,dict(time=time.time(),results=results))
        # Bounded cache and local deletion are independent of track retention.
        for path in sorted(self.root.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[100:]:path.unlink()
        return results

    def route(self, start, end, url, consent):
        endpoint(url)
        if urlsplit(url).query:raise Rejected('Routing endpoint must be a profile-specific OSRM /route/v1/<profile> URL')
        a=coordinates(start['latitude'],start['longitude']);b=coordinates(end['latitude'],end['longitude'])
        coords=f"{a['longitude']},{a['latitude']};{b['longitude']},{b['latitude']}"
        data=self.request(url.rstrip('/')+'/'+coords+'?overview=full&geometries=geojson&steps=true',consent)
        if data.get('code')!='Ok' or not data.get('routes'):raise Rejected('Routing provider returned no route')
        route=data['routes'][0]
        points=route['geometry']['coordinates']
        if not 2<=len(points)<=100000:raise Rejected('Invalid route geometry size')
        line=[coordinates(p[1],p[0]) for p in points]
        steps=[]
        for leg in route.get('legs',[])[:100]:
            for s in leg.get('steps',[])[:1000]:
                m=s.get('maneuver',{})
                steps.append(dict(text=' '.join(str(v) for v in (m.get('type',''),m.get('modifier',''),s.get('name','')) if v)[:300],distance=number(s.get('distance',0),0,1e8)))
        return dict(line=line,steps=steps,distance=number(route['distance'],0,1e8),duration=number(route['duration'],0,1e8),traffic=False,offline=False)
