#include "fingerprintclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
static const QString service="com.etherneco.EtherFingerprint1";
FingerprintClient::FingerprintClient(QObject *parent):QObject(parent) {
 auto *watch=new QDBusServiceWatcher(service,QDBusConnection::systemBus(),QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){++m_generation;m_state={{"ready",false}};emit changed();if(!owner.isEmpty())refresh();});
 refresh();
}
void FingerprintClient::refresh() {
 // Read-only diagnostics are safe in isolated development sessions too.
 const auto generation=++m_generation;
 auto msg=QDBusMessage::createMethodCall(service,"/com/etherneco/EtherFingerprint1",service,"GetState");
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg,5000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,generation]{
  if(generation!=m_generation){watch->deleteLater();return;}
  auto reply=watch->reply();m_state={{"ready",false}};
  if(reply.type()!=QDBusMessage::ErrorMessage && reply.arguments().size()==1){
   auto doc=QJsonDocument::fromJson(reply.arguments().first().toString().toUtf8());
   if(doc.isObject())m_state=doc.object().toVariantMap();
  }
  emit changed();watch->deleteLater();
 });
}
