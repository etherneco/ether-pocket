#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickImageProvider>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusUnixFileDescriptor>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QCache>
#include <QMutex>
#include <QMutexLocker>
#include <QFile>
#include <QClipboard>
#include <QMimeData>
#include <QDesktopServices>
#include <QTimer>
#include <QQuickWindow>
#include <QDir>
#include <unistd.h>
#include <functional>
#include <QQueue>
#include <QSet>
#include <QDateTime>
#include <QVideoSink>
#include <QVideoFrame>
#include <memory>

class MediaImages:public QQuickImageProvider {
 QMutex mutex;QCache<QString,QImage> cache{8192};
public:
 MediaImages():QQuickImageProvider(QQuickImageProvider::Image){}
 void put(const QString &key,const QImage &image){QMutexLocker lock(&mutex);cache.insert(key,new QImage(image),qMax(1,int(image.sizeInBytes()/1024)));}
 QImage requestImage(const QString &id,QSize *size,const QSize&)override{QMutexLocker lock(&mutex);auto *image=cache.object(id.section('?',0,0));QImage result=image?*image:QImage();if(size)*size=result.size();return result;}
 void clear(){QMutexLocker lock(&mutex);cache.clear();}
};

class LibraryClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantList items READ items NOTIFY itemsChanged)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
 Q_PROPERTY(int nextOffset READ nextOffset NOTIFY changed)
 Q_PROPERTY(QString imageSource READ imageSource NOTIFY selected)
 Q_PROPERTY(QVariantMap selectedMedia READ selectedMedia NOTIFY selected)
 Q_PROPERTY(bool privateState READ privateState NOTIFY changed)
 Q_PROPERTY(QVideoSink* videoSink READ videoSink CONSTANT)
 Q_PROPERTY(QString videoFrameSource READ videoFrameSource NOTIFY videoFrameReady)
 Q_PROPERTY(int videoFrames READ videoFrames NOTIFY videoFrameReady)
 QVariantList m_items;QString m_message,m_imageSource;QVariantMap m_selected;
 MediaImages *images;int pending=0,next=-1,generation=0;bool locked=true;
 QString search,kind,album;QTimer jobTimer;QString job;int jobGeneration=0;
 QQueue<QString> thumbnails;QSet<QString> requestedThumbnails;int thumbnailPending=0;
 QVideoSink sink;QString videoSource;int receivedVideoFrames=0;
 const QString name="com.etherneco.EtherCamera1",path="/com/etherneco/EtherCamera1";
 void request(const QString &method,const QVariantList &args,std::function<void(QVariant)> done={},std::function<void()> finished={}){
  auto msg=QDBusMessage::createMethodCall(name,path,name,method);msg.setArguments(args);
  ++pending;emit changed();
  auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,45000),this);
  connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,done,finished]{--pending;auto reply=watch->reply();if(reply.type()==QDBusMessage::ErrorMessage)m_message=reply.errorMessage();else if(done)done(reply.arguments().value(0));if(finished)finished();emit changed();watch->deleteLater();});
 }
 void pumpThumbnails(){while(thumbnailPending<4&&!thumbnails.isEmpty()&&!locked){
  auto ref=thumbnails.dequeue();int current=generation;++thumbnailPending;
  request("GetThumbnail",{ref},[this,ref,current](QVariant value){if(current!=generation||locked)return;auto handle=qvariant_cast<QDBusUnixFileDescriptor>(value);QFile file;if(!handle.isValid()||!file.open(handle.fileDescriptor(),QIODevice::ReadOnly))return;auto image=QImage::fromData(file.read(1024*1024));if(!image.isNull()){images->put(ref,image);emit thumbnailReady(ref);}},[this]{--thumbnailPending;pumpThumbnails();});
 }}
 static QVariantMap object(const QVariant &value){return QJsonDocument::fromJson(value.toString().toUtf8()).object().toVariantMap();}
 void loadPage(int offset){
  const int current=generation;
  QVariantMap query{{"search",search},{"kind",kind},{"album",album}};
  request("ListMediaPage",{QString::fromUtf8(QJsonDocument::fromVariant(query).toJson(QJsonDocument::Compact)),QVariant::fromValue(uint(offset))},[this,current,offset](QVariant value){
   if(current!=generation)return;auto data=object(value);if(!offset)m_items.clear();
   for(const auto &value:data.value("items").toList()){
    auto row=value.toMap();const auto day=QDateTime::fromString(row.value("timestamp").toString(),Qt::ISODate).toLocalTime().date().toString(Qt::ISODate);
    row["localDay"]=day;row["dayHeader"]=m_items.isEmpty()||m_items.last().toMap().value("localDay").toString()!=day?day:QString();m_items<<row;
   }next=data.value("nextOffset",-1).toInt();m_message.clear();emit itemsChanged();emit changed();
  });
 }
 void jobStarted(QVariant value){job=value.toString();jobGeneration=generation;jobTimer.start();}
