#include "mobile.h"
#include <QtTest>
#include <QUuid>
#include <QDBusConnection>
#include <QDBusMessage>
// Opt-in acceptance against a REAL NetworkManager. Never activate any profile.
// Uses a reserved .invalid APN purely as stored test data, not carrier settings.
class ProfileTest:public QObject {
    Q_OBJECT
    QString created;
private slots:
    void realProfileLifecycle(){
        Mobile mobile;
        const QString name="acceptance-"+QUuid::createUuid().toString(QUuid::WithoutBraces);
        mobile.saveProfile("",name,"acceptance.invalid",false,false,"IPv4");
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        if(qEnvironmentVariableIsSet("ETHERMOBILE_EXPECT_AUTH_FAILURE")) {
            QVERIFY2(mobile.operation().value("state").toString()=="Permission denied",qPrintable(mobile.message()));
            return;
        }
        QVERIFY2(mobile.operation().value("state").toString()=="Saved",qPrintable(mobile.message()));
        auto find=[&]()->QVariantMap{for(const auto &v:mobile.profiles())if(v.toMap().value("name").toString()=="EtherMobile · "+name)return v.toMap();return {};};
        QTRY_VERIFY_WITH_TIMEOUT(!find().isEmpty(),20000);
        auto p=find();created=p.value("path").toString();
        QVERIFY(!p.value("roaming").toBool());QVERIFY(!p.value("internetRoute").toBool());
        const QString NM="org.freedesktop.NetworkManager";
        auto query=QDBusMessage::createMethodCall(NM,created,NM+".Settings.Connection","GetSettings");
        auto reply=QDBusConnection::systemBus().call(query);
        QVERIFY(reply.type()!=QDBusMessage::ErrorMessage);
        auto settings=qdbus_cast<Settings>(reply.arguments().value(0));
        QVERIFY(!settings.value("connection").value("autoconnect").toBool());
        QCOMPARE(settings.value("ipv4").value("route-metric").toLongLong(),qint64(900));
        QCOMPARE(settings.value("gsm").value("home-only").toBool(),true);
        mobile.saveProfile(created,name,"edited.invalid",false,false,"IPv4 + IPv6");
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        QVERIFY2(mobile.operation().value("state").toString()=="Saved",qPrintable(mobile.message()));
        QTRY_COMPARE_WITH_TIMEOUT(find().value("apn").toString(),QString("edited.invalid"),20000);
        // If the NM editor adds credentials, subsequent APN edits must preserve
        // them. This secret is test-only and never printed or used on a carrier.
        reply=QDBusConnection::systemBus().call(query);
        settings=qdbus_cast<Settings>(reply.arguments().value(0));
        const QString secret=QUuid::createUuid().toString(QUuid::WithoutBraces);
        settings["gsm"]["username"]="fixture";
        settings["gsm"]["password"]=secret;
        settings["gsm"]["password-flags"]=quint32(0);
        settings["gsm"]["apn"]="authenticated.invalid";
        auto update=QDBusMessage::createMethodCall(NM,created,NM+".Settings.Connection","Update");
        update.setArguments({QVariant::fromValue(settings)});
        QVERIFY(QDBusConnection::systemBus().call(update).type()!=QDBusMessage::ErrorMessage);
        mobile.refresh();
        QTRY_COMPARE_WITH_TIMEOUT(find().value("apn").toString(),QString("authenticated.invalid"),20000);
        mobile.saveProfile(created,name,"preserved.invalid",false,false,"IPv4");
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        QVERIFY2(mobile.operation().value("state").toString()=="Saved",qPrintable(mobile.message()));
        QTRY_COMPARE_WITH_TIMEOUT(find().value("apn").toString(),QString("preserved.invalid"),20000);
        auto getSecrets=QDBusMessage::createMethodCall(NM,created,NM+".Settings.Connection","GetSecrets");
        getSecrets.setArguments({QString("gsm")});
        const auto saved=QDBusConnection::systemBus().call(getSecrets);
        QVERIFY(saved.type()!=QDBusMessage::ErrorMessage);
        QVERIFY(qdbus_cast<Settings>(saved.arguments().value(0)).value("gsm").value("password").toString()==secret);
        // The independent secret read can change NM's VersionId. Obtain the
        // current revision before exercising the legacy deletion wrapper.
        mobile.editConfiguration(created);QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        mobile.refresh();QTRY_COMPARE_WITH_TIMEOUT(find().value("version").toString(),mobile.editor().value("version").toString(),20000);
        mobile.deleteProfile(created);
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        QVERIFY2(mobile.operation().value("state").toString()=="Saved",qPrintable(mobile.message()));
        QTRY_VERIFY_WITH_TIMEOUT(find().isEmpty(),20000);
        created.clear();
    }
    void cleanup(){
        // On a failed assertion remove only the exact profile created by this run.
        if(created.isEmpty())return;
        const QString NM="org.freedesktop.NetworkManager";
        QDBusConnection::systemBus().call(QDBusMessage::createMethodCall(NM,created,NM+".Settings.Connection","Delete"));
        created.clear();
    }
};
QTEST_GUILESS_MAIN(ProfileTest)
#include "profile-test.moc"
