#pragma once
#include <QQuickImageProvider>
#include <QSqlDatabase>
#include <QSqlQuery>
#include <QDir>
#include <QCache>
#include <QImageReader>
#include <QBuffer>
static QString mapRoot(){return QDir::homePath()+"/.local/share/etherlocation/maps";}
static bool validId(const QString &id){if(id.size()!=32)return false;for(auto c:id)if(!QString("0123456789abcdef").contains(c))return false;return true;}
class Tiles:public QQuickImageProvider {
 QCache<QString,QImage> cache{32768};
public:
 Tiles():QQuickImageProvider(QQuickImageProvider::Image){}
 QImage requestImage(const QString &id,QSize *size,const QSize&)override {
  if(auto p=cache.object(id)){if(size)*size=p->size();return *p;}
  QImage image(256,256,QImage::Format_RGB32);image.fill(QColor("#d9e0e7"));
  auto parts=id.split('/');bool ok=false;
  if(parts.size()!=4||!validId(parts[0]))return image;
  const int z=parts[1].toInt(&ok);if(!ok||z<0||z>20)return image;
  const int x=parts[2].toInt(&ok);if(!ok||x<0||x>=(1<<z))return image;
  const int y=parts[3].toInt(&ok);if(!ok||y<0||y>=(1<<z))return image;
  {auto db=QSqlDatabase::addDatabase("QSQLITE","map-tile");db.setConnectOptions("QSQLITE_OPEN_READONLY");db.setDatabaseName(mapRoot()+"/"+parts[0]+".mbtiles");
   if(db.open()) {QSqlQuery q(db);q.prepare("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=? LIMIT 1");q.addBindValue(z);q.addBindValue(x);q.addBindValue((1<<z)-1-y);
    if(q.exec()&&q.next()) {auto bytes=q.value(0).toByteArray();if(bytes.size()<=4*1024*1024){QBuffer b(&bytes);b.open(QIODevice::ReadOnly);QImageReader reader(&b);auto s=reader.size();if(s.width()>0&&s.height()>0&&s.width()<=512&&s.height()<=512){auto result=reader.read();if(!result.isNull())image=result;}}}
   }db.close();}
  QSqlDatabase::removeDatabase("map-tile");if(size)*size=image.size();cache.insert(id,new QImage(image),image.sizeInBytes()/1024);return image;
 }
};