public:
 LibraryClient(MediaImages *provider):images(provider){
  connect(&sink,&QVideoSink::videoFrameChanged,this,[this](const QVideoFrame &frame){
   if(locked||!frame.isValid()||m_selected.value("metadata").toMap().value("suffix")!=".mp4")return;
   const auto image=frame.toImage();if(image.isNull())return;
   images->put("video",image);videoSource="image://library/video?"+QString::number(++receivedVideoFrames);emit videoFrameReady();
  });
  auto bus=QDBusConnection::sessionBus();
  bus.connect(name,path,name,"Changed",this,SLOT(state(QString)));
  bus.connect("com.etherneco.EtherLock1","/com/etherneco/EtherLock1","com.etherneco.EtherLock1","Changed",this,SLOT(lockState(QString)));
  bus.connect("org.freedesktop.DBus","/org/freedesktop/DBus","org.freedesktop.DBus","NameOwnerChanged",this,SLOT(ownerChanged(QString,QString,QString)));
  jobTimer.setInterval(300);jobTimer.setSingleShot(true);
  connect(&jobTimer,&QTimer::timeout,this,[this]{request("GetJob",{job},[this](QVariant value){auto result=object(value);if(result.value("state")=="running"){jobTimer.start();return;}job.clear();if(result.value("state")=="failed")m_message=result.value("error").toString();else{m_message="Document saved";if(jobGeneration==generation)load(search,kind,album);}});});
  request("GetState",{},[this](QVariant value){state(value.toString());});
 }
 QVariantList items()const{return m_items;}QString message()const{return m_message;}bool busy()const{return pending>0;}int nextOffset()const{return next;}QString imageSource()const{return m_imageSource;}QVariantMap selectedMedia()const{return m_selected;}bool privateState()const{return locked;}
 QVideoSink *videoSink(){return &sink;}QString videoFrameSource()const{return videoSource;}int videoFrames()const{return receivedVideoFrames;}
 Q_INVOKABLE void load(const QString &s={},const QString &k={},const QString &a={}){search=s;kind=k;album=a;++generation;thumbnails.clear();requestedThumbnails.clear();m_items.clear();next=-1;emit itemsChanged();emit changed();if(!locked)loadPage(0);}
 Q_INVOKABLE void more(){if(!busy()&&next>=0)loadPage(next);}
 Q_INVOKABLE void thumbnail(const QString &ref){if(locked||requestedThumbnails.contains(ref))return;requestedThumbnails.insert(ref);thumbnails.enqueue(ref);pumpThumbnails();}
 Q_INVOKABLE void choose(const QString &ref){
  clearSelection();const int current=generation;
  request("MediaInfo",{ref},[this,current,ref](QVariant value){if(current!=generation||locked)return;m_selected=object(value);emit selected();auto meta=m_selected.value("metadata").toMap();if(meta.value("suffix")==".jpg"||meta.value("suffix")==".png")request("OpenMedia",{ref},[this,current](QVariant value){if(current!=generation||locked)return;auto handle=qvariant_cast<QDBusUnixFileDescriptor>(value);QFile file;if(!handle.isValid()||!file.open(handle.fileDescriptor(),QIODevice::ReadOnly))return;auto image=QImage::fromData(file.read(16*1024*1024));if(!image.isNull()){images->put("full",image);m_imageSource="image://library/full?"+QString::number(++imageVersion);emit selected();}});});
 }
 Q_INVOKABLE void clearSelection(){m_selected.clear();m_imageSource.clear();videoSource.clear();receivedVideoFrames=0;emit videoFrameReady();emit selected();}
 Q_INVOKABLE void remove(const QString &ref){request("DeleteMedia",{ref},[this](QVariant){clearSelection();load(search,kind,album);m_message="Media deleted";});}
 Q_INVOKABLE void setAlbum(const QString &ref,const QString &a){request("SetAlbum",{ref,a},[this,ref](QVariant){load(search,kind,album);choose(ref);});}
 Q_INVOKABLE void exportMedia(const QString &ref){request("ExportMedia",{ref},[this](QVariant value){m_message="Exported to "+value.toString();});}
 Q_INVOKABLE void openSelected(){if(!locked&&!m_selected.isEmpty())QDesktopServices::openUrl(QUrl(m_selected.value("url").toString()));}
 Q_INVOKABLE void copyFile(){if(locked||m_selected.isEmpty())return;auto *data=new QMimeData;data->setUrls({QUrl(m_selected.value("url").toString())});QGuiApplication::clipboard()->setMimeData(data);m_message="File copied for sharing; paste into the destination application";emit changed();}
 Q_INVOKABLE void process(const QString &ref,int rotation,bool gray){request("ProcessDocument",{ref,QString::fromUtf8(QJsonDocument(QJsonObject{{"rotation",rotation},{"grayscale",gray}}).toJson(QJsonDocument::Compact))},[this](QVariant value){jobStarted(value);});}
 Q_INVOKABLE void pdf(const QStringList &references){request("ExportDocument",{references},[this](QVariant value){jobStarted(value);});}
