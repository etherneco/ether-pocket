"""Opt-in physical failure tests. Uses the already enabled cellular session.

Run only after verifying USB SSH and Wi-Fi recovery. No radio, firmware,
gadget or modem reset. A finally block restores cellular data and stops sharing.
"""
from pathlib import Path
import json,runpy,shlex,subprocess,time
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
PRELUDE="""import dbus,json,pathlib,subprocess,time
assert pathlib.Path('/etc/etherpocket/disk-identity').read_text().strip()=='GM1920-548cb338-mobian-sda21'
api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1')
"""

def remote(source,timeout=50):
    r=subprocess.run(SSH+['python3 -c '+shlex.quote(PRELUDE+source)],capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr[-2500:])
    return json.loads(r.stdout)

def request(text):
    # Exercise the normal user's PolicyKit path, rather than a root-only test API.
    code=PRELUDE+text
    return remote("r=subprocess.run(['/usr/sbin/runuser','-u','mobian','--','python3','-c',"+repr(code)+"],capture_output=True,text=True,timeout=80);assert r.returncode==0,r.stderr;print(json.dumps({'ok':True}))",90)

def traffic():
    r=subprocess.run(['curl.exe','-4','--interface','10.77.0.1','--noproxy','*','--max-time','5','--silent','--output','NUL','--write-out','%{http_code} %{size_download}','https://1.1.1.1/cdn-cgi/trace'],capture_output=True,text=True,timeout=8)
    return dict(exit=r.returncode,result=r.stdout)

if __name__=='__main__':
    results={}
    try:
        request("api.Stop('all',timeout=60);api.Configure(json.dumps({'upstream':'epcell0','failover':False,'autostart':False}),timeout=20);api.Start('usb','usb0',False,timeout=60)")
        results['lte_usb_before']=traffic();assert results['lte_usb_before']['exit']==0
        results['data_stop']=remote("r=subprocess.run(['systemctl','stop','ethermobile-data'],capture_output=True,text=True,timeout=40);print(json.dumps({'exit':r.returncode,'owned_interface_removed':not pathlib.Path('/sys/class/net/epcell0').exists()}))",45)
        assert results['data_stop']['owned_interface_removed']
        request("api.Refresh(timeout=60)")
        results['no_upstream']=remote("d=json.loads(api.GetState());print(json.dumps({'active':d['active'],'wifi_still_connected':'10.1.' in subprocess.check_output(['ip','-4','addr','show','wlan0'],text=True)}))")
        results['no_bypass']=traffic();assert results['no_bypass']['exit']!=0
        remote("subprocess.run(['systemctl','start','ethermobile-data'],check=True);time.sleep(3);print(json.dumps({'data_active':subprocess.run(['systemctl','is-active','ethermobile-data'],capture_output=True).returncode==0}))")
        request("api.Refresh(timeout=60)")
        results['lte_usb_recovered']=traffic();assert results['lte_usb_recovered']['exit']==0
        results['crash_restart']=remote("subprocess.run(['systemctl','kill','--signal=SIGKILL','ethershare'],check=True);time.sleep(5);api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherShare1','/com/etherneco/EtherShare1'),'com.etherneco.EtherShare1');print(json.dumps({'active':json.loads(api.GetState())['active'],'forward':pathlib.Path('/proc/sys/net/ipv4/ip_forward').read_text().strip(),'foreign_routes_preserved':bool(subprocess.check_output(['ip','route','show','default'],text=True)),'owned_rules_left':'ESH' in subprocess.check_output(['/usr/sbin/iptables-legacy-save'],text=True)}))")
        assert not results['crash_restart']['active'] and not results['crash_restart']['owned_rules_left']
        results['passed']=True
    finally:
        try:
            remote("subprocess.run(['systemctl','start','ethermobile-data'],check=True);print(json.dumps({'restored':True}))")
            request("api.Stop('all',timeout=60);api.Configure(json.dumps({'upstream':'auto','failover':False,'autostart':False}),timeout=20)")
        finally:
            (ROOT/'evidence/ethershare-recovery-tests.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,indent=2))
