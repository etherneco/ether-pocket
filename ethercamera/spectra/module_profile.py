"""Bounded read-only decoder for this handset's Parameter Parser 1.3.2 module
files. Extracts only IMX586 probe/power facts. Never loads a vendor library or
reads calibration, EEPROM or tuning contents. Not a generic Chromatix parser.
"""
import hashlib
import struct

class ProfileError(ValueError):pass

def decode(blob):
    if not isinstance(blob,bytes) or not 232<=len(blob)<=2*1024*1024:raise ProfileError('Module size outside bounds')
    if not blob.startswith(b'QTI Chromatix Header\0'):raise ProfileError('Unsupported module magic')
    if b'Parameter Parser V1.3.2 ' not in blob[36:144]:raise ProfileError('Unsupported generator')
    table,count=struct.unpack_from('<II',blob,152)
    if table!=160 or count!=3:raise ProfileError('Unsupported section table')
    sections={}
    previous=232
    for index in range(count):
        kind,start,size=struct.unpack_from('<QQQ',blob,table+index*24)
        if kind in sections or start!=previous or start>len(blob) or size>len(blob)-start:raise ProfileError('Invalid section boundary')
        sections[kind]=(start,size);previous=start+size
    if set(sections)!={0,1,2} or previous!=len(blob):raise ProfileError('Invalid module sections')
    start,size=sections[0];data_start,data_size=sections[1]
    if size%72 or not 2<=size//72<=20000:raise ProfileError('Invalid symbol table')
    symbols={}
    for offset in range(start,start+size,72):
        ident=struct.unpack_from('<Q',blob,offset)[0]
        raw_name=blob[offset+8:offset+40]
        try:name=raw_name.split(b'\0')[0].decode('ascii')
        except UnicodeError:raise ProfileError('Invalid symbol name')
        major,minor,relative,length=struct.unpack_from('<QQQQ',blob,offset+40)
        if not ident or ident in symbols or not name or relative>data_size or length>data_size-relative:raise ProfileError('Invalid symbol data')
        symbols[ident]=(name,blob[data_start+relative:data_start+relative+length])
    def symbol(ident,name=None):
        if ident not in symbols or name is not None and symbols[ident][0]!=name:raise ProfileError('Unexpected schema symbol')
        return symbols[ident][1]
    def words(data):
        if len(data)%8:raise ProfileError('Unaligned schema value')
        return struct.unpack('<'+'Q'*(len(data)//8),data)
    root=words(symbol(1,'cameraModuleData'));sensor=words(symbol(2,'sensorDriverData'))
    if len(root)!=5 or root[:3]!=(1,0,0) or root[3]!=1 or len(sensor)!=103 or sensor[:3]!=(1,0,0):raise ProfileError('Unsupported schema revision')
    module=words(symbol(root[4],'moduleConfiguration'))
    if len(module)!=38 or module[0]!=0:raise ProfileError('Only rear main slot 0 is permitted')
    sensor_name=symbol(sensor[4],'sensorName').rstrip(b'\0').decode('ascii')
    if sensor_name!='imx586' or sensor[3]!=7 or tuple(sensor[5:12])!=(0x34,2,2,0x16,0x586,0xffff,3):raise ProfileError('Unexpected main-sensor probe data')
    def power(count,ident):
        raw=words(symbol(ident,'powerSetting'))
        if count!=7 or len(raw)!=count*3:raise ProfileError('Unexpected power sequence count')
        result=[]
        for i in range(count):
            seq,value,delay=raw[i*3:i*3+3]
            if seq not in (0,1,2,3,8,10,11) or delay>100:raise ProfileError('Unsupported power operation')
            if seq==0 and value not in (0,19200000) or seq!=0 and value not in (0,1):raise ProfileError('Unexpected power value')
            result.append(dict(type=seq,value=value,delayMs=delay))
        return result
    up=power(sensor[12],sensor[13]);down=power(sensor[14],sensor[15])
    if up[-1]!={'type':8,'value':1,'delayMs':1} or down[0]!={'type':8,'value':0,'delayMs':1}:raise ProfileError('Unexpected reset lifecycle')
    return dict(schemaVersion=1,sourceSha256=hashlib.sha256(blob).hexdigest(),source='device-owned vendor module, read-only',
        sensor=sensor_name,slot=0,slaveAddress=52,idRegister=22,expectedId=1414,idMask=65535,addressBytes=2,dataBytes=2,i2cMode=3,
        powerUp=up,powerDown=down,profileProvenance='decoded module data; not physical sensor identification',physicalFrameVerified=False)