signals:void changed();void itemsChanged();void selected();void videoFrameReady();void thumbnailReady(const QString&);
private slots:
 void state(const QString &document){auto data=object(document);if(!data.value("permissionCoordinatorAvailable").toBool()){lockState("{\"locked\":true}");m_message="EtherLock is unavailable. Camera media remains private.";emit changed();return;}
  requestLock();
 }
 void requestLock(){auto msg=QDBusMessage::createMethodCall("com.etherneco.EtherLock1","/com/etherneco/EtherLock1","com.etherneco.EtherLock1","GetState");auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,3000),this);connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch]{auto reply=watch->reply();lockState(reply.type()==QDBusMessage::ErrorMessage?"{\"locked\":true}":reply.arguments().value(0).toString());watch->deleteLater();});}
 void lockState(const QString &document){auto data=object(document);bool nextLocked=!data.value("ready").toBool()||data.value("locked",true).toBool();bool was=locked;locked=nextLocked;if(locked){++generation;thumbnails.clear();requestedThumbnails.clear();m_items.clear();emit itemsChanged();clearSelection();images->clear();next=-1;jobTimer.stop();job.clear();}else if(was)load(search,kind,album);emit changed();}
 void ownerChanged(const QString &owner,const QString &old,const QString &now){if((owner=="com.etherneco.EtherLock1"||owner==name)&&!old.isEmpty()&&now.isEmpty())lockState("{\"locked\":true}");if((owner==name||owner=="com.etherneco.EtherLock1")&&!now.isEmpty())request("GetState",{},[this](QVariant value){state(value.toString());});}
private:int imageVersion=0;
};

int main(int argc,char **argv){
 if(geteuid()==0){fprintf(stderr,"Run EtherCamera Media as the desktop user\n");return 1;}
 if(!qEnvironmentVariableIsSet("QT_QUICK_BACKEND"))qputenv("QT_QUICK_BACKEND","software");
 qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
 if(!qEnvironmentVariableIsSet("QT_FFMPEG_DECODING_HW_DEVICE_TYPES"))qputenv("QT_FFMPEG_DECODING_HW_DEVICE_TYPES",",");
 QGuiApplication app(argc,argv);app.setApplicationName("EtherCamera Media");app.setOrganizationName("Etherneco");
 auto *images=new MediaImages;LibraryClient library(images);QQmlApplicationEngine engine;engine.addImageProvider("library",images);engine.rootContext()->setContextProperty("Library",&library);
 engine.load(QUrl("qrc:/MediaLibrary.qml"));if(engine.rootObjects().isEmpty())return 2;
 const auto output=qEnvironmentVariable("ETHERCAMERA_MEDIA_QA_OUTPUT");
 if(!output.isEmpty()){
  auto size=qEnvironmentVariable("ETHERCAMERA_MEDIA_QA_SIZE").split('x');if(size.size()==2){engine.rootObjects().first()->setProperty("width",qBound(320,size[0].toInt(),2340));engine.rootObjects().first()->setProperty("height",qBound(480,size[1].toInt(),2340));}
  const auto view=qEnvironmentVariable("ETHERCAMERA_MEDIA_QA_VIEW");
  if(view=="photo"||view=="video"){
   auto opened=std::make_shared<bool>(false);
   QObject::connect(&library,&LibraryClient::changed,&app,[&,opened,view]{if(*opened)return;for(const auto &item:library.items()){auto row=item.toMap();if((view=="video")== (row.value("suffix")==".mp4")){*opened=true;QMetaObject::invokeMethod(engine.rootObjects().first(),"openMedia",Q_ARG(QVariant,row.value("reference")));break;}}});
   if(view=="video")engine.rootObjects().first()->setProperty("qaPlayVideo",true);
  }
  QTimer::singleShot(2400,&app,[&]{auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());QDir().mkpath(output);bool ok=window&&window->grabWindow().save(output+"/library.png");QFile file(output+"/result.json");file.open(QIODevice::WriteOnly);file.write(QJsonDocument(QJsonObject{{"rendered",ok},{"private",library.privateState()},{"items",int(library.items().size())},{"imageLoaded",!library.imageSource().isEmpty()},{"videoPosition",engine.rootObjects().first()->property("mediaPosition").toInt()},{"videoFrames",engine.rootObjects().first()->property("qaVideoFrames").toInt()}}).toJson());app.exit(ok?0:3);});
 }
 return app.exec();
}
#include "media_main.moc"
