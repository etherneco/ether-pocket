#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQmlNetworkAccessManagerFactory>
#include <QNetworkAccessManager>
#include <QNetworkDiskCache>
#include <QNetworkRequest>
#include <QProcess>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <QQuickWindow>
#include <QTimer>
#include <QFile>
#include <QQuickStyle>
#include <QMutex>
#include <QMutexLocker>
#ifdef ETHERMAP_UI_TESTS
#include <QTest>
#endif
#include "../etherlocation/tiles.h"

struct NetworkPolicy { QMutex mutex; bool online=false; QString host; };
class Network:public QNetworkAccessManager {
 NetworkPolicy *policy;
public:Network(QObject *parent,NetworkPolicy *p):QNetworkAccessManager(parent),policy(p){
 auto cache=new QNetworkDiskCache(this);cache->setCacheDirectory(QStandardPaths::writableLocation(QStandardPaths::CacheLocation)+"/tiles");cache->setMaximumCacheSize(128*1024*1024);setCache(cache);
 }
protected:QNetworkReply *createRequest(Operation op,const QNetworkRequest &original,QIODevice *data=nullptr)override{
 QNetworkRequest request(original);QMutexLocker lock(&policy->mutex);
 if(request.url().scheme()=="https"){
  if(!policy->online||request.url().host()!=policy->host){request.setUrl(QUrl());}
  request.setRawHeader("User-Agent","EtherMAP/0.1 (Etherneco LTD; native Qt map viewer)");
  request.setAttribute(QNetworkRequest::CacheLoadControlAttribute,QNetworkRequest::PreferCache);
  request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,QNetworkRequest::ManualRedirectPolicy);
  request.setTransferTimeout(15000);
 }
 return QNetworkAccessManager::createRequest(op,request,data);
 }
};
class Factory:public QQmlNetworkAccessManagerFactory {
 NetworkPolicy *policy;
public:explicit Factory(NetworkPolicy *p):policy(p){} QNetworkAccessManager *create(QObject *p)override{return new Network(p,policy);}
};
class Model:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 QProcess worker;QByteArray buffer;QVariantMap snapshot;NetworkPolicy *policy;
public:
 Model(NetworkPolicy *p):policy(p){
  snapshot={{"settings",QVariantMap{}},{"position",QVariantMap{}},{"summary",QVariantMap{}},{"location",QVariantMap{}}};
  connect(&worker,&QProcess::readyReadStandardOutput,this,[this]{buffer+=worker.readAllStandardOutput();if(buffer.size()>16*1024*1024){worker.kill();return;}int end;while((end=buffer.indexOf('\n'))>=0){auto data=QJsonDocument::fromJson(buffer.left(end));buffer.remove(0,end+1);if(data.isObject()){snapshot=data.object().toVariantMap();auto s=snapshot.value("settings").toMap();{QMutexLocker lock(&policy->mutex);policy->online=s.value("onlineTiles").toBool();policy->host=QUrl(s.value("tileTemplate").toString()).host();}emit changed();}}});
  connect(&worker,&QProcess::errorOccurred,this,[this](QProcess::ProcessError){snapshot["message"]="EtherMAP worker unavailable";emit changed();});
  connect(&worker,&QProcess::readyReadStandardError,this,[this]{qWarning().noquote()<<QString::fromUtf8(worker.readAllStandardError());});
  connect(&worker,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int,QProcess::ExitStatus){snapshot["message"]="Map worker stopped. Reopen EtherMAP to reconnect.";snapshot["mode"]="Off";snapshot["recording"]=false;snapshot["position"]=QVariantMap{};snapshot["trail"]=QVariantList{};emit changed();});
  worker.start("/usr/bin/python3",{"/usr/share/ethermap/backend.py"});
 }
 ~Model(){worker.closeWriteChannel();if(!worker.waitForFinished(3000)){worker.terminate();if(!worker.waitForFinished(2000)){worker.kill();worker.waitForFinished(1000);}}}
 QVariantMap state()const{return snapshot;}
 Q_INVOKABLE void send(const QString &op,const QVariantMap &args=QVariantMap{}){worker.write(QJsonDocument::fromVariant(QVariantMap{{"op",op},{"args",args}}).toJson(QJsonDocument::Compact)+'\n');}
