#include "sensorclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
static const QString service="com.etherneco.EtherSensors1",path="/com/etherneco/EtherSensors1";
SensorClient::SensorClient(QObject *parent):QObject(parent){
 m_state={{"ready",false}};
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){
  if(qEnvironmentVariableIsSet("ETHERSHELL_MOBILE_TEST_OUTPUT")){QFile f(qEnvironmentVariable("ETHERSENSORS_QA_STATE"));if(f.open(QIODevice::ReadOnly))update(QString::fromUtf8(f.readAll()));}
  return;
 }
 auto bus=QDBusConnection::sessionBus();bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){
  if(owner.isEmpty()){m_state={{"ready",false}};m_sample.clear();m_management.clear();m_token.clear();m_timer.stop();emit changed();}else refresh();
 });
 m_timer.setInterval(1100);connect(&m_timer,&QTimer::timeout,this,[this]{if(++m_reads>25)stopTest();else request("ReadLatest",{m_token});});refresh();
}
void SensorClient::update(const QString &text){auto j=QJsonDocument::fromJson(text.toUtf8());if(!j.isObject())return;m_state=j.object().toVariantMap();if(!m_state.value("activeSubscriptions").toInt()){m_sample.clear();m_timer.stop();m_token.clear();}emit changed();}
void SensorClient::request(const QString &method,const QVariantList &args){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);msg.setArguments(args);
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,5000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method]{
  auto reply=watch->reply();
  if(reply.type()==QDBusMessage::ErrorMessage){m_message=reply.errorMessage();if(method=="ReadLatest"){m_sample.clear();m_timer.stop();auto token=m_token;m_token.clear();if(!token.isEmpty())request("StopSubscription",{token});}}
  else if(!reply.arguments().isEmpty()){
   auto text=reply.arguments().first().toString();auto j=QJsonDocument::fromJson(text.toUtf8());m_message.clear();
   if(method=="TestSensor"){m_token=text;m_reads=0;m_timer.start();}
   else if(method=="GetManagement"||method=="ResolvePermission")m_management=j.object().toVariantMap();
   else if(method=="ReadLatest")m_sample=j.object().toVariantMap();
   else if(method=="ExportDiagnostics")m_message=text;
   else if(j.isObject())update(text);
  }
  emit changed();watch->deleteLater();
 });
}
void SensorClient::refresh(){request("GetState");}
void SensorClient::configure(const QVariantMap &v){request("Configure",{QString::fromUtf8(QJsonDocument::fromVariant(v).toJson(QJsonDocument::Compact))});}
void SensorClient::review(){request("GetManagement");}
void SensorClient::resolve(const QString &owner,bool allow){request("ResolvePermission",{owner,allow});}
void SensorClient::revoke(const QString &owner){request("RevokePermission",{owner});review();}
void SensorClient::test(const QString &ident){stopTest();request("TestSensor",{ident});}
void SensorClient::stopTest(){if(!m_token.isEmpty())request("StopSubscription",{m_token});m_timer.stop();m_token.clear();m_sample.clear();emit changed();}
void SensorClient::diagnostics(){request("ExportDiagnostics");}
