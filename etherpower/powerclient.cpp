#include "powerclient.h"
#include "core.h"
#include "media.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QGuiApplication>
#include <QScreen>
static const QString service="com.etherneco.EtherPower1",path="/com/etherneco/EtherPower1";
PowerClient::PowerClient(Core *core,Media *media,QObject *parent):QObject(parent),m_core(core),m_media(media){
 m_state={{"ready",false},{"message","EtherPower service unavailable"}};
 auto bus=QDBusConnection::systemBus();
 bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));
 bus.connect(service,path,service,"Notice",this,SLOT(backendNotice(QString,QString)));
 bus.connect(service,path,service,"Event",this,SLOT(backendEvent(QString,QString)));
 auto *watcher=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watcher,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){if(owner.isEmpty()){m_state={{"ready",false},{"message","Power service stopped; current policy evidence unavailable"}};m_core->setPowerState(m_state);emit changed();}else call("GetState");});
 m_reportTimer.setSingleShot(true);m_reportTimer.setInterval(400);connect(&m_reportTimer,&QTimer::timeout,this,&PowerClient::reportDisplay);
 connect(m_core,&Core::telemetryChanged,this,[this]{m_reportTimer.start();});
 connect(m_media,&Media::powerStateChanged,this,[this]{m_reportTimer.start();});
 connect(m_media,&Media::powerMenuRequested,this,&PowerClient::powerMenuRequested);
 connect(qGuiApp,&QGuiApplication::screenAdded,this,[this]{displayPolicy();});
 connect(qGuiApp,&QGuiApplication::screenRemoved,this,[this]{displayPolicy();});
 QTimer::singleShot(0,this,[this]{call("GetState");});
}
void PowerClient::update(const QString &document){
 auto parsed=QJsonDocument::fromJson(document.toUtf8());if(!parsed.isObject())return;
 m_state=parsed.object().toVariantMap();m_core->setPowerState(m_state);
 displayPolicy();emit changed();
 if(m_historyHours&&!m_state.value("busy").toBool())loadHistory(m_historyHours);
}
void PowerClient::backendNotice(const QString &title,const QString &message){emit notice(title,message);}
void PowerClient::backendEvent(const QString &kind,const QString &document){
 if(kind=="ShutdownRequested"){m_message="Emergency battery policy requests shutdown confirmation";emit powerMenuRequested();}
 if(kind=="ResumeCompleted"){m_media->setScreenBlank(false);m_core->refresh();refresh();}
 Q_UNUSED(document)
}
void PowerClient::call(const QString &method,const QVariantList &args){
 auto message=QDBusMessage::createMethodCall(service,path,service,method);message.setArguments(args);message.setInteractiveAuthorizationAllowed(true);
 ++m_pending;emit changed();auto *w=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message,90000),this);
 connect(w,&QDBusPendingCallWatcher::finished,this,[this,w,method]{
  --m_pending;auto reply=w->reply();
  if(reply.type()==QDBusMessage::ErrorMessage){m_message="Power request failed: "+reply.errorMessage();}
  else if(method=="GetState"&&!reply.arguments().isEmpty())update(reply.arguments().first().toString());
  else if(method=="GetHistory"&&!reply.arguments().isEmpty()){
   auto d=QJsonDocument::fromJson(reply.arguments().first().toString().toUtf8()).object();
   if(d["ready"].toBool())m_history=d["samples"].toArray().toVariantList();
  }else if(method=="GetProcessImpact"&&!reply.arguments().isEmpty()){
   m_processes=QJsonDocument::fromJson(reply.arguments().first().toString().toUtf8()).object()["processes"].toArray().toVariantList();
  }else if(method!="ReportDisplayState")m_message="Request completed; inspect effective hardware values";
  emit changed();w->deleteLater();
 });
}
void PowerClient::refresh(){call("Refresh");}
void PowerClient::profile(const QString &name,const QString &custom){if(busy())return;if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT")){m_message="Profile writes are disabled in isolated UI acceptance";emit changed();return;}call("ApplyProfile",{name,custom});}
void PowerClient::configure(const QVariantMap &values){if(busy())return;if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT")){m_message="Power preference changes are disabled in isolated UI acceptance";emit changed();return;}call("Configure",{QString::fromUtf8(QJsonDocument(QJsonObject::fromVariantMap(values)).toJson(QJsonDocument::Compact))});}
void PowerClient::restore(){if(!busy()&&!qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT"))call("RestoreOriginal");}
void PowerClient::powerAction(const QString &action){if(!busy()&&!qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT"))call("PowerAction",{action});}
void PowerClient::loadHistory(int hours){if(!QList<int>{1,24,168,720}.contains(hours))return;m_historyHours=hours;call("GetHistory",{quint32(hours)});}
void PowerClient::inspectProcesses(){if(!busy())call("GetProcessImpact");}
void PowerClient::setBrightness(int value){
 if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT"))return;
 const auto key=m_state.value("externalPower").toBool()?"powerBrightnessExternal":"powerBrightnessBattery";
 m_core->setting(key,qBound(1,value,100));m_core->control("brightness",QString::number(qBound(1,value,100)));
}
void PowerClient::screenOff(){m_media->setScreenBlank(true);m_reportTimer.start();}
void PowerClient::wake(){m_media->setScreenBlank(false);m_reportTimer.start();}
void PowerClient::displayPolicy(){
 if(!m_state.value("ready").toBool()||qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT"))return;
 const auto config=m_state.value("config").toMap();const bool external=m_state.value("externalPower").toBool();
 const auto mode=m_state.value("profileState").toMap().value("effective").toString();
 const int timeout=config.value(external?"externalTimeout":"batteryTimeout",external?300:60).toInt();
 m_media->setPowerTimeout(timeout,config.value("externalDisplayPolicy").toString()!="allow-blank");m_timeout=timeout;
 if(m_firstDisplay||external!=m_external){
  const int brightness=m_core->preferences().value(external?"powerBrightnessExternal":"powerBrightnessBattery",-1).toInt();
  if(brightness>0)m_core->control("brightness",QString::number(brightness));
 }
 if(mode=="power-saver"&&m_lastProfile!="power-saver"){
  m_beforeSaver=m_core->telemetry().value("brightness").toInt();m_saverLevel=qMin(m_beforeSaver,config.value("saverBrightness",25).toInt());
  if(m_saverLevel>0)m_core->control("brightness",QString::number(m_saverLevel));
 }else if(mode!="power-saver"&&m_lastProfile=="power-saver"&&m_beforeSaver>0&&m_core->telemetry().value("brightness").toInt()==m_saverLevel){
  m_core->control("brightness",QString::number(m_beforeSaver));m_beforeSaver=-1;
 }
 m_lastProfile=mode;m_firstDisplay=false;m_external=external;m_reportTimer.start();
}
void PowerClient::reportDisplay(){
 if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT")||!m_state.value("ready").toBool())return;
 QVariantMap data{{"timeoutSeconds",m_media->property("powerTimeout")},{"brightnessPercent",m_core->telemetry().value("brightness")},
  {"screenBlank",m_media->property("screenBlank")},{"externalConnected",QGuiApplication::screens().size()>1},
  {"policy","Existing software blanker; no DPMS power-down"}};
 if(data==m_session)return;m_session=data;emit changed();
 call("ReportDisplayState",{QString::fromUtf8(QJsonDocument(QJsonObject::fromVariantMap(data)).toJson(QJsonDocument::Compact))});
}
