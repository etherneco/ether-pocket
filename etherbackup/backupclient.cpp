#include "backupclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
static const QString service="com.etherneco.EtherBackup1",path="/com/etherneco/EtherBackup1";
BackupClient::BackupClient(QObject *parent):QObject(parent){
 m_state={{"ready",false}};
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){
  if(qEnvironmentVariableIsSet("ETHERSHELL_MOBILE_TEST_OUTPUT")){QFile snapshot(qEnvironmentVariable("ETHERBACKUP_QA_STATE"));if(snapshot.open(QIODevice::ReadOnly)){m_details=QJsonDocument::fromJson(snapshot.readAll()).object().toVariantMap();m_state=m_details;m_private=false;}}
  return;
 }
 auto bus=QDBusConnection::systemBus();bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));bus.connect(service,path,service,"Event",this,SLOT(event(QString)));
 auto session=QDBusConnection::sessionBus();
 session.connect("com.etherneco.EtherLock1","/com/etherneco/EtherLock1","com.etherneco.EtherLock1","Changed",this,SLOT(privacy(QString)));
 auto lock=QDBusMessage::createMethodCall("com.etherneco.EtherLock1","/com/etherneco/EtherLock1","com.etherneco.EtherLock1","GetState");
 auto *initial=new QDBusPendingCallWatcher(session.asyncCall(lock,5000),this);
 connect(initial,&QDBusPendingCallWatcher::finished,this,[this,initial]{auto r=initial->reply();if(r.type()!=QDBusMessage::ErrorMessage&&!r.arguments().isEmpty())privacy(r.arguments().first().toString());initial->deleteLater();});
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){m_details.clear();m_preview.clear();m_selected.clear();++m_epoch;if(owner.isEmpty()){m_state={{"ready",false}};emit changed();}else refresh();});
 auto *lockWatch=new QDBusServiceWatcher("com.etherneco.EtherLock1",session,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(lockWatch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString){privacy("{}");});refresh();
}
void BackupClient::privacy(const QString &document){auto state=QJsonDocument::fromJson(document.toUtf8()).object();m_private=state.value("locked").toBool(true);++m_epoch;if(m_private){m_details.clear();m_preview.clear();m_selected.clear();m_message.clear();}emit changed();}
void BackupClient::update(const QString &document){auto j=QJsonDocument::fromJson(document.toUtf8());if(j.isObject()){m_state=j.object().toVariantMap();emit changed();}}
void BackupClient::request(const QString &method,const QVariantList &args){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 if(method!="GetState"&&m_private){m_message="Unlock the session before accessing backups.";emit changed();return;}
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);msg.setArguments(args);auto epoch=m_epoch;
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg,10800000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method,epoch]{
  auto reply=watch->reply();
  if(method!="GetState"&&(m_private||epoch!=m_epoch)){watch->deleteLater();return;}
  if(reply.type()==QDBusMessage::ErrorMessage)m_message=reply.errorMessage();
  else if(!reply.arguments().isEmpty()){
   auto text=reply.arguments().first().toString();auto result=QJsonDocument::fromJson(text.toUtf8()).object().toVariantMap();m_message.clear();
   if(method=="GetState")update(text);
   else if(method=="Inspect")m_details=result;
   else if(method=="Preview")m_preview=result;
   else if(method=="Restore"){m_message="Restored and validated in "+result.value("destination").toString();m_preview.clear();m_selected.clear();}
   else if(method=="RecoveryInfo")m_message=text;
   else m_message="Operation completed. Review backup details for the verification result.";
  }
  emit changed();watch->deleteLater();
 });
}
void BackupClient::refresh(){request("GetState");}
void BackupClient::inspect(){request("Inspect");}
void BackupClient::backup(const QString &profile,const QString &dest){request("Backup",{profile,dest});}
void BackupClient::verify(const QString &id){request("Verify",{id,"sample"});}
void BackupClient::select(const QString &id,const QString &prefix){m_selected=id;m_prefix=prefix;m_preview.clear();request("Preview",{id,prefix});}
void BackupClient::restore(){if(!m_preview.isEmpty())request("Restore",{m_preview.value("point").toString(),m_preview.value("selection").toString(),true});}
void BackupClient::protect(const QString &id){request("Protect",{id});}
void BackupClient::recoveryInfo(const QString &id){request("RecoveryInfo",{id});}
void BackupClient::event(const QString &kind){
 Q_UNUSED(kind)
 auto msg=QDBusMessage::createMethodCall("org.freedesktop.Notifications","/org/freedesktop/Notifications","org.freedesktop.Notifications","Notify");
 msg.setArguments({"EtherBackup",QVariant::fromValue(uint(0)),"document-save","Backup & Restore","A backup operation changed status. Unlock Settings to review it.",QStringList{},QVariantMap{{"category","system"}},-1});
 QDBusConnection::sessionBus().asyncCall(msg,3000);
}
