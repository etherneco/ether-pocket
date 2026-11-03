#include "notificationclient.h"
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QJsonDocument>
#include <QTimer>
#include <QDebug>
int main(int argc,char**argv){
 QCoreApplication app(argc,argv);auto bus=QDBusConnection::sessionBus();
 if(!bus.registerService("com.etherneco.NotificationTestUI"))return 2;
 NotificationClient client;uint ident=0;QStringList errors;int stage=0;
 auto check=[&](bool ok,const QString&label){if(!ok)errors<<label;};
 auto send=[&]{auto msg=QDBusMessage::createMethodCall("org.freedesktop.Notifications","/org/freedesktop/Notifications","org.freedesktop.Notifications","Notify");msg.setArguments({QString("Qt test"),uint(0),QString("mail-unread"),QString("Client test"),QString("Private body"),QStringList{"default","Open"},QVariantMap{{"x-ether-privacy","sensitive"}},0});auto*w=new QDBusPendingCallWatcher(bus.asyncCall(msg),&client);QObject::connect(w,&QDBusPendingCallWatcher::finished,&client,[&,w]{auto r=w->reply();if(r.type()==QDBusMessage::ErrorMessage)errors<<r.errorMessage();else ident=r.arguments().value(0).toUInt();w->deleteLater();});};
 client.session(false,false,false);
 QTimer steps;steps.setInterval(350);QObject::connect(&steps,&QTimer::timeout,&app,[&]{
  switch(stage++){
   case 0:check(client.state().value("ready").toBool(),"initial snapshot");check(!client.state().value("locked").toBool(),"session unlock");send();break;
   case 1:check(ident!=0,"standard Notify ID");check(client.banner().value("id").toUInt()==ident,"banner queue delivery");client.command("invoke",ident,{{"key","default"}});break;
   case 2:check(client.banner().isEmpty(),"action clears banner");check(client.state().value("unread").toInt()==0,"unread after action");client.configure({{"dnd","priority"},{"manualDnd",true}});break;
   case 3:send();break;
   case 4:check(client.banner().isEmpty(),"DND suppresses banner");{auto cards=client.state().value("cards").toList();QString appId;for(auto v:cards)if(v.toMap().value("id").toUInt()==ident)appId=v.toMap().value("appId").toString();check(!appId.isEmpty(),"verified app identity");client.appPolicy(appId,{{"dndException",true}});}break;
   case 5:send();break;
   case 6:check(client.banner().value("id").toUInt()==ident,"authorized DND exception banner");client.session(true,false,false);break;
   case 7:check(client.banner().isEmpty(),"lock immediately clears banner");{bool redacted=true;for(auto v:client.state().value("cards").toList())redacted&=v.toMap().value("body").toString().isEmpty();check(redacted,"lock redacts actual client snapshot");}qInfo().noquote()<<QJsonDocument::fromVariant(QVariantMap{{"errors",errors},{"checks",9}}).toJson(QJsonDocument::Compact);app.exit(errors.isEmpty()?0:3);break;
  }
 });steps.start();QTimer::singleShot(10000,&app,[&]{app.exit(4);});return app.exec();
}
