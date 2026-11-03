#include "updateclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QDBusUnixFileDescriptor>
#include <unistd.h>
#include <fcntl.h>
static const QString service="com.etherneco.EtherUpdate1",path="/com/etherneco/EtherUpdate1";
UpdateClient::UpdateClient(QObject *parent):QObject(parent){
 m_state={{"ready",false}};
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){
  if(qEnvironmentVariableIsSet("ETHERSHELL_MOBILE_TEST_OUTPUT")){QFile snapshot(qEnvironmentVariable("ETHERUPDATE_QA_STATE"));if(snapshot.open(QIODevice::ReadOnly))update(QString::fromUtf8(snapshot.readAll()));}
  return;
 }
 auto bus=QDBusConnection::systemBus();
 bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));
 bus.connect(service,path,service,"Event",this,SLOT(event(QString,QString)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){
  if(owner.isEmpty()){m_state={{"ready",false}};m_plan.clear();m_approval.clear();emit changed();}else refresh();
 });refresh();
}
void UpdateClient::update(const QString &document){auto j=QJsonDocument::fromJson(document.toUtf8());if(!j.isObject())return;m_state=j.object().toVariantMap();emit changed();}
void UpdateClient::request(const QString &method,const QVariantList &args){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);msg.setArguments(args);
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg,method=="Download"||method=="InstallApproved"?3600000:120000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method]{
  auto reply=watch->reply();
  if(reply.type()==QDBusMessage::ErrorMessage)m_message=reply.errorMessage();
  else if(!reply.arguments().isEmpty()){
   auto text=reply.arguments().first().toString();m_message.clear();
   if(method=="GetState")update(text);
   else if(method=="PrepareInstall"){
    m_plan=QJsonDocument::fromJson(text.toUtf8()).object().toVariantMap();m_approval=m_plan.take("approval").toString();
   }
   else if(method=="SetCredential")m_message="Token saved and connection verified.";
   else if(method=="RemoveCredential")m_message="Token removed. Public access only.";
  }
  if(method=="InstallApproved"){m_plan.clear();m_approval.clear();}
  emit changed();watch->deleteLater();
 });
}
void UpdateClient::event(const QString &kind,const QString &message){
 Q_UNUSED(kind)
 // EtherNotifications owns DND, delivery and history. No root GUI/notification daemon.
 auto msg=QDBusMessage::createMethodCall("org.freedesktop.Notifications","/org/freedesktop/Notifications","org.freedesktop.Notifications","Notify");
 msg.setArguments({"Software Updates",QVariant::fromValue(uint(0)),"system-software-update","EtherUpdate",message,QStringList{},QVariantMap{},-1});
 QDBusConnection::sessionBus().asyncCall(msg,3000);
}
void UpdateClient::refresh(){request("GetState");}
void UpdateClient::check(){request("CheckUpdates");}
void UpdateClient::saveToken(QString value){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 auto bytes=value.toUtf8();value.clear();
 if(bytes.size()<20||bytes.size()>4096){bytes.fill('\0');m_message="Enter only the API token (20–4096 characters).";emit changed();return;}
 int fds[2];
 if(::pipe2(fds,O_CLOEXEC)!=0){bytes.fill('\0');m_message="Secure token transfer unavailable.";emit changed();return;}
 // At most PIPE_BUF bytes, written before passing the FD, with the writer closed.
 const auto written=::write(fds[1],bytes.constData(),bytes.size());bytes.fill('\0');::close(fds[1]);
 if(written!=bytes.size()){::close(fds[0]);m_message="Secure token transfer failed.";emit changed();return;}
 QDBusUnixFileDescriptor fd(fds[0]);::close(fds[0]);
 request("SetCredential",{QVariant::fromValue(fd)});
}
void UpdateClient::removeToken(){request("RemoveCredential");}
void UpdateClient::download(const QString &id){request("Download",{id});}
void UpdateClient::prepare(const QString &id){m_plan.clear();m_approval.clear();request("PrepareInstall",{id});}
void UpdateClient::install(){if(!m_approval.isEmpty()){auto approval=m_approval;m_approval.clear();request("InstallApproved",{approval});}}
void UpdateClient::cancel(){request("CancelDownload");}
void UpdateClient::channel(const QString &p,const QString &c,bool confirmed){request("SetChannel",{p,c,confirmed});}
