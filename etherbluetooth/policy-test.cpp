#include "policy.h"
#include <QtTest>
class Tests:public QObject{
    Q_OBJECT
private slots:
    void boundedRetries(){QCOMPARE(Policy::retryDelay(0,true,true,true,false),2000);QCOMPARE(Policy::retryDelay(3,true,true,true,false),16000);QCOMPARE(Policy::retryDelay(4,true,true,true,false),-1);}
    void respectUser(){QCOMPARE(Policy::retryDelay(0,true,true,true,true),-1);QCOMPARE(Policy::retryDelay(0,false,true,true,false),-1);QCOMPARE(Policy::retryDelay(0,true,false,true,false),-1);QCOMPARE(Policy::retryDelay(0,true,true,false,false),-1);}
    void categoriesUseEvidence(){QCOMPARE(Policy::category("",{}),QString("Bluetooth device"));QCOMPARE(Policy::category("input-keyboard",{}),QString("Keyboard"));}
    void errors(){QVERIFY(Policy::explain("org.bluez.Error.AuthenticationRejected").contains("rejected"));QVERIFY(Policy::explain("org.bluez.Error.NotReady").contains("Doctor"));}
};
QTEST_GUILESS_MAIN(Tests)
#include "policy-test.moc"
