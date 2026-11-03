"""Read the supplied distributor through MCP. Credentials never enter output."""
from pathlib import Path
import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
import sys

ROOT=Path(__file__).resolve().parent.parent
USER_AGENT='EtherShell-Autoupdate/1.0 (+https://etherneco.com)'

def redact_payload(value):
    """Drop account data returned unnecessarily by management serializers."""
    if isinstance(value,dict):
        return {key:('[OMITTED]' if key.lower() in {'owner','user','password','two_factor_secret','access_token','refresh_token','remember_token'} else redact_payload(item)) for key,item in value.items()}
    if isinstance(value,list): return [redact_payload(item) for item in value]
    if isinstance(value,str) and value.lstrip().startswith(('{','[')):
        try: return json.dumps(redact_payload(json.loads(value)),ensure_ascii=False)
        except ValueError: pass
    return value

class HTTPFailure(RuntimeError):
    def __init__(self,status,ray,body):
        self.status=status
        self.ray=ray
        try: self.details=json.loads(body)
        except ValueError: self.details={}
        self.cloudflare=self.details.get('error_code')==1010 or 'error 1010' in body.lower()
        super().__init__(f'HTTP {status}; cf-ray={ray}; '+('Cloudflare 1010: required owner rule.' if self.cloudflare else 'Request rejected.'))

class SameOriginRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, target):
        old=urllib.parse.urlsplit(request.full_url)
        new=urllib.parse.urlsplit(target)
        if new.scheme!='https' or new.netloc!=old.netloc:
            raise RuntimeError('Refusing distributor redirect to another origin.')
        return super().redirect_request(request,response,code,message,headers,target)

class MCP:
    def __init__(self):
        self.secret=json.loads((ROOT/'build/autoupdate-credential.json').read_text())
        self.endpoint=self.secret['base_url']+'/api/mcp'
        self.auth_mode='bearer'
        self.session=None
        self.counter=0
        self.protocol='2024-11-05'
        self.opener=urllib.request.build_opener(SameOriginRedirects)
        initialized=self.request('initialize',{'protocolVersion':self.protocol,'capabilities':{},'clientInfo':{'name':'EtherShell-discovery','version':'0.1.1'}})
        if 'error' in initialized: raise RuntimeError('MCP initialize returned an error.')
        self.protocol=initialized.get('result',{}).get('protocolVersion',self.protocol)
        self.request('notifications/initialized',{},notification=True)

    def request(self,method,params,notification=False):
        payload={'jsonrpc':'2.0','method':method,'params':params}
        if not notification:
            self.counter+=1
            payload['id']=self.counter
        headers={'User-Agent':USER_AGENT,'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':self.protocol}
        endpoint=self.endpoint
        if self.auth_mode=='bearer': headers['Authorization']='Bearer '+self.secret['token']
        else: endpoint+='?'+urllib.parse.urlencode({'token':self.secret['token']})
        if self.session: headers['Mcp-Session-Id']=self.session
        request=urllib.request.Request(endpoint,json.dumps(payload).encode(),headers)
        try:
            with self.opener.open(request,timeout=40) as response:
                print(json.dumps({'method':method,'status':response.status,'cf-ray':response.headers.get('cf-ray','unavailable'),'auth':self.auth_mode}),file=sys.stderr)
                self.session=response.headers.get('Mcp-Session-Id',self.session)
                if 'text/event-stream' in response.headers.get('Content-Type',''):
                    lines=[]
                    for raw in response:
                        line=raw.decode().rstrip('\r\n')
                        if line.startswith('data:'): lines.append(line[5:].lstrip())
                        elif not line and lines:
                            item=json.loads('\n'.join(lines));lines=[]
                            if item.get('id')==payload.get('id'): return item
                    return {}
                data=response.read().decode()
                if not data.strip(): return {}
                return json.loads(data)
        except urllib.error.HTTPError as error:
            body=error.read().decode(errors='replace').replace(self.secret['token'],'[REDACTED]')
            failure=HTTPFailure(error.code,error.headers.get('cf-ray','unavailable'),body)
            print(json.dumps({'method':method,'status':failure.status,'cf-ray':failure.ray,'auth':self.auth_mode,'cloudflare_1010':failure.cloudflare}),file=sys.stderr)
            if failure.cloudflare: raise failure from None
            # Only retry authentication if the server explicitly rejects Bearer.
            if error.code==401 and self.auth_mode=='bearer':
                self.auth_mode='query'
                return self.request(method,params,notification)
            raise failure from None
        except urllib.error.URLError as error:
            raise RuntimeError('Connection failed: '+str(error.reason).replace(self.secret['token'],'[REDACTED]')) from None

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--tool')
    parser.add_argument('--args',default='{}')
    parser.add_argument('--output')
    opts=parser.parse_args()
    try: client=MCP()
    except RuntimeError as error:
        print(str(error),file=sys.stderr)
        raise SystemExit(1)
    result=client.request('tools/call',{'name':opts.tool,'arguments':json.loads(opts.args)}) if opts.tool else client.request('tools/list',{})
    output=json.dumps(redact_payload(result),indent=2,ensure_ascii=False).replace(client.secret['token'],'[REDACTED]')
    if opts.output: Path(opts.output).write_text(output,encoding='utf-8')
    else: print(output)
