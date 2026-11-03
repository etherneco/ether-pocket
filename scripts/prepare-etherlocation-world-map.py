"""Build a small, real offline overview from public-domain Natural Earth land.

No tile server is queried; this does not provide street maps or navigation.
"""
import hashlib,io,json,math,sqlite3,urllib.request
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent.parent
URL='https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson'
source=ROOT/'build/natural-earth-110m-land.geojson'
if not source.exists():
    with urllib.request.urlopen(URL,timeout=30) as response:source.write_bytes(response.read(4*1024**2))
features=json.loads(source.read_text())['features']
target=ROOT/'build/etherlocation-world-overview.mbtiles'
with sqlite3.connect(target) as db:
    db.execute('CREATE TABLE IF NOT EXISTS metadata(name TEXT PRIMARY KEY,value TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS tiles(zoom_level INTEGER,tile_column INTEGER,tile_row INTEGER,tile_data BLOB,PRIMARY KEY(zoom_level,tile_column,tile_row))')
    db.executemany('INSERT OR REPLACE INTO metadata VALUES(?,?)',dict(name='Natural Earth · World Overview',format='png',attribution='Natural Earth 1:110m land · Public domain · naturalearthdata.com · Overview only; no street data',bounds='-180,-85,180,85',minzoom='0',maxzoom='3',scheme='tms').items())
    for zoom in range(4):
        n=2**zoom;size=256*n;image=Image.new('RGB',(size,size),'#b8d5e8');draw=ImageDraw.Draw(image)
        def point(lon,lat):
            rad=math.radians(max(-85.05112878,min(85.05112878,lat)))
            return ((lon+180)/360*size,(1-math.log(math.tan(rad)+1/math.cos(rad))/math.pi)/2*size)
        for feature in features:
            geom=feature['geometry'];polygons=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
            for polygon in polygons:
                for i,ring in enumerate(polygon):draw.polygon([point(*p[:2]) for p in ring],fill='#dfe2cf' if i==0 else '#b8d5e8')
        for x in range(n):
            for y in range(n):
                out=io.BytesIO();image.crop((x*256,y*256,(x+1)*256,(y+1)*256)).save(out,'PNG')
                db.execute('INSERT OR REPLACE INTO tiles VALUES(?,?,?,?)',(zoom,x,n-1-y,out.getvalue()))
    db.execute('CREATE TABLE IF NOT EXISTS etherlocation_places(name TEXT,latitude REAL,longitude REAL)')
evidence=dict(source=URL,sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),license='Public domain',terms='https://www.naturalearthdata.com/about/terms-of-use/',datasetSha256=hashlib.sha256(target.read_bytes()).hexdigest(),dataset=str(target),zoom=[0,3],purpose='Real geographic overview; no invented GNSS coordinates, street search or navigation')
(ROOT/'evidence/etherlocation-map-provenance.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
print(target)
