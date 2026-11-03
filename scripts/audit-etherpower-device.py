"""Read-only physical power audit and USB-powered baseline; no suspend or load."""
from pathlib import Path
import json,runpy,shlex,subprocess
ROOT=Path(__file__).resolve().parent.parent
SSH=runpy.run_path(str(ROOT/'scripts/deploy-ethermobile.py'))['SSH']
SOURCE=r'''
import datetime,gzip,json,pathlib,subprocess,time
def read(p):
 try:return pathlib.Path(p).read_text().replace('\0','').strip()
 except OSError:return None
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=8);return {'exit':p.returncode,'output':p.stdout[:30000]}
def files(base,fields):return {str(p):{k:read(p/k) for k in fields} for p in pathlib.Path(base).glob('*')}
power_fields=['type','status','present','online','capacity','health','voltage_now','current_now','input_current_now','temp','charge_counter','charge_full','charge_full_design','cycle_count','charge_control_start_threshold','charge_control_end_threshold','charge_control_limit','charge_control_limit_max','charging_enabled','pd_active','typec_mode','typec_power_role','real_type','input_suspend']
def sample():return {'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'supplies':files('/sys/class/power_supply',power_fields),'load':read('/proc/loadavg')}
data={'kernel':read('/proc/sys/kernel/osrelease'),'model':read('/proc/device-tree/model'),
 'power':{k:read('/sys/power/'+k) for k in ['state','mem_sleep','wakeup_reasons/last_resume_reason']},
 'supplies':files('/sys/class/power_supply',power_fields),
 'policies':files('/sys/devices/system/cpu/cpufreq',['related_cpus','scaling_governor','scaling_available_governors','scaling_available_frequencies','scaling_min_freq','scaling_max_freq','cpuinfo_min_freq','cpuinfo_max_freq','scaling_cur_freq']),
 'devfreq':files('/sys/class/devfreq',['name','governor','available_governors','available_frequencies','min_freq','max_freq','cur_freq']),
 'thermal':files('/sys/class/thermal',['type','temp','mode','cur_state','max_state']),
 'backlights':files('/sys/class/backlight',['brightness','actual_brightness','max_brightness','bl_power','type']),
 'wake':{str(p):read(p) for p in pathlib.Path('/sys/devices').glob('platform/soc/*/power/wakeup')},
 'rtc':files('/sys/class/rtc',['name','wakealarm','since_epoch']),
 'inhibitors':run(['systemd-inhibit','--list','--no-pager']),
 'services':run(['systemctl','list-units','--all','--no-pager','--plain','*power*','*thermal*','*perf*']),
 'userPowerProcesses':run(['pgrep','-a','-f','xfce4-power-manager|thermald|thermal-engine|power-profiles|tlp']),
 'samples':[sample()]}
try:
 config=gzip.open('/proc/config.gz','rt').read()
 data['kernelConfig']=[s for s in config.splitlines() if any(x in s for x in ['CONFIG_PM','CONFIG_SUSPEND','CONFIG_RTC','CONFIG_CPU_FREQ','CONFIG_DEVFREQ','CONFIG_THERMAL','CONFIG_WAKELOCK'])]
except OSError:data['kernelConfig']=None
time.sleep(12);data['samples'].append(sample())
data['baselineScope']='USB-powered low-activity samples; X11 screen state was not measured. No battery-only, LTE traffic, physical AR, CPU-load or suspended measurement is inferred'
print(json.dumps(data,indent=2))
'''
if __name__=='__main__':
 p=subprocess.run(SSH+['python3 -c '+shlex.quote(SOURCE)],capture_output=True,timeout=45)
 if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
 d=json.loads(p.stdout);(ROOT/'evidence/etherpower-audit.json').write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:d[k] for k in ['kernel','power','policies','backlights','rtc','baselineScope']},indent=2))
