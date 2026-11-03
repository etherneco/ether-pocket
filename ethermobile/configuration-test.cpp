#include "mobile.h"
#include <QtTest>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QUuid>

// Real NetworkManager acceptance. Test-only APNs use reserved .invalid names;
// profiles never autoconnect, install default routes or activate a data session.
class ConfigurationTest:public QObject{
    Q_OBJECT
    QString fixture=qEnvironmentVariable("ETHERMOBILE_FIXTURE_ID","EtherMobile configuration-"+QUuid::createUuid().toString(QUuid::WithoutBraces));
    const QString NM="org.freedesktop.NetworkManager", CI=NM+".Settings.Connection";
    QDBusMessage invoke(const QString &path,const QString &method,QVariantList args={}){
        auto message=QDBusMessage::createMethodCall(NM,path,CI,method);message.setArguments(args);return QDBusConnection::systemBus().call(message);
    }
    QVariantMap fields(Mobile &mobile){auto f=mobile.editor();f["password"]="";f["changePassword"]=false;return f;}
private slots:
    void roundTripAndConcurrency(){
        Mobile mobile;
        mobile.editConfiguration("");QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        auto f=fields(mobile);const auto secret=QUuid::createUuid().toString(QUuid::WithoutBraces);
        f["name"]=fixture;f["apn"]="configuration.invalid";f["username"]="fixture";f["password"]=secret;f["changePassword"]=true;
        f["auth"]="PAP";f["ipType"]="IPv4 + IPv6";f["priority"]=7;f["metric"]=1900;
        f["manualDns"]=true;f["dns4"]="192.0.2.53";f["dns6"]="2001:db8::53";
        mobile.saveConfiguration(f);f["password"]="";
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        if(qEnvironmentVariableIsSet("ETHERMOBILE_EXPECT_AUTH_FAILURE")){
            QVERIFY2(mobile.operation().value("state")=="Permission denied",qPrintable(mobile.message()));return;
        }
        QVERIFY2(mobile.operation().value("state")=="Saved",qPrintable(mobile.message()));
        const auto path=mobile.editor().value("path").toString();QVERIFY(path.startsWith("/org/freedesktop/NetworkManager/Settings/"));
        QCOMPARE(mobile.editor().value("dns4").toString(),QString("192.0.2.53"));
        QCOMPARE(mobile.editor().value("dns6").toString(),QString("2001:db8::53"));
        QCOMPARE(mobile.editor().value("auth").toString(),QString("PAP"));
        QVERIFY(!mobile.editor().value("roaming").toBool());QVERIFY(!mobile.editor().value("autoconnect").toBool());
        QVERIFY(!mobile.editor().value("internetRoute").toBool());
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.profiles().isEmpty(),20000);
        // Editing through the same backend preserves the secret and IP policy.
        f=fields(mobile);f["apn"]="edited.invalid";mobile.saveConfiguration(f);
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);QVERIFY2(mobile.operation().value("state")=="Saved",qPrintable(mobile.message()));
        // Restore only when the exact post-write version still matches.
        mobile.rollbackConfiguration();QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        QVERIFY2(mobile.operation().value("state")=="Saved",qPrintable(mobile.message()));
        QCOMPARE(mobile.editor().value("apn").toString(),QString("configuration.invalid"));
        auto secrets=invoke(path,"GetSecrets",{QString("gsm")});QVERIFY(secrets.type()!=QDBusMessage::ErrorMessage);
        QVERIFY(qdbus_cast<Settings>(secrets.arguments().value(0)).value("gsm").value("password").toString()==secret);
        // External NM editor changes the version. Stale drafts must not win.
        f=fields(mobile);
        auto reply=invoke(path,"GetSettings");auto settings=qdbus_cast<Settings>(reply.arguments().value(0));
        settings["gsm"]["apn"]="external.invalid";settings["gsm"]["password"]=secret;
        QVERIFY(invoke(path,"Update",{QVariant::fromValue(settings)}).type()!=QDBusMessage::ErrorMessage);
        f["apn"]="must-not-overwrite.invalid";mobile.saveConfiguration(f);
        QTRY_VERIFY_WITH_TIMEOUT(!mobile.busy(),20000);
        QVERIFY2(mobile.operation().value("state")=="Verification failed",qPrintable(mobile.message()));
        reply=invoke(path,"GetSettings");QCOMPARE(qdbus_cast<Settings>(reply.arguments().value(0)).value("gsm").value("apn").toString(),QString("external.invalid"));
        // A fresh backend instance reads the persistent profile after restart.
        Mobile restarted;
        auto find=[&](Mobile &m){for(const auto &v:m.profiles())if(v.toMap().value("name").toString()==fixture)return v.toMap();return QVariantMap{};};
        QTRY_VERIFY_WITH_TIMEOUT(!find(restarted).isEmpty(),20000);
        QCOMPARE(find(restarted).value("apn").toString(),QString("external.invalid"));
        restarted.editConfiguration(path,true);QTRY_VERIFY_WITH_TIMEOUT(!restarted.busy(),20000);
        f=fields(restarted);f["name"]=fixture+" copy";restarted.saveConfiguration(f);
        QTRY_VERIFY_WITH_TIMEOUT(!restarted.busy(),20000);QVERIFY2(restarted.operation().value("state")=="Saved",qPrintable(restarted.message()));
        const auto copyPath=restarted.editor().value("path").toString();QVERIFY(copyPath!=path);
        secrets=invoke(copyPath,"GetSecrets",{QString("gsm")});QVERIFY(secrets.type()!=QDBusMessage::ErrorMessage);
        QVERIFY(qdbus_cast<Settings>(secrets.arguments().value(0)).value("gsm").value("password").toString()==secret);
        auto hasCopy=[&]{for(const auto &v:restarted.profiles())if(v.toMap().value("path").toString()==copyPath)return true;return false;};
        QTRY_VERIFY_WITH_TIMEOUT(hasCopy(),20000);
        // The independent GetSecrets above can bump NM's revision. Reopen before
        // deletion instead of bypassing the optimistic revision guard.
        restarted.editConfiguration(copyPath);QTRY_VERIFY_WITH_TIMEOUT(!restarted.busy(),20000);
        restarted.clearConfigurationSecrets(copyPath,restarted.editor().value("version").toString());
        QTRY_VERIFY_WITH_TIMEOUT(!restarted.busy(),20000);QVERIFY2(restarted.operation().value("state")=="Saved",qPrintable(restarted.message()));
        f=fields(restarted);f["username"]="";f["ipType"]="IPv6";
        restarted.saveConfiguration(f);QTRY_VERIFY_WITH_TIMEOUT(!restarted.busy(),20000);
        QVERIFY2(restarted.operation().value("state")=="Saved",qPrintable(restarted.message()));
        QCOMPARE(restarted.editor().value("ipType").toString(),QString("IPv6"));
        secrets=invoke(copyPath,"GetSecrets",{QString("gsm")});
        QVERIFY(secrets.type()!=QDBusMessage::ErrorMessage||secrets.errorName().endsWith(".NoSecrets"));
        if(secrets.type()!=QDBusMessage::ErrorMessage)QVERIFY(qdbus_cast<Settings>(secrets.arguments().value(0)).value("gsm").value("password").toString().isEmpty());
        restarted.editConfiguration(copyPath);QTRY_VERIFY_WITH_TIMEOUT(!restarted.busy(),20000);
        restarted.deleteConfiguration(copyPath,restarted.editor().value("version").toString());
        QTRY_VERIFY_WITH_TIMEOUT(!restarted.busy(),20000);QVERIFY2(restarted.operation().value("state")=="Saved",qPrintable(restarted.message()));
        QVERIFY(invoke(copyPath,"GetSettings").type()==QDBusMessage::ErrorMessage);
        restarted.applyMode("16/16");QCOMPARE(restarted.operation().value("state").toString(),QString("Unsupported"));
    }
    void cleanup(){
        // Remove only this invocation's exact random fixture names, even if a
        // verification assertion failed after NetworkManager accepted a write.
        auto message=QDBusMessage::createMethodCall(NM,"/org/freedesktop/NetworkManager/Settings",NM+".Settings","ListConnections");
        auto list=QDBusConnection::systemBus().call(message);
        for(const auto &path:qdbus_cast<QList<QDBusObjectPath>>(list.arguments().value(0))){
            auto reply=invoke(path.path(),"GetSettings");if(reply.type()==QDBusMessage::ErrorMessage)continue;
            auto name=qdbus_cast<Settings>(reply.arguments().value(0)).value("connection").value("id").toString();
            if(name==fixture||name==fixture+" copy")invoke(path.path(),"Delete");
        }
    }
};
QTEST_GUILESS_MAIN(ConfigurationTest)
#include "configuration-test.moc"
