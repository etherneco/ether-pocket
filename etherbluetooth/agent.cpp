#include "agent.h"
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusReply>
#include <QRegularExpression>
Agent::Agent(QObject *parent):QObject(parent) {
    timeout.setSingleShot(true);
    connect(&timeout,&QTimer::timeout,this,[this]{answer(false,{});});
}
bool Agent::allowed() {
    auto owner=QDBusConnection::systemBus().interface()->serviceOwner("org.bluez");
    if(!calledFromDBus() || !owner.isValid() || message().service()!=owner.value()) {
        if(calledFromDBus()) sendErrorReply("org.bluez.Error.Rejected","Only BlueZ may invoke the agent");
        return false;
    }
    return true;
}
void Agent::request(const QDBusObjectPath &device,const QString &kind,const QString &value) {
    if(!allowed())return;
    if(!pending.service().isEmpty())answer(false,{});
    setDelayedReply(true);pending=message();
    prompt={{"device",device.path()},{"kind",kind},{"value",value}};
    timeout.start(60000);emit changed();
}
void Agent::answer(bool accept,const QString &value) {
    if(!pending.service().isEmpty()) {
        QVariantList result;
        const QString kind=prompt.value("kind").toString();
        if(kind=="pin") {accept=accept && !value.isEmpty() && value.size()<=16;result<<value;}
        if(kind=="passkey") {accept=accept && QRegularExpression("^[0-9]{1,6}$").match(value).hasMatch();result<<QVariant::fromValue(value.toUInt());}
        QDBusConnection::systemBus().send(accept?pending.createReply(result):pending.createErrorReply("org.bluez.Error.Rejected","User declined, invalid input or timeout"));
    }
    timeout.stop();pending=QDBusMessage();prompt.clear();emit changed();
}
QString Agent::RequestPinCode(const QDBusObjectPath &d){request(d,"pin");return {};}
uint Agent::RequestPasskey(const QDBusObjectPath &d){request(d,"passkey");return 0;}
void Agent::RequestConfirmation(const QDBusObjectPath &d,uint key){request(d,"confirm",QString("%1").arg(key,6,10,QChar('0')));}
void Agent::RequestAuthorization(const QDBusObjectPath &d){request(d,"authorize");}
void Agent::AuthorizeService(const QDBusObjectPath &d,const QString &uuid){request(d,"service",uuid);}
void Agent::DisplayPinCode(const QDBusObjectPath &d,const QString &pin){if(!allowed())return;prompt={{"device",d.path()},{"kind","display"},{"value",pin}};timeout.start(60000);emit changed();}
void Agent::DisplayPasskey(const QDBusObjectPath &d,uint key,ushort entered){DisplayPinCode(d,QString("%1  (%2 entered)").arg(key,6,10,QChar('0')).arg(entered));}
void Agent::Cancel(){if(!allowed())return;answer(false,{});}
void Agent::Release(){if(!allowed())return;answer(false,{});}
