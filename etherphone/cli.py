#!/usr/bin/python3
"""Explicit session-bus client. Never dials by default."""
import argparse,json,os
import dbus
def main():
    p=argparse.ArgumentParser(description='EtherPhone native telephony; calls/audio unverified')
    p.add_argument('action',choices=['state','diagnostics','command'])
    p.add_argument('--operation');p.add_argument('--target',default='');p.add_argument('--data',default='{}')
    a=p.parse_args()
    api=dbus.Interface(dbus.SessionBus().get_object('com.etherneco.EtherPhone1','/com/etherneco/EtherPhone1'),'com.etherneco.EtherPhone1')
    if a.action=='state':print(str(api.GetState(timeout=5)))
    else:
        if a.action=='command' and not a.operation:p.error('--operation is required')
        print(str(api.Command('diagnostics' if a.action=='diagnostics' else a.operation,a.target,a.data,timeout=45)))
if __name__=='__main__':
    os.umask(0o077);main()
