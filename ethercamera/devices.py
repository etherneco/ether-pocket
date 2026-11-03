"""Read-only V4L2 discovery. Vendor and memory-to-memory nodes cannot be opened as sensors."""
import errno
import fcntl
import os
from pathlib import Path
import struct
import subprocess
import re
from core import role

def parse_formats(text):
    modes=[];pixel='';current=None
    for line in text.splitlines():
        fmt=re.search(r"\[\d+\]:\s+'([^']+)'",line)
        if fmt:pixel=fmt[1];current=None
        size=re.search(r'Size:\s+Discrete\s+(\d+)x(\d+)',line)
        if size:
            current=dict(pixelFormat=pixel,width=int(size[1]),height=int(size[2]),frameRates=[]);modes.append(current)
        fps=re.search(r'\(([0-9.]+) fps\)',line)
        if fps and current is not None:current['frameRates'].append(float(fps[1]))
    return modes

def enumerate_devices():
    rows=[]
    for p in sorted(Path('/sys/class/video4linux').glob('video[0-9]*')):
        try:name=(p/'name').read_text().strip()
        except OSError:continue  # Hot-unplug between directory enumeration and name read.
        binding=p/'device/driver'
        row=dict(id='/dev/'+p.name,name=name,driver=binding.resolve().name if binding.is_symlink() else '',role='unavailable',operational=None,
                 connected=True,busy=None,
                 previewVerified=False,stillVerified=False,videoVerified=False)
        try:
            fd=os.open(row['id'],os.O_RDONLY|os.O_NONBLOCK)
            try:
                b=bytearray(104);fcntl.ioctl(fd,0x80685600,b,True)
            finally:os.close(fd)
            driver=bytes(b[:16]).split(b'\0')[0].decode(errors='replace')
            card=bytes(b[16:48]).split(b'\0')[0].decode(errors='replace')
            _,caps,dcaps=struct.unpack_from('=III',b,80)
            flags=dcaps if caps&0x80000000 else caps
            row.update(driver=driver,name=card or name,role=role(driver,card,flags),deviceCaps=flags)
            if row['role']=='capture-candidate':
                # Restrict initial provider to USB UVC: no motor or proprietary ISP activation.
                row['supportedProvider']=driver=='uvcvideo'
                for key,args in [('formats',['--list-formats-ext']),('controls',['--list-ctrls-menus'])]:
                    result=subprocess.run(['v4l2-ctl','-d',row['id']]+args,capture_output=True,text=True,timeout=4,env=dict(os.environ,LC_ALL='C'))
                    row[key]=result.stdout[:24000]
                row['modes']=parse_formats(row.get('formats',''))
                row['pixelFormats']=sorted({m['pixelFormat'] for m in row['modes']})
                controls=row.get('controls','')
                row['focusControls']=[c for c in ['focus_auto','focus_automatic_continuous','focus_absolute'] if re.search(r'^\s*'+c+r'\s+0x',controls,re.M)]
                row['exposureControls']=[c for c in ['exposure_auto','auto_exposure','exposure_absolute','exposure_time_absolute'] if re.search(r'^\s*'+c+r'\s+0x',controls,re.M)]
                row['flashAvailable']=None
            else:row['supportedProvider']=False
        except (OSError,subprocess.TimeoutExpired) as e:
            row.update(error=str(e),supportedProvider=False)
            if name=='cam-req-mgr':row['role']='vendor-request-manager'
            if name=='cam_sync':row['role']='vendor-sync'
            if isinstance(e,OSError) and e.errno==errno.EBUSY:row['busy']=True
            if isinstance(e,OSError) and e.errno in (errno.ENODEV,errno.ENOENT):row['connected']=False
        rows.append(row)
    from spectra_provider import available,device
    if available():rows.insert(0,device())
    return rows
