"""Render one small licensed OSM XML extract into real offline raster MBTiles.

No tile-server access. This bounded street-map acceptance dataset is not a
navigation database. Run on Debian with python3-pil. XML can also be supplied
locally. OSM attribution and provenance accompany the output.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
BOUNDS=(-0.135,51.499,-0.125,51.505)

def xy(lon,lat,z):
    r=math.radians(lat);n=256*2**z
    return ((lon+180)/360*n,(1-math.asinh(math.tan(r))/math.pi)/2*n)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--xml',type=Path);args=parser.parse_args()
    source=ROOT/'build/ethermap-westminster.osm'
    url='https://api.openstreetmap.org/api/0.6/map?bbox='+','.join(map(str,BOUNDS))
    if args.xml:raw=args.xml.read_bytes()
    elif source.exists():raw=source.read_bytes()
    else:
        request=urllib.request.Request(url,headers={'User-Agent':'EtherMAP/0.1 (Etherneco LTD; bounded offline map acceptance)'})
        with urllib.request.urlopen(request,timeout=60) as response:raw=response.read(32*1024**2+1)
        if len(raw)>32*1024**2:raise ValueError('OSM extract too large')
        source.write_bytes(raw)
    data=ET.fromstring(raw);nodes={n.attrib['id']:(float(n.attrib['lon']),float(n.attrib['lat'])) for n in data.findall('node')}
    ways=[]
    for way in data.findall('way'):
        tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
        points=[nodes[n.attrib['ref']] for n in way.findall('nd') if n.attrib['ref'] in nodes]
        if len(points)>1:ways.append((points,tags))
    target=ROOT/'build/ethermap-westminster-osm.mbtiles'
    if target.exists():target.unlink()
    db=sqlite3.connect(target)
    db.execute('CREATE TABLE metadata(name TEXT,value TEXT)');db.execute('CREATE TABLE tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB,UNIQUE(zoom_level,tile_column,tile_row))')
    db.execute('CREATE TABLE etherlocation_places(name TEXT,latitude REAL,longitude REAL)')
    metadata=dict(name='Westminster · OpenStreetMap',format='png',scheme='tms',minzoom='13',maxzoom='16',bounds=','.join(map(str,BOUNDS)),attribution='© OpenStreetMap contributors · ODbL 1.0 · openstreetmap.org/copyright')
    db.executemany('INSERT INTO metadata VALUES(?,?)',metadata.items())
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',11)
    count=0
    for z in range(13,17):
        left,top=xy(BOUNDS[0],BOUNDS[3],z);right,bottom=xy(BOUNDS[2],BOUNDS[1],z)
        minx,maxx=math.floor(left/256),math.floor(right/256);miny,maxy=math.floor(top/256),math.floor(bottom/256)
        width=(maxx-minx+1)*256;height=(maxy-miny+1)*256
        image=Image.new('RGB',(width,height),'#eeeae1');draw=ImageDraw.Draw(image)
        prepared=[([(xy(lon,lat,z)[0]-minx*256,xy(lon,lat,z)[1]-miny*256) for lon,lat in points],tags) for points,tags in ways]
        for points,tags in prepared:
            if points[0]==points[-1] and len(points)>3:
                fill='#d6dfc4' if tags.get('leisure') in ('park','garden','pitch') or tags.get('landuse') in ('grass','forest','recreation_ground') else '#9fcfdf' if tags.get('natural')=='water' or tags.get('waterway')=='riverbank' else '#d7cfc4' if 'building' in tags else None
                if fill:draw.polygon(points,fill=fill)
        for points,tags in prepared:
            if 'highway' in tags:
                large=tags['highway'] in ('primary','secondary','trunk','tertiary');w=max(2,round((5 if large else 3)*2**(z-15)))
                draw.line(points,fill='#bcb6aa',width=w+2,joint='curve');draw.line(points,fill='#f8ce89' if large else '#fffdf8',width=w,joint='curve')
            elif tags.get('waterway'):draw.line(points,fill='#9fcfdf',width=max(2,2**(z-14)))
        occupied=[]
        for points,tags in prepared:
            if z<15 or 'highway' not in tags or not tags.get('name'):continue
            x,y=points[len(points)//2];text=tags['name'];box=draw.textbbox((x,y),text,font=font)
            if not (0<x<width and 0<y<height) or any(not(box[2]<b[0] or box[0]>b[2] or box[3]<b[1] or box[1]>b[3]) for b in occupied):continue
            draw.text((x,y),text,font=font,fill='#43505a',stroke_width=1,stroke_fill='#faf8f0');occupied.append(box)
        for tx in range(minx,maxx+1):
            for ty in range(miny,maxy+1):
                tile=image.crop(((tx-minx)*256,(ty-miny)*256,(tx-minx+1)*256,(ty-miny+1)*256));stream=io.BytesIO();tile.save(stream,format='PNG')
                db.execute('INSERT INTO tiles VALUES(?,?,?,?)',(z,tx,2**z-1-ty,stream.getvalue()));count+=1
    for points,tags in ways:
        if tags.get('name'):
            p=points[len(points)//2];db.execute('INSERT INTO etherlocation_places VALUES(?,?,?)',(tags['name'],p[1],p[0]))
    db.commit();db.close()
    result=dict(source=url,sourceSha256=hashlib.sha256(raw).hexdigest(),dataset=str(target.relative_to(ROOT)),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),bytes=target.stat().st_size,tiles=count,nodes=len(nodes),ways=len(ways),bounds=BOUNDS,license='OpenStreetMap ODbL 1.0',publicTileRequests=0)
    (ROOT/'evidence/ethermap-osm-dataset.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
