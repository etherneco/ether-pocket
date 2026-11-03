#include "capture_controller.h"
#include <QMutexLocker>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusUnixFileDescriptor>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QFile>
#include <QProcess>
#include <QGuiApplication>
#include <QDateTime>
#include <unistd.h>

namespace {
const QString name="com.etherneco.EtherCamera1",path="/com/etherneco/EtherCamera1";
QJsonObject json(const QString &text){return QJsonDocument::fromJson(text.toUtf8()).object();}
}
void CaptureImage::put(const QImage &image){QMutexLocker guard(&mutex);frame=image;}
QImage CaptureImage::requestImage(const QString&,QSize *size,const QSize&){QMutexLocker guard(&mutex);if(size)*size=frame.size();return frame;}

CaptureController::CaptureController(CaptureImage *provider):images(provider){
 auto bus=QDBusConnection::sessionBus();
 bus.connect(name,path,name,"Changed",this,SLOT(state(QString)));
 bus.connect("com.etherneco.EtherLock1","/com/etherneco/EtherLock1","com.etherneco.EtherLock1","Changed",this,SLOT(lockState(QString)));
 bus.connect("org.freedesktop.DBus","/org/freedesktop/DBus","org.freedesktop.DBus","NameOwnerChanged",this,SLOT(ownerChanged(QString,QString,QString)));
 frames.setInterval(100);connect(&frames,&QTimer::timeout,this,&CaptureController::nextFrame);
 clock.setInterval(1000);connect(&clock,&QTimer::timeout,this,[this]{++m_seconds;emit changed();});
 connect(qGuiApp,&QGuiApplication::applicationStateChanged,this,[this](Qt::ApplicationState s){
  if(s!=Qt::ApplicationActive)release();
 });
 connect(qGuiApp,&QCoreApplication::aboutToQuit,this,[this]{
  closing=true;const auto current=token;reset();
  if(!current.isEmpty()){
   auto msg=QDBusMessage::createMethodCall(name,path,name,"Release");msg<<current;
   // Release finalizes a running video; keep the owning connection alive until acknowledgement.
   QDBusConnection::sessionBus().call(msg,QDBus::Block,12000);
  }
 });
 refresh();
}
CaptureController::~CaptureController(){frames.stop();clock.stop();}
void CaptureController::call(const QString &method,const QVariantList &args,Done done,std::function<void(QString)> fail){
 const int current=generation;
 auto msg=QDBusMessage::createMethodCall(name,path,name,method);msg.setArguments(args);
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,15000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,done,fail,current]{
  auto reply=watch->reply();watch->deleteLater();if(closing)return;
  if(reply.type()==QDBusMessage::ErrorMessage){if(current!=generation)return;if(fail)fail(reply.errorMessage());else failed(reply.errorMessage());}
  else if(done)done(reply.arguments().value(0));
 });
}
void CaptureController::clearFrame(){m_source.clear();images->put({});}
void CaptureController::reset(){++generation;token.clear();m_active=false;m_recording=false;m_busy=false;framePending=false;frames.stop();clock.stop();clearFrame();}
void CaptureController::failed(const QString &error){release();m_message=error;emit changed();}
void CaptureController::refresh(){
 if(m_busy||m_active)return;m_busy=true;emit changed();
 call("Refresh",{},[this](QVariant value){m_busy=false;state(value.toString());},[this](QString error){m_busy=false;m_message=error;emit changed();});
}
void CaptureController::state(const QString &document){
 const auto data=json(document);m_devices.clear();
 for(const auto &item:data.value("devices").toArray()){
  auto row=item.toObject();if(row.value("supportedProvider").toBool())m_devices<<row.toVariantMap();
 }
 m_denied=data.value("config").toObject().value("cameraPolicy")=="deny";
 if(!token.isEmpty()&&(!data.value("busy").toBool()||data.value("owner").toString()!=QDBusConnection::sessionBus().baseService())){
  reset();m_message=data.value("lastError").toString();if(m_message.isEmpty())m_message=QStringLiteral("Sesja kamery została zakończona.");
 }else if(m_recording&&!m_busy&&!data.value("recording").toBool()){
  // Service duration/power limits may finalize recording without another user action.
  reset();m_message=QStringLiteral("Nagrywanie zakończone przez usługę. Sprawdź galerię.");
 }
 if(m_denied&&!token.isEmpty()){reset();m_message=QStringLiteral("Dostęp do kamery wyłączono w Ustawieniach.");}
 if(!data.value("permissionCoordinatorAvailable").toBool())lockState("{}");else updateLock();
 emit changed();
}
void CaptureController::updateLock(){
 const int revision=privacyRevision;
 auto msg=QDBusMessage::createMethodCall("com.etherneco.EtherLock1","/com/etherneco/EtherLock1","com.etherneco.EtherLock1","GetState");
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,2500),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,revision]{auto reply=watch->reply();watch->deleteLater();if(revision!=privacyRevision)return;lockState(reply.type()==QDBusMessage::ErrorMessage?"{}":reply.arguments().value(0).toString());});
}
void CaptureController::lockState(const QString &document){
 ++privacyRevision;
 auto data=json(document);m_private=!(data.value("ready").toBool()&&data.value("locked").isBool()&&!data.value("locked").toBool()&&data.value("phase")=="unlocked");
 if(m_private){release();m_saved.clear();m_message=QStringLiteral("Odblokuj telefon, aby użyć kamery.");}emit changed();
}
void CaptureController::ownerChanged(const QString &owner,const QString &old,const QString &now){
 if(owner!=name&&owner!="com.etherneco.EtherLock1")return;
 if(!old.isEmpty()){++privacyRevision;m_private=true;reset();m_saved.clear();m_message=QStringLiteral("Usługa kamery lub prywatności została zatrzymana.");emit changed();}
 if(!now.isEmpty())call("GetState",{},[this](QVariant value){state(value.toString());});
}
void CaptureController::start(const QString &device){
 if(m_private||m_denied||m_busy||m_active)return;
 bool known=false;for(const auto &row:m_devices)known|=row.toMap().value("id")==device;
 if(!known){m_message=QStringLiteral("Brak dostępnej kamery przechwytującej obraz.");emit changed();return;}
 m_busy=true;m_saved.clear();m_message=QStringLiteral("Uruchamianie kamery…");emit changed();const int current=++generation;
 call("RequestSession",{device,QStringLiteral("EtherCamera — zdjęcia i filmy"),true,QStringLiteral("{}")},[this,current](QVariant value){
  const auto granted=value.toString();
  if(current!=generation||m_private){call("Release",{granted},[](QVariant){},[](QString){});return;}
  token=granted;
  call("StartPreview",{token},[this,current](QVariant){if(current!=generation)return;m_busy=false;m_active=true;m_message=QStringLiteral("Oczekiwanie na obraz z kamery…");frames.start();emit changed();});
 });
}
void CaptureController::nextFrame(){
 if(framePending||m_busy||!m_active||m_private||token.isEmpty())return;
 framePending=true;const int current=generation;
 call("GetFrame",{token},[this,current](QVariant value){
  framePending=false;if(current!=generation||m_private)return;
  auto handle=qvariant_cast<QDBusUnixFileDescriptor>(value);QFile file;
  if(!handle.isValid()||!file.open(handle.fileDescriptor(),QIODevice::ReadOnly)){failed("Nie można odczytać obrazu.");return;}
  const auto image=QImage::fromData(file.read(16*1024*1024));if(image.isNull()){failed("Nieprawidłowy obraz kamery.");return;}
  images->put(image);m_source="image://capture/frame?"+QString::number(++version);
  if(m_message==QStringLiteral("Oczekiwanie na obraz z kamery…"))m_message.clear();emit changed();
 },[this,current](QString error){framePending=false;if(current!=generation)return;
  if(error.contains("Frame request rate exceeded"))return;
  if(error.contains("No fresh physical camera frame")){clearFrame();emit changed();return;}failed(error);
 });
}
void CaptureController::photo(){
 if(m_busy||!hasFrame()||m_recording||m_private)return;
 m_busy=true;emit changed();const int current=generation;
 call("CapturePhoto",{token},[this,current](QVariant value){if(current!=generation)return;m_saved=json(value.toString()).value("reference").toString();m_busy=false;m_message=QStringLiteral("Zdjęcie zapisane w galerii.");emit saved("photo");emit changed();});
}
void CaptureController::requestLocation(){if(token.isEmpty())return;call("RequestPhotoLocation",{token},[this](QVariant){m_message="Review the location request in Settings → Location. Restart camera preview after reviewing.";emit changed();});}
void CaptureController::enableLocation(bool consent){if(token.isEmpty())return;call("EnablePhotoLocation",{token,consent},[this,consent](QVariant){m_message=consent?"Photo location enabled for this camera session when a fresh permitted fix exists":"Photo location disabled";emit changed();});}
void CaptureController::record(bool microphoneConsent){
 if(m_busy||!hasFrame()||m_recording||m_private)return;
 m_busy=true;m_saved.clear();clearFrame();emit changed();const int current=generation;
 call(microphoneConsent?"StartRecordingWithAudio":"StartRecording",microphoneConsent?QVariantList{token,true}:QVariantList{token},[this,current](QVariant){
  if(current!=generation)return;m_busy=false;m_recording=true;m_seconds=0;clock.start();m_message=QStringLiteral("Nagrywanie — maksymalnie 60 sekund.");emit changed();
 });
}
void CaptureController::stopRecording(){
 if(m_busy||!m_recording||m_private)return;
 m_busy=true;frames.stop();clearFrame();clock.stop();emit changed();const int current=generation;
 call("StopRecording",{token},[this,current](QVariant value){if(current!=generation)return;
  m_saved=json(value.toString()).value("reference").toString();m_recording=false;m_active=false;m_busy=false;
  m_message=QStringLiteral("Film zapisany w galerii.");emit saved("video");release();
 });
}
void CaptureController::release(){
 const auto current=token;const bool wasRecording=m_recording;reset();
 if(wasRecording)m_message=QStringLiteral("Nagrywanie zakończone. Sprawdź zapis w galerii.");emit changed();
 if(!current.isEmpty())call("Release",{current},[](QVariant){},[](QString){});
}
void CaptureController::gallery(){release();QProcess::startDetached("ethercamera-media",{});}
