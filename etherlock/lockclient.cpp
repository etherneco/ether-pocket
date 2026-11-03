#include "lockclient.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
static const QString name="com.etherneco.EtherLock1",path="/com/etherneco/EtherLock1";
LockClient::LockClient(QObject *parent):QObject(parent){
 auto bus=QDBusConnection::sessionBus();bus.connect(name,path,name,"Changed",this,SLOT(update(QString)));
 auto watch=new QDBusServiceWatcher(name,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){if(owner.isEmpty()){m_state={{"ready",false},{"locked",m_required}};m_message="Locker coordinator unavailable";emit changed();}else refresh();});
 m_poll.setInterval(3000);connect(&m_poll,&QTimer::timeout,this,&LockClient::refresh);m_poll.start();refresh();
}
void LockClient::update(const QString &document){auto d=QJsonDocument::fromJson(document.toUtf8());if(!d.isObject())return;m_state=d.object().toVariantMap();m_required=m_state.value("enabled").toBool();emit changed();}
void LockClient::call(const QString &method,const QVariantList &args){
 if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT"))return;
 auto msg=QDBusMessage::createMethodCall(name,path,name,method);msg.setArguments(args);
 auto watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,7000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method]{auto reply=watch->reply();if(reply.type()==QDBusMessage::ErrorMessage){m_message=reply.errorMessage();if(method=="GetState")m_state={{"ready",false},{"locked",m_required}};}else if(method=="GetState"||method=="Configure"){update(reply.arguments().value(0).toString());m_message.clear();}else if(method=="Lock"&&!reply.arguments().value(0).toBool())m_message="Lock enforcement not confirmed; inspect recovery diagnostics";emit changed();watch->deleteLater();});
}
void LockClient::refresh(){call("GetState");}
void LockClient::lock(){call("Lock",{QString("manual")});}
void LockClient::configure(const QVariantMap &patch){call("Configure",{QString::fromUtf8(QJsonDocument::fromVariant(patch).toJson(QJsonDocument::Compact))});}
bool LockClient::beforeBlank(){
 if(!m_required||!m_state.value("config").toMap().value("lockOnScreenOff",true).toBool())return true;
 // Explicit blanking is permitted only after a trusted enforcement acknowledgement.
 auto msg=QDBusMessage::createMethodCall(name,path,name,"Lock");msg.setArguments({QString("screen-off")});
 auto reply=QDBusConnection::sessionBus().call(msg,QDBus::Block,6500);
 const bool ok=reply.type()!=QDBusMessage::ErrorMessage&&reply.arguments().value(0).toBool();
 if(!ok){m_message="Screen off blocked: authentication lock was not confirmed";emit changed();}return ok;
}
