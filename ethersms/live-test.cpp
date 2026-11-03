#include "controller.h"
#include "mobile.h"
#include <QCoreApplication>
#include <QSaveFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDateTime>
#include <QTimer>
#include <QFile>
#include <sys/stat.h>
// Opt-in physical-device acceptance harness. Never part of the installed app.
// The recipient comes from the operator environment, not a repository fixture.
int main(int argc,char **argv){
 umask(0077);QCoreApplication app(argc,argv);app.setOrganizationName("Etherneco");app.setApplicationName("EtherSMS");
 const auto args=app.arguments();if(args.size()!=3||args[1]!="--confirm-authorized-send")return 2;
 const auto journal=args[2],recipient=qEnvironmentVariable("ETHERSMS_TEST_RECIPIENT");
 if(normalizedNumber(recipient).isEmpty()||QFile::exists(journal))return 3;
 QFile guard(journal);if(!guard.open(QIODevice::WriteOnly|QIODevice::NewOnly))return 4;guard.write("{\"state\":\"Preparing\",\"attempted\":false}\n");guard.close();
 bool attempted=false;QString state="Awaiting backend";QJsonObject receipt;
 auto save=[&]{receipt["state"]=state;receipt["attempted"]=attempted;receipt["recipientSuffix"]=recipient.right(4);receipt["timeUtc"]=QDateTime::currentDateTimeUtc().toString(Qt::ISODate);QSaveFile f(journal);if(f.open(QIODevice::WriteOnly)){f.write(QJsonDocument(receipt).toJson());f.commit();}};
 Mobile mobile;MobileSmsTransport transport(&mobile,nullptr,false);SmsSettings settings;settings.set("deliveryReports",true);settings.set("notifications",false);Speech speech;
 Controller core(&transport,&settings,&speech,qEnvironmentVariable("ETHERSMS_TEST_DATABASE"));
 QObject::connect(&transport,&ISmsTransport::capabilitiesChanged,&app,[&]{
  if(attempted||!transport.capabilities().value("canSend").toBool())return;
  attempted=true;state="Invoking explicit send";save();core.open(recipient);
  if(core.number()!=recipient){state="Draft selection failed";save();app.exit(5);return;}
  if(!core.draft().isEmpty()){state="Existing draft preserved; no send";save();app.exit(6);return;}
  const auto text=qEnvironmentVariable("ETHERSMS_TEST_TEXT",QString::fromUtf8("EtherSMS test — native Linux messaging validation"));
  const auto estimate=estimateSms(text);receipt["encoding"]=estimate.encoding;receipt["segments"]=estimate.segments;save();core.setDraft(text);
  if(!core.send()){state="Send preflight failed";receipt["error"]=core.error();save();app.exit(7);}
 });
 QObject::connect(&transport,&ISmsTransport::stateChanged,&app,[&](const QString &id,const QString &s,const QString &key,const QString &error){
  state=s;receipt["messageId"]=id;receipt["transportKey"]=key;receipt["error"]=error;save();
  if(s=="Submitted to network")QTimer::singleShot(2000,&app,[&]{app.exit(0);});
  if(s=="Delivered")QTimer::singleShot(500,&app,[&]{app.exit(0);});
  else if(s=="Failed"||s=="Uncertain")QTimer::singleShot(500,&app,[&]{app.exit(8);});
 });
 QTimer::singleShot(45000,&app,[&]{save();app.exit(state=="Submitted to network"?0:9);});
 return app.exec();
}
