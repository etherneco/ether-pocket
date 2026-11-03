#include "client.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
static const QString name="com.etherneco.EtherShare1",path="/com/etherneco/EtherShare1";
ShareClient::ShareClient(QObject *parent):QObject(parent){
 m_state={{"available",false},{"message","EtherShare service is unavailable"}};
 auto bus=QDBusConnection::systemBus();
 bus.connect(name,path,name,"Changed",this,SLOT(update(QString)));
 bus.connect(name,path,name,"Notice",this,SLOT(backendNotice(QString,QString)));
 auto *watcher=new QDBusServiceWatcher(name,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watcher,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){
  if(owner.isEmpty()){m_state["available"]=false;m_state["message"]="EtherShare service stopped; recovery journal will be checked on restart";emit changed();}else refresh();
 });
 QTimer::singleShot(0,this,&ShareClient::refresh);
}
void ShareClient::update(const QString &json){
 QJsonParseError error;auto d=QJsonDocument::fromJson(json.toUtf8(),&error);
 if(error.error==QJsonParseError::NoError&&d.isObject()){m_state=d.object().toVariantMap();emit changed();}
}
void ShareClient::backendNotice(const QString &title,const QString &message){emit notice(title,message);}
void ShareClient::refresh(){
 auto message=QDBusMessage::createMethodCall(name,path,name,"GetState");
 auto *w=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message,10000),this);
 connect(w,&QDBusPendingCallWatcher::finished,this,[this,w]{auto r=w->reply();if(r.type()!=QDBusMessage::ErrorMessage&&!r.arguments().isEmpty())update(r.arguments().first().toString());w->deleteLater();});
}
void ShareClient::call(const QString &method,const QVariantList &args){
 if(busy())return;
 if(qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT")){emit notice("Internet Sharing","Network changes are disabled in the isolated preview");return;}
 m_pending=true;emit changed();
 auto message=QDBusMessage::createMethodCall(name,path,name,method);message.setArguments(args);message.setInteractiveAuthorizationAllowed(true);
 auto *w=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message,90000),this);
 connect(w,&QDBusPendingCallWatcher::finished,this,[this,w,method]{m_pending=false;auto r=w->reply();if(r.type()==QDBusMessage::ErrorMessage){m_state["message"]=r.errorMessage();emit notice("Internet Sharing",r.errorMessage());}else if(method=="RevealHotspotPassword"&&!r.arguments().isEmpty()){m_password=r.arguments().first().toString();QTimer::singleShot(30000,this,[this]{m_password.clear();emit changed();});}emit changed();refresh();w->deleteLater();});
}
void ShareClient::start(const QString &m,const QString &i,bool replace){call("Start",{m,i,replace});}
void ShareClient::stop(const QString &m){call("Stop",{m});}
void ShareClient::configure(const QVariantMap &v){call("Configure",{QString::fromUtf8(QJsonDocument(QJsonObject::fromVariantMap(v)).toJson(QJsonDocument::Compact))});}
void ShareClient::checkInternet(){call("Refresh");}
void ShareClient::startConcurrentHotspot(const QString &parent){call("StartConcurrentHotspot",{parent});}
void ShareClient::revealPassword(){call("RevealHotspotPassword");}
void ShareClient::renameClient(const QString &mac,const QString &name){call("RenameClient",{mac,name});}
