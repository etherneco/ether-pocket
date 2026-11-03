#include "sms.h"
#include "mobile.h"
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusPendingCallWatcher>
#include <QDBusServiceWatcher>
#include <QCryptographicHash>
#include <QDateTime>
static const QString service="org.freedesktop.ModemManager1", messaging=service+".Modem.Messaging",sms=service+".Sms",props="org.freedesktop.DBus.Properties";
bool smsCreationRejected(const QString &name){
 return name.endsWith(".Unauthorized")||name.endsWith(".AccessDenied")||name.endsWith(".InvalidArgs")||name.endsWith(".Unsupported");
}
MobileSmsTransport::MobileSmsTransport(Mobile *mobile,QObject *parent,bool receiveMessages):ISmsTransport(parent),m_receiveMessages(receiveMessages),m_mobile(mobile){
 auto bus=QDBusConnection::systemBus();
 connect(mobile,&Mobile::changed,this,&MobileSmsTransport::discover);
 if(m_receiveMessages)bus.connect(service,QString(),messaging,"Added",this,SLOT(added(QDBusObjectPath,bool,QDBusMessage)));
 if(m_receiveMessages)bus.connect(service,QString(),props,"PropertiesChanged",this,SLOT(properties(QString,QVariantMap,QStringList,QDBusMessage)));
 auto *watch=new QDBusServiceWatcher(service,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
 connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](const QString &,const QString &,const QString &owner){
  ++m_generation;m_owner=owner;m_path.clear();m_scanning=false;
  for(const auto &id:m_pending)emit stateChanged(id,"Uncertain",{},"Modem service restarted. Verify with the recipient before sending again.");
  m_pending.clear();m_knownPaths.clear();m_reports.clear();m_caps.clear();emit capabilitiesChanged();
 });
 m_owner=bus.interface()->serviceOwner(service).value();discover();
}
void MobileSmsTransport::call(const QString &path,const QString &iface,const QString &method,const QVariantList &args,std::function<void(QDBusMessage)> done){
 auto msg=QDBusMessage::createMethodCall(service,path,iface,method);msg.setArguments(args);
 if(method=="Create"||method=="Send")msg.setInteractiveAuthorizationAllowed(true);
 auto *w=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg,30000),this);
 connect(w,&QDBusPendingCallWatcher::finished,this,[w,done]{auto r=w->reply();w->deleteLater();done(r);});
}
void MobileSmsTransport::discover(){
 const auto s=m_mobile->snapshot();const QString path=s.value("selected").toString();
 const bool available=s.value("smsInterface").toBool(),wasAvailable=m_caps.value("available").toBool();
 m_caps={{"backend","EtherMobile / ModemManager"},{"available",available},{"canSend",available&&s.value("simReady").toBool()&&s.value("registered").toBool()},
 {"canReceive",available},{"sim",s.value("sim")},{"simReady",s.value("simReady")},{"network",s.value("state")},
 {"deliveryReports","Requested when enabled; delivery requires a matching report"},{"simStorage",available?"Exposed by modem; no storage changes made":"Unavailable"}};
 emit capabilitiesChanged();
 if(path!=m_path){
  ++m_generation;
  for(const auto &id:m_pending)emit stateChanged(id,"Uncertain",{},"Selected modem changed. Verify with recipient before resending.");
  m_pending.clear();m_knownPaths.clear();m_reports.clear();m_scanning=false;m_path=path;if(available)scan();
 }else if(available&&!wasAvailable)scan();
}
void MobileSmsTransport::scan(){
 if(!m_receiveMessages||m_scanning||m_path.isEmpty()||!m_caps.value("available").toBool())return;
 m_scanning=true;const auto generation=m_generation;
 call(m_path,messaging,"List",{},[this,generation](QDBusMessage r){
  if(generation!=m_generation)return;
  m_scanning=false;
  if(r.type()!=QDBusMessage::ErrorMessage&&!r.arguments().isEmpty())for(const auto &p:qdbus_cast<QList<QDBusObjectPath>>(r.arguments().first())){m_knownPaths.insert(p.path());read(p.path());}
 });
}
void MobileSmsTransport::added(const QDBusObjectPath &path,bool,const QDBusMessage &message){if(message.path()!=m_path)return;m_knownPaths.insert(path.path());read(path.path());}
void MobileSmsTransport::properties(const QString &iface,const QVariantMap &,const QStringList &,const QDBusMessage &message){
 if(iface==sms)read(message.path());else if(iface==messaging&&message.path()==m_path)scan();
}
void MobileSmsTransport::read(const QString &path){
 if(!m_receiveMessages||!m_caps.value("available").toBool()||!m_knownPaths.contains(path))return;
 const auto generation=m_generation;
 call(path,props,"GetAll",{sms},[this,path,generation](QDBusMessage r){
  if(generation!=m_generation||r.type()==QDBusMessage::ErrorMessage||r.arguments().isEmpty())return;
  const auto p=qdbus_cast<QVariantMap>(r.arguments().first());const uint state=p.value("State").toUInt();
  if(m_pending.contains(path)&&state==5){
   emit stateChanged(m_pending.value(path),"Submitted to network",m_owner+path,{});
   if(m_reports.contains(path)&&p.contains("MessageReference"))m_reports[path]["reference"]=p.value("MessageReference");
  }
  if(state==3&&p.value("PduType").toUInt()==3&&p.value("DeliveryState").toUInt()==0&&p.contains("MessageReference")){
   const auto timestamp=QDateTime::fromString(p.value("Timestamp").toString(),Qt::ISODate);
   QStringList matches;
   for(auto it=m_reports.cbegin();it!=m_reports.cend();++it){
    const auto sent=it.value();const auto start=QDateTime::fromString(sent.value("start").toString(),Qt::ISODateWithMs);
    const auto age=start.secsTo(timestamp);
    if(timestamp.isValid()&&age>=-60&&age<172800&&sent.contains("reference")&&sent.value("number")==p.value("Number")&&sent.value("reference").toUInt()==p.value("MessageReference").toUInt())matches<<it.key();
   }
   // Reused modem references must never produce an ambiguous Delivered status.
   if(matches.size()==1){const auto candidate=matches.first();emit stateChanged(m_pending.value(candidate),"Delivered",m_owner+candidate,{});m_pending.remove(candidate);m_reports.remove(candidate);}
   return;
  }
  // ModemManager reconstructs multipart messages. Only state RECEIVED is complete.
  if(state!=3||p.value("PduType").toUInt()!=1)return;
  const auto time=QDateTime::fromString(p.value("Timestamp").toString(),Qt::ISODate);
  if(!time.isValid()||p.value("Text").toString().isEmpty())return;
  const auto number=p.value("Number").toString(),text=p.value("Text").toString();
  QByteArray identity=number.toUtf8();identity+='\0';identity+=time.toUTC().toString(Qt::ISODateWithMs).toUtf8();identity+='\0';identity+=text.toUtf8();
  emit incoming({{"number",number},{"text",text},{"timestamp",time.toUTC().toString(Qt::ISODateWithMs)},
   {"key",QString::fromLatin1(QCryptographicHash::hash(identity,QCryptographicHash::Sha256).toHex())}});
 });
}
void MobileSmsTransport::send(const QString &id,const QString &number,const QString &text,bool report){
 if(!m_caps.value("canSend").toBool()){emit stateChanged(id,"Failed",{},"SMS unavailable: check SIM readiness and network registration.");return;}
 const auto generation=m_generation;
 emit stateChanged(id,"Sending",{},{});
 call(m_path,messaging,"Create",{QVariantMap{{"number",number},{"text",text},{"delivery-report-request",report}}},[this,id,number,report,generation](QDBusMessage r){
  if(generation!=m_generation){emit stateChanged(id,"Uncertain",{},"Modem changed during submission. Verify before resending.");return;}
  if(r.type()==QDBusMessage::ErrorMessage||r.arguments().isEmpty()){
   m_caps["lastErrorName"]=r.errorName();emit capabilitiesChanged();
   const auto name=r.errorName();
   const bool denied=name.endsWith(".Unauthorized")||name.endsWith(".AccessDenied");
   const bool rejected=smsCreationRejected(name);
   emit stateChanged(id,rejected?"Failed":"Uncertain",{},denied?"ModemManager denied SMS permission. Check the desktop user's messaging authorization.":"SMS creation was not confirmed ("+name+"). No automatic retry; check modem and recipient.");return;}
  const auto path=qvariant_cast<QDBusObjectPath>(r.arguments().first()).path();m_knownPaths.insert(path);m_pending[path]=id;if(report)m_reports[path]={{"number",number},{"start",QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs)}};
  emit stateChanged(id,"Sent to modem",m_owner+path,{});
  call(path,sms,"Send",{},[this,id,path,generation](QDBusMessage result){
   if(generation!=m_generation)return;
   emit stateChanged(id,result.type()==QDBusMessage::ErrorMessage?"Uncertain":"Submitted to network",m_owner+path,
    result.type()==QDBusMessage::ErrorMessage?"Network submission not confirmed. Verify with the recipient before composing a new send.":QString());
   read(path);
  });
 });
}
