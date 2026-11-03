#include "bluetooth.h"
#include <QDBusVirtualObject>
#include <QDBusMetaType>
#include <QDBusPendingReply>
#include <QSignalSpy>
#include <QtTest>
class FakeBlueZ:public QDBusVirtualObject {
public:
    Objects objects;
    QStringList calls;
    QString introspect(const QString &)const override{return {};}
    bool handleMessage(const QDBusMessage &message,const QDBusConnection &bus)override{
        calls<<message.member();
        if(message.member()=="GetManagedObjects")bus.send(message.createReply({QVariant::fromValue(objects)}));
        else bus.send(message.createReply());
        return true;
    }
    void property(const QString &path,const QString &interface,const QVariantMap &values){
        for(auto i=values.cbegin();i!=values.cend();++i)objects[QDBusObjectPath(path)][interface][i.key()]=i.value();
        auto message=QDBusMessage::createSignal(path,"org.freedesktop.DBus.Properties","PropertiesChanged");
        message<<interface<<values<<QStringList{};QDBusConnection("fake-bluez").send(message);
    }
};
class Integration:public QObject {
    Q_OBJECT
private slots:
    void realDBusMessages(){
        qDBusRegisterMetaType<Interfaces>();qDBusRegisterMetaType<Objects>();
        auto bus=QDBusConnection::connectToBus(QDBusConnection::SystemBus,"fake-bluez");
        QVERIFY2(qEnvironmentVariableIsSet("ETHERBLUETOOTH_TEST_BUS"),"Use the isolated test runner; never own org.bluez on the real system bus");
        QVERIFY(bus.registerService("org.bluez"));FakeBlueZ fake;
        fake.objects[QDBusObjectPath("/org/bluez/hci0")]["org.bluez.Adapter1"]={{"Alias","Test adapter"},{"Powered",true},{"Discovering",false}};
        fake.objects[QDBusObjectPath("/org/bluez/hci0/dev_TEST")]["org.bluez.Device1"]={{"Alias","Paired keyboard"},{"Address","00:00:00:00:00:01"},{"Adapter",QVariant::fromValue(QDBusObjectPath("/org/bluez/hci0"))},{"Paired",true},{"Connected",false},{"Trusted",false},{"Icon","input-keyboard"}};
        QVERIFY(bus.registerVirtualObject("/",&fake,QDBusConnection::SingleNode));
        QVERIFY(bus.registerVirtualObject("/org/bluez",&fake,QDBusConnection::SubPath));
        {
            Bluetooth bluetooth;
            QTRY_COMPARE(bluetooth.adapters().size(),1);
            QCOMPARE(bluetooth.devices().size(),1);
            QCOMPARE(bluetooth.devices()[0].toMap()["state"].toString(),QString("Paired · disconnected"));
            bluetooth.scan(true);QTRY_VERIFY(fake.calls.contains("StartDiscovery"));
            bluetooth.scan(false);QTRY_VERIFY(fake.calls.contains("StopDiscovery"));
            fake.property("/org/bluez/hci0/dev_TEST","org.bluez.Device1",{{"Connected",true}});
            QTRY_COMPARE(bluetooth.devices()[0].toMap()["state"].toString(),QString("Connected"));
            fake.property("/org/bluez/hci0/dev_TEST","org.bluez.Device1",{{"Connected",false}});
            QTRY_COMPARE(bluetooth.devices()[0].toMap()["state"].toString(),QString("Paired · disconnected"));
            QVERIFY(!fake.calls.contains("Connect")); // untrusted devices never reconnect
            bluetooth.action("/not/a/device","connect");QVERIFY(!fake.calls.contains("Connect"));
            auto request=QDBusMessage::createMethodCall(QDBusConnection::systemBus().baseService(),"/org/etherneco/EtherBluetooth/agent","org.bluez.Agent1","RequestConfirmation");
            request<<QVariant::fromValue(QDBusObjectPath("/org/bluez/hci0/dev_TEST"))<<uint(123);
            QDBusPendingCall pending=bus.asyncCall(request);
            QTRY_COMPARE(bluetooth.pairing().value("value").toString(),QString("000123"));
            QVERIFY(!pending.isFinished());bluetooth.answer(false);
            QTRY_VERIFY(pending.isFinished());QDBusPendingReply<> reply=pending;
            QVERIFY(reply.isError());QCOMPARE(reply.error().name(),QString("org.bluez.Error.Rejected"));
            request=QDBusMessage::createMethodCall(QDBusConnection::systemBus().baseService(),"/org/etherneco/EtherBluetooth/agent","org.bluez.Agent1","RequestPinCode");
            request<<QVariant::fromValue(QDBusObjectPath("/org/bluez/hci0/dev_TEST"));pending=bus.asyncCall(request);
            QTRY_COMPARE(bluetooth.pairing().value("kind").toString(),QString("pin"));
            bluetooth.answer(true,"1234");QTRY_VERIFY(pending.isFinished());
            QDBusPendingReply<QString> pinReply=pending;QVERIFY(!pinReply.isError());QCOMPARE(pinReply.value(),QString("1234"));
        }
        bus.unregisterObject("/",QDBusConnection::UnregisterTree);bus.unregisterService("org.bluez");
    }
};
QTEST_GUILESS_MAIN(Integration)
#include "integration-test.moc"
