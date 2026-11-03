"""Opt-in EXIF GPS encoding from the permission-filtered EtherLocation result."""
import datetime
import math
import time

def gps_exif(position,now=None):
    from PIL import Image,TiffImagePlugin
    now=time.time() if now is None else now
    for key,lo,hi in [('latitude',-90,90),('longitude',-180,180),('accuracy',.01,10000000),('timestamp',1,now+5)]:
        value=position.get(key)
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Invalid location metadata')
    if position.get('kind')!='live' or now-position['timestamp']>30:raise ValueError('A fresh live location is required for photo metadata')
    rational=TiffImagePlugin.IFDRational
    def degrees(v):
        v=abs(v);d=int(v);m=int((v-d)*60);return (rational(d),rational(m),rational((v-d-m/60)*3600))
    stamp=datetime.datetime.fromtimestamp(position['timestamp'],datetime.timezone.utc)
    gps={0:b'\x02\x03\x00\x00',1:'N' if position['latitude']>=0 else 'S',2:degrees(position['latitude']),3:'E' if position['longitude']>=0 else 'W',4:degrees(position['longitude']),
         7:(rational(stamp.hour),rational(stamp.minute),rational(stamp.second+stamp.microsecond/1e6)),18:'WGS-84',29:stamp.strftime('%Y:%m:%d'),31:rational(position['accuracy'])}
    # Approximate responses deliberately omit altitude; never reconstruct it.
    if position.get('precision')=='precise' and 'altitude' in position:
        altitude=position['altitude']
        if math.isfinite(altitude):gps[5]=0 if altitude>=0 else 1;gps[6]=rational(abs(altitude))
    exif=Image.Exif();exif[34853]=gps;return exif