signals:void changed();
};
int main(int argc,char **argv){
 QGuiApplication app(argc,argv);app.setApplicationName("EtherMAP");app.setOrganizationName("Etherneco");QQuickStyle::setStyle("Basic");
 NetworkPolicy policy;Factory factory(&policy);Model model(&policy);QQmlApplicationEngine engine;engine.setNetworkAccessManagerFactory(&factory);engine.addImageProvider("tiles",new Tiles);
 engine.rootContext()->setContextProperty("Maps",&model);engine.load(QUrl("qrc:/Main.qml"));if(engine.rootObjects().isEmpty())return 1;
 auto window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
 const int sizeIndex=app.arguments().indexOf("--size");if(window&&sizeIndex>=0&&sizeIndex+1<app.arguments().size()){auto dimensions=app.arguments()[sizeIndex+1].split('x');if(dimensions.size()==2){const int width=dimensions[0].toInt(),height=dimensions[1].toInt();if(width>=320&&width<=3840&&height>=480&&height<=3840)window->resize(width,height);}}
 if(app.arguments().contains("--settings"))QTimer::singleShot(500,&app,[&]{QMetaObject::invokeMethod(engine.rootObjects().first(),"openSettings");});
#ifdef ETHERMAP_UI_TESTS
 if(app.arguments().contains("--interaction-test"))QTimer::singleShot(3000,&app,[&]{
  auto root=engine.rootObjects().first();auto viewport=root->findChild<QObject*>("mapViewport");QVariantMap result;
  const int z=root->property("zoom").toInt();root->setProperty("zoom",z-1);QTest::qWait(200);result["zoom"]=root->property("zoom").toInt()==z-1;
  root->setProperty("bearing",30.0);result["rotation"]=root->property("bearing").toDouble()==30;root->setProperty("bearing",0.0);
  double before=viewport?viewport->property("contentX").toDouble():0;
  QTest::mousePress(window,Qt::LeftButton,Qt::NoModifier,QPoint(150,280));QTest::mouseMove(window,QPoint(180,280),80);QTest::mouseMove(window,QPoint(230,280),80);QTest::mouseRelease(window,Qt::LeftButton,Qt::NoModifier,QPoint(230,280));QTest::qWait(500);
  result["pan"]=viewport&&std::abs(viewport->property("contentX").toDouble()-before)>1;
  if(viewport)QMetaObject::invokeMethod(viewport,"cancelFlick");QTest::qWait(300);
  double panned=viewport?viewport->property("contentX").toDouble():0;QTest::qWait(2300);result["panSurvivesStatusRefresh"]=viewport&&std::abs(viewport->property("contentX").toDouble()-panned)<1;
  QTest::mouseClick(window,Qt::LeftButton,Qt::NoModifier,QPoint(160,320));QTest::qWait(60);QTest::mouseDClick(window,Qt::LeftButton,Qt::NoModifier,QPoint(160,320));QTest::mouseRelease(window,Qt::LeftButton,Qt::NoModifier,QPoint(160,320));QTest::qWait(500);
  result["manualSeparate"]=model.state().value("manual").toMap().value("kind")=="manual"&&model.state().value("position").toMap().isEmpty()&&model.state().value("trail").toList().isEmpty();
  if(!result["manualSeparate"].toBool())qInfo().noquote()<<"Manual diagnostic:"<<QJsonDocument::fromVariant(model.state().value("manual")).toJson(QJsonDocument::Compact);
  model.send("savePlace",{{"name","QA offline saved place"},{"latitude",51.502},{"longitude",-0.13}});QTest::qWait(300);
  model.send("search",{{"query","QA offline"},{"online",false}});QTest::qWait(300);result["savedPlaceSearch"]=!model.state().value("results").toList().isEmpty();
  const auto settings=model.state().value("settings").toMap();result["historyDefaultOff"]=!settings.value("history").toBool()&&!model.state().value("recording").toBool();
  model.send("clear");QTest::qWait(300);
  qInfo().noquote()<<QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact);
  bool passed=true;for(auto it=result.begin();it!=result.end();++it)passed=passed&&it.value().toBool();app.exit(passed?0:6);
 });
#endif
 if(app.arguments().contains("--smoke-test"))QTimer::singleShot(3500,&app,[&]{int i=app.arguments().indexOf("--screenshot");if(i>=0&&i+1<app.arguments().size()){auto w=qobject_cast<QQuickWindow*>(engine.rootObjects().first());if(!w||!w->grabWindow().save(app.arguments()[i+1])){app.exit(2);return;}}if(!model.state().value("ready").toBool()){app.exit(3);return;}if(app.arguments().contains("--expect-offline")&&model.state().value("regions").toList().isEmpty()){app.exit(4);return;}app.quit();});
 return app.exec();
}
#include "main.moc"
