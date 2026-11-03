#include "hardwareclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QGuiApplication>
#include <QScreen>
#include <QProcess>
#include <QTimer>
#include <QSaveFile>
#include <QFileInfo>
#include <QTemporaryDir>
#include <QStandardPaths>
#include <QDir>
#include <QDateTime>
#include <QDataStream>
#include <QRegularExpression>
#include <cmath>
#include <memory>
static const QString name="com.etherneco.EtherHardware1",path="/com/etherneco/EtherHardware1";
HardwareClient::HardwareClient(QObject *parent):QObject(parent){
 m_state={{"available",false},{"ready",false},{"message","EtherHardware service is unavailable"}};
 auto bus=QDBusConnection::systemBus();
 bus.connect(name,path,name,"Changed",this,SLOT(update(QString)));
 auto *watcher=new QDBusServiceWatcher(name,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watcher,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){
  if(owner.isEmpty()){m_state={{"available",false},{"ready",false},{"components",QVariantList()},{"capabilities",QVariantList()},{"message","Hardware service stopped; previous evidence invalidated"}};emit changed();}else fetch();
 });
 QTimer::singleShot(0,this,&HardwareClient::fetch);
}
void HardwareClient::update(const QString &json){auto doc=QJsonDocument::fromJson(json.toUtf8());if(doc.isObject()){m_state=doc.object().toVariantMap();emit changed();}}
void HardwareClient::fetch(){call("GetState");}
void HardwareClient::call(const QString &method,const QVariantList &args,const QString &format){
 auto request=QDBusMessage::createMethodCall(name,path,name,method);request.setArguments(args);request.setInteractiveAuthorizationAllowed(true);
 ++m_pending;emit changed();
 auto *watcher=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(request,65000),this);
 connect(watcher,&QDBusPendingCallWatcher::finished,this,[this,watcher,method,format]{
  --m_pending;const auto reply=watcher->reply();
  if(reply.type()==QDBusMessage::ErrorMessage)m_message="Hardware request failed: "+reply.errorMessage();
  else if(method=="GetState"&&!reply.arguments().isEmpty())update(reply.arguments().first().toString());
  else if(method=="GetHistory"&&!reply.arguments().isEmpty())m_history=QJsonDocument::fromJson(reply.arguments().first().toString().toUtf8()).array().toVariantList();
  else if(method=="ExportReport"&&!reply.arguments().isEmpty()){
   const auto folder=QStandardPaths::writableLocation(QStandardPaths::DocumentsLocation)+"/EtherHardware";QDir().mkpath(folder);
   const auto file=folder+"/hardware-"+QDateTime::currentDateTimeUtc().toString("yyyyMMdd-HHmmss-zzz")+(format=="json"?".json":".txt");
   QSaveFile out(file);const auto bytes=reply.arguments().first().toString().toUtf8();
   bool ok=out.open(QIODevice::WriteOnly);if(ok){out.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);ok=out.write(bytes)==bytes.size()&&out.commit();}
   m_message=ok?"Redacted report saved to "+file:"Report could not be saved";
  }else if(method=="ClearHistory"){m_message="Shared diagnostic history cleared";loadHistory();}
  else if(method=="RunDiagnostics"||method=="Refresh")m_message="Read-only hardware check requested";
  emit changed();watcher->deleteLater();
 });
}
void HardwareClient::refresh(const QString &category){if(!busy())call("Refresh",{category});}
void HardwareClient::diagnose(const QString &category){if(!busy())call("RunDiagnostics",{category});}
void HardwareClient::loadHistory(const QString &q,const QString &c){call("GetHistory",{q.left(128),c.left(256)});}
void HardwareClient::clearHistory(){if(!busy())call("ClearHistory");}
void HardwareClient::exportReport(const QString &f){if(f=="json"||f=="text")call("ExportReport",{f},f);}
void HardwareClient::inspectSession(){
 QVariantList displays;for(auto *s:QGuiApplication::screens())displays<<QVariantMap{{"name",s->name()},{"width",s->size().width()},{"height",s->size().height()},{"refreshHz",s->refreshRate()},{"scale",s->devicePixelRatio()},{"orientation",int(s->orientation())}};
 m_session["displays"]=displays;m_session["shellRendering"]="Qt Quick software (existing EtherShell configuration)";
 for(const auto &kind:QStringList{"sinks","sources"}){
  auto *p=new QProcess(this);auto *timer=new QTimer(p);timer->setSingleShot(true);
  connect(timer,&QTimer::timeout,p,[p]{p->kill();});
  connect(p,&QProcess::errorOccurred,this,[this,p,kind](QProcess::ProcessError){m_session[kind]=QVariantList();m_message="Session audio inspection unavailable";emit changed();if(p->state()==QProcess::NotRunning)p->deleteLater();});
  connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p,kind](int code,QProcess::ExitStatus){
   QVariantList rows;for(auto v:QJsonDocument::fromJson(p->readAllStandardOutput()).array()){
    const auto o=v.toObject();rows<<QVariantMap{{"index",o["index"].toVariant()},{"state",o["state"].toString()},{"sampleSpec",o["sample_specification"].toString()},{"channels",o["channel_map"].toString()}};
   }m_session[kind]=rows;m_session[kind+"Status"]=code?"Service unavailable":"Session audio service readable; physical routing untested";emit changed();p->deleteLater();
  });
  p->start("pactl",{"--format=json","list",kind});timer->start(5000);
 }
 auto *gl=new QProcess(this);auto *timer=new QTimer(gl);timer->setSingleShot(true);connect(timer,&QTimer::timeout,gl,[gl]{gl->kill();});
 connect(gl,&QProcess::errorOccurred,this,[this,gl](QProcess::ProcessError){m_session["graphics"]="glxinfo unavailable; acceleration is not tested";emit changed();if(gl->state()==QProcess::NotRunning)gl->deleteLater();});
 connect(gl,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,gl](int code,QProcess::ExitStatus){
  QStringList values;const auto lines=QString::fromUtf8(gl->readAllStandardOutput()).split('\n');
  for(auto line:lines)if(line.startsWith("OpenGL vendor string:")||line.startsWith("OpenGL renderer string:")||line.startsWith("OpenGL version string:")||line.startsWith("direct rendering:"))values<<line;
  m_session["graphics"]=code||values.isEmpty()?"GLX context unavailable; acceleration is not tested":values.join("\n");emit changed();gl->deleteLater();
 });gl->start("glxinfo",{"-B"});timer->start(7000);emit changed();
}
void HardwareClient::mediaTest(const QString &kind){
 if(m_mediaRunning||(kind!="microphone"&&kind!="speaker"))return;
 if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT")){m_message="Media capture/playback is disabled in the isolated UI acceptance session";emit changed();return;}
 auto directory=std::make_shared<QTemporaryDir>();if(!directory->isValid())return;
 const auto file=directory->path()+"/test.wav";
 if(kind=="speaker"){
  QFile wav(file);if(!wav.open(QIODevice::WriteOnly))return;QDataStream out(&wav);out.setByteOrder(QDataStream::LittleEndian);
  const quint32 bytes=16000;out.writeRawData("RIFF",4);out<<quint32(36+bytes);out.writeRawData("WAVEfmt ",8);out<<quint32(16)<<quint16(1)<<quint16(1)<<quint32(16000)<<quint32(32000)<<quint16(2)<<quint16(16);out.writeRawData("data",4);out<<bytes;
  for(int i=0;i<8000;++i)out<<qint16(2500*std::sin(2*3.141592653589793*440*i/16000));wav.close();
 }
 auto *p=new QProcess(this);m_mediaRunning=true;++m_pending;m_message=kind=="microphone"?"Recording for three seconds to a private temporary file; it is deleted after this test":"Playing a quiet half-second tone through the current default output";emit changed();
 auto finish=[this,p,directory,kind,file](bool ok){
  m_mediaRunning=false;--m_pending;
  m_message=ok?(kind=="microphone"?"Capture produced audio data; the temporary recording has been deleted. Physical microphone quality is not verified.":"Playback completed. Confirm that you heard the tone; the selected physical speaker is not automatically certified."):"Media test failed; check the current audio route and permissions";
  emit changed();p->deleteLater();
 };
 connect(p,&QProcess::errorOccurred,this,[p,finish](QProcess::ProcessError error){if(error==QProcess::FailedToStart)finish(false);});
 connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[finish,file,kind](int code,QProcess::ExitStatus){finish((code==0||kind=="microphone")&&QFileInfo(file).size()>44);});
 p->start(kind=="microphone"?"parecord":"paplay",kind=="microphone"?QStringList{"--file-format=wav","--rate=16000","--channels=1",file}:QStringList{file});
 QTimer::singleShot(kind=="microphone"?3000:5000,p,[p]{if(p->state()!=QProcess::NotRunning){p->terminate();QTimer::singleShot(1000,p,[p]{if(p->state()!=QProcess::NotRunning)p->kill();});}});
}
void HardwareClient::planRepair(const QString &package){
 if(busy()||!QStringList{"iw","v4l-utils","mesa-utils","alsa-utils","pulseaudio-utils"}.contains(package))return;
 m_plan.clear();++m_pending;emit changed();auto *p=new QProcess(this);
 connect(p,&QProcess::errorOccurred,this,[this,p](QProcess::ProcessError e){if(e==QProcess::FailedToStart){--m_pending;m_message="Repair helper unavailable";emit changed();p->deleteLater();}});
 connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p](int code,QProcess::ExitStatus){--m_pending;auto data=QJsonDocument::fromJson(p->readAllStandardOutput()).object().toVariantMap();if(!code)m_plan=data;m_message=code?data.value("message","Tool compatibility check failed").toString():"Review the exact package plan before installing";emit changed();p->deleteLater();});
 p->start("/usr/libexec/etherhardware-repair",{"--plan",package});QTimer::singleShot(30000,p,[p]{if(p->state()!=QProcess::NotRunning)p->kill();});
}
void HardwareClient::installReviewedTool(){
 if(busy()||m_plan.isEmpty()||m_plan.value("alreadyInstalled").toBool())return;
 if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT")){m_message="Tool installation is disabled in isolated acceptance";emit changed();return;}
 auto *p=new QProcess(this);++m_pending;emit changed();
 connect(p,&QProcess::errorOccurred,this,[this,p](QProcess::ProcessError e){if(e==QProcess::FailedToStart){--m_pending;m_message="PolicyKit tool installer unavailable";emit changed();p->deleteLater();}});
 connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p](int code,QProcess::ExitStatus){--m_pending;auto data=QJsonDocument::fromJson(p->readAllStandardOutput()).object();m_message=data["message"].toString(code?"Installation cancelled or denied":"Tools installed; hardware recheck requested");m_plan.clear();emit changed();if(!code)refresh();p->deleteLater();});
 p->start("pkexec",{"/usr/libexec/etherhardware-repair",m_plan.value("package").toString(),m_plan.value("candidate").toString()});
}
