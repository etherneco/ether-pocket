"""Decode one pinned IMX586 RAW10 mode on-device. Tables stay on the phone;
only a private transient JSON plan is passed to the native capture worker.
"""
import hashlib
import math
import struct
from module_profile import decode,ProfileError

ALLOWED={'0e67372a3fb69030ab0e9749bf8de2c0b1a1774719ff9e388e6527be3afbb950',
 'ff92daf0496ee923f77f459e959d29907490dc15ed2e2eec932c1575cccd074d',
 '5dc0f4ab6916f425a7dafaeaa6588d78e94673812bbc233009268627d4ee167d'}

def capture_profile(blob):
    profile=decode(blob)
    if profile['sourceSha256'] not in ALLOWED:raise ProfileError('Unpinned module; no sensor programming permitted')
    sections=[struct.unpack_from('<QQQ',blob,160+i*24) for i in range(3)]
    start,length=sections[0][1:];base=sections[1][1];symbols={}
    for p in range(start,start+length,72):
        ident=struct.unpack_from('<Q',blob,p)[0];name=blob[p+8:p+40].split(b'\0')[0].decode('ascii')
        off,size=struct.unpack_from('<QQ',blob,p+56);symbols[ident]=(name,blob[base+off:base+off+size])
    def data(ident,name):
        if ident not in symbols or symbols[ident][0]!=name:raise ProfileError('Unexpected capture schema')
        b=symbols[ident][1]
        if len(b)%8:raise ProfileError('Unaligned capture data')
        return struct.unpack('<'+'Q'*(len(b)//8),b)
    def registers(count,ident):
        values=data(ident,'regSetting')
        if not 1<=count<=4096 or len(values)!=count*10:raise ProfileError('Invalid register table')
        result=[]
        for i in range(count):
            row=values[i*10:(i+1)*10]
            if row[0]!=0 or row[3]!=1 or row[5:8]!=(2,1,0) or row[8] not in (0,1):raise ProfileError('Unsupported register operation')
            val=data(row[4],'registerData')
            delay=data(row[9],'delayUs') if row[8] else (0,)
            if len(val)!=1 or len(delay)!=1 or val[0]>255 or row[2]>65535 or delay[0]>100000:raise ProfileError('Register operation outside bounds')
            result.append([row[2],val[0],delay[0]])
        return result
    sensor=data(2,'sensorDriverData');resolution=data(sensor[41],'resolutionInfo')
    if resolution[2]!=9:raise ProfileError('Unexpected mode count')
    rows=data(resolution[3],'resolutionData')
    if len(rows)!=9*36:raise ProfileError('Unexpected mode schema')
    mode=rows[:36];streams=data(mode[2],'streamConfiguration')
    if mode[0]!=0 or mode[1]!=2 or len(streams)!=16 or streams[:8]!=(0,43,0,0,4000,3000,10,1):raise ProfileError('Unsupported primary image stream')
    if (mode[7],mode[11],mode[14],mode[15])!=(577650000,3,14,1):raise ProfileError('Unexpected RAW10 clock/lane/timing profile')
    init=data(sensor[70],'initSettings')
    if len(init)!=3 or init[0]!=0:raise ProfileError('Unsupported init settings')
    on=registers(sensor[55],sensor[56]);off=registers(sensor[57],sensor[58])
    if on!=[[256,1,0]] or off!=[[256,0,0]]:raise ProfileError('Unexpected streaming lifecycle')
    initial=registers(init[1],init[2]);mode_regs=registers(mode[18],mode[19])
    profile.update(width=4000,height=3000,bits=10,virtualChannel=0,dataType=43,bayer=0,
        outputPixelClock=mode[7],laneCount=3,is3Phase=True,laneAssign=528,settle=14,
        initial=initial,mode=mode_regs,streamOn=on,streamOff=off)
    profile['tableSha256']=hashlib.sha256(repr([initial,mode_regs,on,off]).encode()).hexdigest()
    profile['packetSha256']=hashlib.sha256(b''.join(struct.pack('<III',*r) for group in [initial,mode_regs,on,off] for r in group)).hexdigest()
    return profile
