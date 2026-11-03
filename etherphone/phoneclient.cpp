#include "phoneclient.h"
#include <QGuiApplication>
#include <QClipboard>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QDir>
#include <QStandardPaths>
#include <QDateTime>
#include <QUrl>
static const QString service="com.etherneco.EtherPhone1",path="/com/etherneco/EtherPhone1";
PhoneClient::PhoneClient(QObject *parent):QObject(parent){
 m_state={{"ready",false}};
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){
  if(qEnvironmentVariableIsSet("ETHERSHELL_MOBILE_TEST_OUTPUT")){
   QFile snapshot(qEnvironmentVariable("ETHERPHONE_QA_STATE"));if(snapshot.open(QIODevice::ReadOnly))update(QString::fromUtf8(snapshot.readAll()));
  }
  return;
 }
 auto bus=QDBusConnection::sessionBus();
 bus.connect(service,path,service,"Changed",this,SLOT(update(QString)));
 bus.connect(service,path,service,"Event",this,SLOT(event(QString,QString)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](QString,QString,QString owner){if(owner.isEmpty()){m_state={{"ready",false}};m_message="Telephony service unavailable";emit changed();}else refresh();});
 refresh();
}
void PhoneClient::update(const QString &document){auto d=QJsonDocument::fromJson(document.toUtf8());if(!d.isObject())return;m_state=d.object().toVariantMap();emit changed();}
void PhoneClient::event(const QString &kind,const QString&){if(kind=="Incoming")emit incoming();else if(kind=="OpenHistory")emit openHistory();}
void PhoneClient::call(const QString &method,const QVariantList &args,const QString &exportKind){
 if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1)return;
 auto msg=QDBusMessage::createMethodCall(service,path,service,method);msg.setArguments(args);++m_pending;emit changed();
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg,45000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,method,exportKind]{auto reply=watch->reply();--m_pending;
  if(reply.type()==QDBusMessage::ErrorMessage)m_message=reply.errorMessage();
  else if(method=="GetState")update(reply.arguments().value(0).toString());
  else if(!exportKind.isEmpty()){
   const QString folder=QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)+"/etherphone/exports";
   QDir().mkpath(folder);QFile::setPermissions(folder,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);
   const auto filename=folder+"/"+exportKind+"-"+QString::number(QDateTime::currentMSecsSinceEpoch())+(exportKind=="contacts"?".vcf":".json");
   QFile file(filename);const auto bytes=reply.arguments().value(0).toString().toUtf8();
   if(file.open(QIODevice::WriteOnly|QIODevice::NewOnly)){
    file.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);
    m_message=file.write(bytes)==bytes.size()?"Saved privately: "+filename:"Export write failed";
   }else m_message="Cannot create private export";
  }else{m_message="Request completed. Call progress follows modem observations.";refresh();}
  emit changed();watch->deleteLater();
 });
}
void PhoneClient::refresh(){call("GetState");}
void PhoneClient::command(const QString &action,const QString &target,const QVariantMap &data){call("Command",{action,target,QString::fromUtf8(QJsonDocument::fromVariant(data).toJson(QJsonDocument::Compact))});}
QString PhoneClient::pasteNumber()const{return QGuiApplication::clipboard()->text().left(128);}
void PhoneClient::importVcard(const QString &location){
 QUrl url(location);QString filePath=url.isLocalFile()?url.toLocalFile():location;
 QFile file(filePath);if(!file.open(QIODevice::ReadOnly)||file.size()>2000000){m_message="Choose a local vCard file up to 2 MB";emit changed();return;}
 command("import-vcard",{},{{"vcard",QString::fromUtf8(file.readAll())}});
}
void PhoneClient::exportFile(const QString &kind){call("Command",{kind=="contacts"?"export-vcard":"diagnostics",QString(),QStringLiteral("{}")},kind);}
