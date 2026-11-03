#include "locationclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
static const QString service="com.etherneco.EtherLocation1",path="/com/etherneco/EtherLocation1";
static QString json(const QVariantMap &value){return QString::fromUtf8(QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact));}
LocationClient::LocationClient(QObject *parent):QObject(parent){
 m_state={{"ready",false}};
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){
  if(qEnvironmentVariableIsSet("ETHERSHELL_MOBILE_TEST_OUTPUT")){QFile snapshot(qEnvironmentVariable("ETHERLOCATION_QA_STATE"));if(snapshot.open(QIODevice::ReadOnly))update(QString::fromUtf8(snapshot.readAll()));}
  return;
 }
 auto bus=QDBusConnection::sessionBus();
 bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){
  if(owner.isEmpty()){m_state={{"ready",false}};m_position.clear();m_token.clear();m_timer.stop();emit changed();}else refresh();
 });
 connect(&m_timer,&QTimer::timeout,this,[this]{if(!m_token.isEmpty())request("ReadUpdate",{m_token});});
 m_timer.setInterval(10000);refresh();
}
void LocationClient::update(const QString &document){auto j=QJsonDocument::fromJson(document.toUtf8());if(!j.isObject())return;m_state=j.object().toVariantMap();if(!m_state.value("live").toBool())m_position.clear();if(m_state.value("locked").toBool()){m_management.clear();m_position.clear();}emit changed();}
void LocationClient::request(const QString &method,const QVariantList &args){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);msg.setArguments(args);
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,15000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method]{
  auto reply=watch->reply();
  if(reply.type()==QDBusMessage::ErrorMessage){m_message=reply.errorMessage();if(method=="ReadUpdate")m_position.clear();}
  else if(!reply.arguments().isEmpty()){
   auto text=reply.arguments().first().toString();auto j=QJsonDocument::fromJson(text.toUtf8());m_message.clear();
   if(method=="StartUpdates"){m_token=text;m_timer.start();}
   else if(method=="RequestPermission")m_message="Permission requested. Review it in Settings → Location.";
   else if(method=="ExportHistory"||method=="ExportDiagnostics")m_message="Saved: "+text;
   else if(method=="GetManagement"||method=="ManageZone"||method=="DeleteHistory"||method=="GetHistoryForMap")m_management=j.object().toVariantMap();
   else if(method=="ReadUpdate"||method=="GetLocation"||method=="GetLastKnownLocation")m_position=j.object().toVariantMap();
   else if(method=="SetManualLocation")m_message="User-supplied location selected; this is not a GNSS fix.";
   else if(j.isObject())update(text);
  }
  emit changed();watch->deleteLater();
 });
}
void LocationClient::refresh(){request("GetState");}
void LocationClient::configure(const QVariantMap &v){request("Configure",{json(v)});}
void LocationClient::review(){request("GetManagement");}
void LocationClient::resolve(const QString &t,const QString &p,const QString &a,bool bg){request("ResolvePermission",{t,p,a,bg});}
void LocationClient::revoke(const QString &a,const QString &o){request("RevokePermission",{a,o});}
void LocationClient::testGnss(){request("TestGnss",{QVariant::fromValue(uint(90))});}
void LocationClient::requestPermission(bool precise){request("RequestPermission",{json({{"precision",precise?"precise":"approximate"}})});}
void LocationClient::startUpdates(bool precise){request("StartUpdates",{json({{"precision",precise?"precise":"approximate"},{"interval",10},{"timeout",300}})});}
void LocationClient::stopUpdates(){if(!m_token.isEmpty())request("StopUpdates",{m_token});m_timer.stop();m_token.clear();m_position.clear();emit changed();}
void LocationClient::historyExport(const QString &kind){request("ExportHistory",{kind});}
void LocationClient::deleteHistory(const QString &ids){request("DeleteHistory",{ids});}
void LocationClient::diagnostics(bool include){request("ExportDiagnostics",{include});}
void LocationClient::zone(const QString &id,const QVariantMap &v){request("ManageZone",{id,json(v)});}
void LocationClient::deleteZone(const QString &id){request("ManageZone",{id,"delete"});}
void LocationClient::manual(double lat,double lon){request("SetManualLocation",{json({{"latitude",lat},{"longitude",lon}})});}
void LocationClient::mapHistory(bool precise){request("GetHistoryForMap",{json({{"precision",precise?"precise":"approximate"}})});}
