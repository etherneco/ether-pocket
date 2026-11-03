#include "notificationclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QStandardPaths>
static const QString service="com.etherneco.EtherNotifications1",path="/com/etherneco/EtherNotifications1";
NotificationClient::NotificationClient(QObject *parent):QObject(parent){
 m_refresh.setSingleShot(true);m_refresh.setInterval(40);connect(&m_refresh,&QTimer::timeout,this,&NotificationClient::refresh);
 m_bannerTimer.setSingleShot(true);m_bannerTimer.setInterval(6000);connect(&m_bannerTimer,&QTimer::timeout,this,&NotificationClient::nextBanner);
 m_lease.setInterval(60000);connect(&m_lease,&QTimer::timeout,this,[this]{if(!m_session.isEmpty())command("session",0,m_session);});
 // Development sessions use their own private bus/store, never host notification state.
 auto bus=QDBusConnection::sessionBus();
 bus.connect(service,path,service,"Changed",this,SLOT(scheduleRefresh()));
 bus.connect(service,path,service,"Banner",this,SLOT(incoming(uint)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){
  m_queue.clear();m_banner.clear();m_bannerTimer.stop();m_state={{"ready",false}};emit changed();
  if(!owner.isEmpty()){if(!m_session.isEmpty())command("session",0,m_session);refresh();}
 });
 refresh();m_lease.start();
}
void NotificationClient::scheduleRefresh(){if(!m_refresh.isActive())m_refresh.start();}
void NotificationClient::refresh(){if(m_loading){m_again=true;return;}m_loading=true;call("GetState",{});}
void NotificationClient::call(const QString& method,const QVariantList& args){
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);msg.setArguments(args);
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,5000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method,args]{
  auto reply=watch->reply();if(method=="GetState")m_loading=false;
  if(reply.type()==QDBusMessage::ErrorMessage){m_message=reply.errorMessage();if(method=="GetState"){m_state={{"ready",false}};m_banner.clear();m_queue.clear();}}
  else if(method=="GetState"){accept(reply.arguments().value(0).toString());m_message.clear();}
  else if(args.value(0).toString()=="export"){
   const auto dir=QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)+"/ethernotifications/exports";
   QDir().mkpath(dir);QFile::setPermissions(dir,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);
   QFile file(dir+"/redacted-"+QString::number(QDateTime::currentMSecsSinceEpoch())+".json");
   if(file.open(QIODevice::WriteOnly|QIODevice::NewOnly)){file.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);file.write(reply.arguments().value(0).toString().toUtf8());m_message="Saved redacted history: "+file.fileName();}
  }
  if(m_again&&!m_loading){m_again=false;scheduleRefresh();}
  emit changed();watch->deleteLater();
 });
}
void NotificationClient::accept(const QString& document){
 auto json=QJsonDocument::fromJson(document.toUtf8());if(!json.isObject())return;m_state=json.object().toVariantMap();
 if(m_state.value("locked").toBool()||m_state.value("sleeping").toBool()||m_state.value("callActive").toBool()){
  m_banner.clear();m_queue.clear();m_bannerTimer.stop();
 }else{
  bool current=false;for(auto v:m_state.value("cards").toList())if(v.toMap().value("id")==m_banner.value("id")&&v.toMap().value("canBanner").toBool())current=true;
  if(!m_banner.isEmpty()&&!current){m_banner.clear();m_bannerTimer.stop();}
  if(m_banner.isEmpty()&&!m_queue.isEmpty())nextBanner();
 }
}
void NotificationClient::command(const QString& action,uint id,const QVariantMap& data){call("Command",{action,id,QString::fromUtf8(QJsonDocument::fromVariant(data).toJson(QJsonDocument::Compact))});}
void NotificationClient::configure(const QVariantMap& data){command("configure",0,data);}
void NotificationClient::appPolicy(const QString& app,const QVariantMap& patch){auto config=m_state.value("config").toMap();auto apps=config.value("apps").toMap();auto p=apps.value(app).toMap();for(auto it=patch.begin();it!=patch.end();++it)p[it.key()]=it.value();apps[app]=p;configure({{"apps",apps}});}
void NotificationClient::session(bool locked,bool callActive,bool screenOff){m_session={{"locked",locked},{"callActive",callActive},{"screenOff",screenOff}};if(locked||callActive||screenOff){m_queue.clear();m_banner.clear();m_bannerTimer.stop();emit changed();}command("session",0,m_session);}
void NotificationClient::incoming(uint id){if(!m_queue.contains(id)&&m_queue.size()<8)m_queue.append(id);scheduleRefresh();}
void NotificationClient::nextBanner(){
 m_banner.clear();m_bannerTimer.stop();
 if(m_state.value("locked").toBool()||m_state.value("sleeping").toBool()||m_state.value("callActive").toBool()){m_queue.clear();emit changed();return;}
 while(!m_queue.isEmpty()&&m_banner.isEmpty()){
  auto id=m_queue.takeFirst();for(auto v:m_state.value("cards").toList()){auto card=v.toMap();if(card.value("id").toUInt()==id&&card.value("canBanner").toBool()){m_banner=card;break;}}
 }
 if(!m_banner.isEmpty())m_bannerTimer.start();emit changed();
}
