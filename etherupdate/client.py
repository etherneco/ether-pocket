#!/usr/bin/python3
"""Local CLI and read-only stdio MCP. D-Bus derives caller identity."""
import argparse
import json
import sys
import dbus
NAME='com.etherneco.EtherUpdate1'
TOOLS={
 'etherupdate_get_status':lambda s:s,
 'etherupdate_list_installed':lambda s:s.get('installed',{}),
 'etherupdate_get_history':lambda s:s.get('history',[]),
 'etherupdate_get_update_details':lambda s:s.get('discovery',{}),
 'etherupdate_get_health':lambda s:[t for t in s.get('history',[]) if t['document'].get('health')],
 'etherupdate_get_recovery_status':lambda s:s.get('recovery',{})}


def api():return dbus.Interface(dbus.SystemBus().get_object(NAME,'/com/etherneco/EtherUpdate1'),NAME)


def mcp():
    # No network listener or privileged token. OS-authenticated D-Bus read access.
    for raw in sys.stdin:
        message={}
        try:
            if len(raw)>65536:raise ValueError('Request too large')
            message=json.loads(raw);method=message['method']
            if method.startswith('notifications/'):continue
            if method=='initialize':result=dict(protocolVersion='2024-11-05',capabilities=dict(tools={}),serverInfo=dict(name='etherupdate-local-readonly',version='0.1.0'))
            elif method=='tools/list':result=dict(tools=[dict(name=k,description='Read local update state; no installation authority',inputSchema=dict(type='object',properties={},additionalProperties=False),annotations=dict(readOnlyHint=True)) for k in TOOLS])
            elif method=='tools/call':
                params=message['params']
                if params.get('arguments'):raise ValueError('No arguments supported')
                result=dict(content=[dict(type='text',text=json.dumps(TOOLS[params['name']](json.loads(str(api().GetState(timeout=5))))))])
            else:raise ValueError('Read-only adapter: operation unavailable')
            response=dict(jsonrpc='2.0',id=message.get('id'),result=result)
        except Exception:response=dict(jsonrpc='2.0',id=message.get('id'),error=dict(code=-32601,message='Request rejected or local service unavailable'))
        print(json.dumps(response),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['state','check','download','prepare','install-approved','cancel','mcp']);parser.add_argument('value',nargs='?')
    args=parser.parse_args()
    if args.command=='mcp':mcp()
    else:
        method={'state':'GetState','check':'CheckUpdates','download':'Download','prepare':'PrepareInstall','install-approved':'InstallApproved','cancel':'CancelDownload'}[args.command]
        print(getattr(api(),method)(*([args.value] if args.value else []),timeout=3600))
