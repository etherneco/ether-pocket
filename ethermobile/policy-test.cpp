#include "policy.h"
#include <QtTest>
class PolicyTest:public QObject {
    Q_OBJECT
private slots:
    void counterResetsAndBilling(){
        QVERIFY(Policy::countUsageDelta(true,true,100000,130000,100,200,90,180));
        QVERIFY(!Policy::countUsageDelta(false,true,100000,130000,100,200,90,180));
        QVERIFY(!Policy::countUsageDelta(true,false,100000,130000,100,200,90,180));
        QVERIFY(!Policy::countUsageDelta(true,true,100000,170000,100,200,90,180));
        QVERIFY(!Policy::countUsageDelta(true,true,100000,90000,100,200,90,180));
        QVERIFY(!Policy::countUsageDelta(true,true,100000,130000,80,200,90,180));
        QVERIFY(!Policy::countUsageDelta(true,true,100000,130000,100,170,90,180));
        QCOMPARE(Policy::billingStart(QDate(2026,3,1),31),QDate(2026,2,28));
        QCOMPARE(Policy::billingStart(QDate(2024,2,29),31),QDate(2024,2,29));
        QCOMPARE(Policy::billingStart(QDate(2026,1,2),15),QDate(2025,12,15));
    }
    void connectionEvidence(){
        QCOMPARE(Policy::state(8,false,true,true,false),QString("Registered"));
        QCOMPARE(Policy::state(11,false,true,true,false),QString("Data session · IP not verified"));
        QCOMPARE(Policy::state(11,true,false,true,false),QString("Data session · IP not verified"));
        QCOMPARE(Policy::state(11,true,true,false,false),QString("Data session · IP not verified"));
        QCOMPARE(Policy::state(11,true,true,true,false),QString("Connected"));
        QCOMPARE(Policy::state(11,true,true,true,true),QString("Connected · roaming"));
        QCOMPARE(Policy::state(2,false,false,false,false),QString("Locked"));
        QCOMPARE(Policy::state(7,false,false,false,false),QString("Searching"));
        QCOMPARE(Policy::state(9,false,false,false,false),QString("Disconnecting"));
    }
    void technologyClaims(){
        QCOMPARE(Policy::technology(0),QString("Unavailable"));
        QCOMPARE(Policy::technology(1u<<14),QString("LTE"));
        QVERIFY(!Policy::technology(1u<<14).contains("5G"));
        QVERIFY(!Policy::technology(1u<<14).contains("Advanced"));
        QCOMPARE(Policy::technology((1u<<14)|(1u<<15)),QString("5G NR + LTE"));
    }
    void apnInput(){
        QVERIFY(Policy::validApn("internet"));QVERIFY(Policy::validApn("carrier-1.example"));
        for(const auto &s:QStringList{"","a..b","-carrier","carrier-","a b","a\nb","$(touch file)",QString(101,'x')})QVERIFY(!Policy::validApn(s));
    }
};
QTEST_GUILESS_MAIN(PolicyTest)
#include "policy-test.moc"
