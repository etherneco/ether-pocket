#include "audio.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
class AudioPolicyTest:public QObject {
 Q_OBJECT
private slots:
 void changesUseCentralPolicy(){
  QTemporaryDir dir;const auto oldPath=qgetenv("PATH");
  auto script=[&](const QString &name,const QByteArray &data){QFile f(dir.path()+"/"+name);if(!f.open(QIODevice::WriteOnly))return false;f.write(data);f.close();return f.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);};
  QVERIFY(script("etheraudio","#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ETHERAUDIO_TEST_ARGS\"\nexit 0\n"));
  QVERIFY(script("pactl","#!/bin/sh\nprintf '[]'\n"));
  qputenv("PATH",dir.path().toUtf8()+":"+oldPath);qputenv("ETHERAUDIO_TEST_ARGS",(dir.path()+"/request").toUtf8());
  Audio audio;
  auto seed=[&]{audio.setProperty("outputs",QVariantList{QVariantMap{{"name","fixture_sink"}}});audio.setProperty("inputs",QVariantList{QVariantMap{{"name","fixture_mic"}}});audio.setProperty("cards",QVariantList{QVariantMap{{"name","fixture_card"},{"profiles",QVariantMap{{"a2dp-sink",QVariantMap{{"available","yes"}}}}}}});};
  auto request=dir.path()+"/request";
  for(int kind=0;kind<5;++kind){
   QFile::remove(request);seed();
   if(kind==0)audio.select("output","fixture_sink");
   if(kind==1)audio.select("input","fixture_mic");
   if(kind==2)audio.volume("fixture_sink",25);
   if(kind==3)audio.mute("fixture_sink",true);
   if(kind==4)audio.profile("fixture_card","a2dp-sink");
   QTRY_VERIFY(QFile::exists(request));QTest::qWait(50);QFile file(request);QVERIFY(file.open(QIODevice::ReadOnly));auto lines=file.readAll().trimmed().split('\n');
   QCOMPARE(lines.value(0),QByteArray("command"));QCOMPARE(lines.value(1),QByteArray(kind<2?"select":kind==2?"volume":kind==3?"mute":"card-profile"));
   if(kind<2)QCOMPARE(lines.value(2),QByteArray(kind==0?"sink":"source"));
   auto data=QJsonDocument::fromJson(lines.value(3)).object();QVERIFY(!data.isEmpty());
  }
  qunsetenv("ETHERAUDIO_TEST_ARGS");qputenv("PATH",oldPath);
 }
};
QTEST_GUILESS_MAIN(AudioPolicyTest)
#include "audio-policy-test.moc"
