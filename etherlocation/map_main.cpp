#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickImageProvider>
#include <QSqlDatabase>
#include <QSqlQuery>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QDir>
#include <QFile>
#include <QProcess>
#include <QStandardPaths>
#include <QCache>
#include <QImageReader>
#include <QQuickWindow>
#include <QSaveFile>
#include <cmath>
#include <QBuffer>
#include "locationclient.h"

#include "tiles.h"
class MapModel:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantList regions READ regions NOTIFY changed)
 Q_PROPERTY(QVariantList results READ results NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
 Q_PROPERTY(QVariantList savedPlaces READ savedPlaces NOTIFY changed)
 QVariantList m_regions,m_results,m_places;QString m_message;QProcess process;
public:
 MapModel(){connect(&process,&QProcess::readyReadStandardOutput,this,[this]{m_message=QString::fromUtf8(process.readAllStandardOutput()).trimmed().right(1000);emit changed();});
  connect(&process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int code,QProcess::ExitStatus){if(code)m_message=QString::fromUtf8(process.readAllStandardError()).left(500);reload();});reload();
  QFile places(mapRoot()+"/../saved-places.json");if(places.size()<65536&&places.open(QIODevice::ReadOnly))m_places=QJsonDocument::fromJson(places.readAll()).array().toVariantList();}
 QVariantList regions()const{return m_regions;}QVariantList results()const{return m_results;}
 QString message()const{return m_message;}bool busy()const{return process.state()!=QProcess::NotRunning;}
 QVariantList savedPlaces()const{return m_places;}
 void savePlaces(){QDir().mkpath(mapRoot());QSaveFile f(mapRoot()+"/../saved-places.json");if(f.open(QIODevice::WriteOnly)){f.setPermissions(QFile::ReadOwner|QFile::WriteOwner);f.write(QJsonDocument::fromVariant(m_places).toJson());f.commit();}emit changed();}
 Q_INVOKABLE void savePlace(const QString &name,double lat,double lon){if(name.trimmed().isEmpty()||name.size()>100||m_places.size()>=100||!std::isfinite(lat)||!std::isfinite(lon)||std::abs(lat)>90||std::abs(lon)>180)return;m_places<<QVariantMap{{"name",name.trimmed()},{"latitude",lat},{"longitude",lon}};savePlaces();}
 Q_INVOKABLE void deletePlace(int index){if(index>=0&&index<m_places.size()){m_places.removeAt(index);savePlaces();}}
 Q_INVOKABLE void reload(){m_regions.clear();QDir dir(mapRoot());for(auto file:dir.entryList({"*.json"},QDir::Files)){auto id=file.chopped(5);if(!validId(id)||!QFile::exists(dir.filePath(id+".mbtiles")))continue;QFile f(dir.filePath(file));if(f.size()>16384||!f.open(QIODevice::ReadOnly))continue;auto row=QJsonDocument::fromJson(f.readAll()).object().toVariantMap();row["id"]=id;m_regions<<row;}emit changed();}
 void command(const QStringList &args){if(busy())return;process.start("/usr/bin/python3",QStringList{"/usr/share/etherlocation/maps.py"}+args);emit changed();}
 Q_INVOKABLE void importRegion(const QString &path,bool license){if(!license){m_message="Confirm offline dataset permission first";emit changed();return;}command({"import",path,"--offline-license-confirmed"});}
 Q_INVOKABLE void download(const QString &url,const QString &sha,bool license){if(!license){m_message="Confirm offline dataset permission first";emit changed();return;}command({"download",url,"--sha256",sha,"--offline-license-confirmed"});}
 Q_INVOKABLE void pause(){if(busy())process.terminate();}
 Q_INVOKABLE void estimate(const QString &url){command({"estimate",url});}
 Q_INVOKABLE void remove(const QString &id){if(validId(id))command({"delete",id});}
 Q_INVOKABLE void search(const QString &id,const QString &text){m_results.clear();if(!validId(id)||text.size()<2||text.size()>100)return;
  {auto db=QSqlDatabase::addDatabase("QSQLITE","map-search");db.setDatabaseName(mapRoot()+"/"+id+".mbtiles");db.setConnectOptions("QSQLITE_OPEN_READONLY");
   if(db.open()){QSqlQuery q(db);q.prepare("SELECT name,latitude,longitude FROM etherlocation_places WHERE name LIKE ? LIMIT 30");q.addBindValue("%"+text+"%");if(q.exec()){while(q.next())m_results<<QVariantMap{{"name",q.value(0)},{"latitude",q.value(1)},{"longitude",q.value(2)}};m_message=m_results.isEmpty()?"No matching places":"";}else m_message="This dataset has no offline place index";}db.close();}
  QSqlDatabase::removeDatabase("map-search");emit changed();}
signals:void changed();
};
int main(int argc,char **argv){
 QGuiApplication app(argc,argv);app.setApplicationName("EtherLocation Maps");
 LocationClient location;MapModel maps;QQmlApplicationEngine engine;engine.addImageProvider("tiles",new Tiles);
 engine.rootContext()->setContextProperty("LocationControl",&location);engine.rootContext()->setContextProperty("MapStore",&maps);
 engine.load(QUrl("qrc:/Map.qml"));if(engine.rootObjects().isEmpty())return 1;
 if(app.arguments().contains("--smoke-test"))QTimer::singleShot(2500,&app,[&]{
  const int i=app.arguments().indexOf("--screenshot");
  if(i>=0&&i+1<app.arguments().size()){
   auto window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
   if(!window||!window->grabWindow().save(app.arguments()[i+1])){app.exit(2);return;}
  }app.quit();
 });
 return app.exec();
}
#include "map_main.moc"
