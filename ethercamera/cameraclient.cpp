#include "cameraclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
static const QString service="com.etherneco.EtherCamera1",path="/com/etherneco/EtherCamera1";
CameraClient::CameraClient(QObject *parent):QObject(parent){
 m_state={{"ready",false}};
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){
  if(qEnvironmentVariableIsSet("ETHERSHELL_MOBILE_TEST_OUTPUT")){QFile snapshot(qEnvironmentVariable("ETHERCAMERA_QA_STATE"));if(snapshot.open(QIODevice::ReadOnly))update(QString::fromUtf8(snapshot.readAll()));}
  return;
 }
 auto bus=QDBusConnection::sessionBus();
 bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){if(owner.isEmpty()){m_state={{"ready",false}};emit changed();}else request("GetState");});
 request("GetState");
}
void CameraClient::update(const QString &document){auto json=QJsonDocument::fromJson(document.toUtf8());if(!json.isObject())return;m_state=json.object().toVariantMap();emit changed();}
void CameraClient::request(const QString &method,const QVariantList &args){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);
 msg.setArguments(args);
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,15000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch]{auto reply=watch->reply();if(reply.type()==QDBusMessage::ErrorMessage)m_message=reply.errorMessage();else if(!reply.arguments().isEmpty()){m_message.clear();update(reply.arguments().first().toString());}emit changed();watch->deleteLater();});
}
void CameraClient::refresh(){request("Refresh");}
void CameraClient::configure(const QVariantMap &data){request("Configure",{QString::fromUtf8(QJsonDocument::fromVariant(data).toJson(QJsonDocument::Compact))});}
