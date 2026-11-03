#include "controller.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QFile>
#include <QSqlQuery>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QStandardPaths>
#include <QDir>
#include <QSignalSpy>
// Test-only transport; never linked into the production application.
class TestTransport final:public ISmsTransport {
public:
 bool enabled=true;int sends=0;QString lastId;
 QVariantMap capabilities()const override{return {{"canSend",enabled},{"network","Automated test backend"}};}
 void send(const QString &id,const QString &,const QString &,bool)override{++sends;lastId=id;emit stateChanged(id,"Uncertain",{},"Test interrupted operation");}
 void inject(const QVariantMap &m){emit incoming(m);}
};
class Tests:public QObject {
 Q_OBJECT
 QTemporaryDir sharedContacts;
private slots:
 void initTestCase(){qputenv("ETHERCONTACTS_DATABASE",(sharedContacts.path()+"/contacts.sqlite").toUtf8());}
 void init(){QFile::remove(sharedContacts.path()+"/contacts.sqlite");}
 void creationFailureCertainty(){QVERIFY(smsCreationRejected("org.freedesktop.ModemManager1.Error.Core.Unauthorized"));QVERIFY(smsCreationRejected("org.freedesktop.DBus.Error.AccessDenied"));QVERIFY(smsCreationRejected("org.freedesktop.DBus.Error.InvalidArgs"));QVERIFY(!smsCreationRejected("org.freedesktop.DBus.Error.NoReply"));QVERIFY(!smsCreationRejected("org.freedesktop.ModemManager1.Error.Core.Failed"));}
 void numbers(){QCOMPARE(normalizedNumber("+48 (512) 345-678"),QString("+48512345678"));QCOMPARE(normalizedNumber("12345"),QString("12345"));QVERIFY(normalizedNumber("+48; rm -rf /").isEmpty());QVERIFY(normalizedNumber("++123").isEmpty());QVERIFY(normalizedNumber("12").isEmpty());}
 void segments(){QCOMPARE(estimateSms(QString(160,'a')).segments,1);QCOMPARE(estimateSms(QString(161,'a')).segments,2);QCOMPARE(estimateSms(QString(80,'^')).segments,1);QCOMPARE(estimateSms(QString(81,'^')).segments,2);QCOMPARE(estimateSms(QString::fromUtf8("zażółć")).encoding,QString("Unicode (UTF-16)"));QCOMPARE(estimateSms(QString(70,QChar(0x105))).segments,1);QCOMPARE(estimateSms(QString(71,QChar(0x105))).segments,2);QCOMPARE(estimateSms(QString::fromUtf8("😀")).units,2);QCOMPARE(estimateSms("").segments,0);QCOMPARE(estimateSms(QString(153,'^')).segments,3);QCOMPARE(estimateSms(QString::fromUtf8("€")).units,2);QCOMPARE(estimateSms(QString::fromUtf8("😀").repeated(67)).segments,3);}
 void persistenceAndRecovery(){
  QTemporaryDir dir;QString path=dir.path()+"/data/messages.sqlite",id;
  {Repository r(path);QVERIFY2(r.ready(),qPrintable(r.error()));QVERIFY(r.saveDraft("+48123456789","private draft"));id=r.enqueue("+48123456789","unsent test");QVERIFY(!id.isEmpty());QVERIFY(r.update(id,"Sending",{},{}));}
  {Repository r(path);QVERIFY(r.ready());QCOMPARE(r.messages("+48123456789").first().toMap().value("state").toString(),QString("Uncertain"));QVERIFY(r.draft("+48123456789").isEmpty());QVERIFY(r.backup(dir.path()+"/backup.sqlite"));QVERIFY(!r.backup(dir.path()+"/backup.sqlite"));}
  Repository backup(dir.path()+"/backup.sqlite");QCOMPARE(backup.messages("+48123456789").size(),1);
 }
 void incomingAndContacts(){
  QTemporaryDir dir;Repository r(dir.path()+"/messages.sqlite");QVariantMap m{{"number","BANK"},{"text","<script>untrusted</script>"},{"timestamp","2026-10-19T11:00:00.000Z"},{"key","a"}};
  QVERIFY(r.receive(m));QVERIFY(!r.receive(m));QCOMPARE(r.unread(),1);QCOMPARE(r.messages("BANK").size(),1);QVERIFY(r.markRead("BANK"));QCOMPARE(r.unread(),0);
  auto id=r.messages("BANK").first().toMap().value("id").toString();QVERIFY(r.remove(id));QVERIFY(!r.receive(m));QCOMPARE(r.messages("BANK").size(),0);
  QVERIFY(r.contact("+48123456789","Ania ' OR 1=1 --"));QCOMPARE(r.contacts().size(),1);QVERIFY(r.contacts("' OR 1=1 --").size()==1);QVERIFY(r.removeContact("+48123456789"));QCOMPARE(r.contacts().size(),0);
 }
 void legacyContactMigrationAndSharedStore(){
  QTemporaryDir dir;auto path=dir.path()+"/messages.sqlite";
  {Repository r(path);QVERIFY(r.ready());}
  {auto db=QSqlDatabase::addDatabase("QSQLITE","legacy-contact-fixture");db.setDatabaseName(path);QVERIFY(db.open());QSqlQuery q(db);
   QVERIFY(q.exec("DROP TABLE contacts_legacy"));QVERIFY(q.exec("CREATE TABLE contacts(number TEXT PRIMARY KEY,name TEXT NOT NULL)"));
   QVERIFY(q.exec("INSERT INTO contacts VALUES('+441234567890','Legacy contact')"));db.close();}
  QSqlDatabase::removeDatabase("legacy-contact-fixture");
  Repository r(path);QVERIFY2(r.ready(),qPrintable(r.error()));QCOMPARE(r.contacts().size(),1);
  {auto db=QSqlDatabase::addDatabase("QSQLITE","shared-contact-fixture");db.setDatabaseName(qEnvironmentVariable("ETHERCONTACTS_DATABASE"));QVERIFY(db.open());QSqlQuery q(db);
   QVERIFY(q.exec("UPDATE people SET notes='Keep notes',emails='[\"a@example.test\"]'"));
   QVERIFY(q.exec("INSERT INTO numbers SELECT '+48123456789',id FROM people"));
   QCOMPARE(r.contacts().size(),2);QVERIFY(r.contact("+48123456789","Updated shared name"));
   QVERIFY(q.exec("SELECT name,notes,emails FROM people"));QVERIFY(q.next());QCOMPARE(q.value(0).toString(),QString("Updated shared name"));QCOMPARE(q.value(1).toString(),QString("Keep notes"));
   QCOMPARE(q.value(2).toString(),QString("[\"a@example.test\"]"));db.close();}
  QSqlDatabase::removeDatabase("shared-contact-fixture");
 }
 void migrationsRejectFuture(){
  QTemporaryDir dir;auto path=dir.path()+"/messages.sqlite";{Repository r(path);QVERIFY(r.ready());}
  {auto db=QSqlDatabase::addDatabase("QSQLITE","future");db.setDatabaseName(path);QVERIFY(db.open());QSqlQuery q(db);QVERIFY(q.exec("PRAGMA user_version=99"));db.close();}QSqlDatabase::removeDatabase("future");
  Repository r(path);QVERIFY(!r.ready());QVERIFY(r.error().contains("newer"));
 }
 void historyPaging(){
  QTemporaryDir dir;Repository r(dir.path()+"/messages.sqlite");
  for(int i=0;i<205;++i)QVERIFY(r.receive({{"number","12345"},{"text","fixture"},{"timestamp",QDateTime::fromString("2026-10-19T11:00:00Z",Qt::ISODate).addSecs(i).toString(Qt::ISODateWithMs)},{"key",QString::number(i)}}));
  QCOMPARE(r.messageCount("12345"),205);QCOMPARE(r.messages("12345").size(),200);QCOMPARE(r.messages("12345",{},200).size(),5);
 }
 void microphoneMonitorRejected(){
  QTemporaryDir dir;auto oldPath=qgetenv("PATH"),oldData=qgetenv("XDG_DATA_HOME");qputenv("XDG_DATA_HOME",dir.path().toUtf8());
  const auto models=QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)+"/models";QVERIFY(models.startsWith(dir.path()));QDir().mkpath(models);
  QFile model(models+"/ggml-base.bin");QVERIFY(model.open(QIODevice::WriteOnly));model.write("test fixture only");model.close();
  auto executable=[&](const QString &name,const QByteArray &script){QFile f(dir.path()+"/"+name);if(!f.open(QIODevice::WriteOnly))return false;f.write(script);f.close();return f.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);};
  QVERIFY(executable("whisper-cli","#!/bin/sh\nexit 2\n"));
  QVERIFY(executable("parec","#!/bin/sh\nexit 2\n"));
  QVERIFY(executable("pactl","#!/bin/sh\nprintf '%s' '[{\"name\":\"speaker.monitor\",\"monitor_of_sink\":1}]'\n"));
  qputenv("PATH",dir.path().toUtf8()+":"+oldPath);
  {Speech speech;QSignalSpy transcript(&speech,&Speech::transcribed);QVERIFY(speech.available());speech.start("pl","ggml-base.bin",{});QTRY_VERIFY(speech.state().contains("No microphone source"));QCOMPARE(transcript.count(),0);speech.cancel();QCOMPARE(speech.state(),QString("Ready"));}
  qputenv("PATH",oldPath);if(oldData.isNull())qunsetenv("XDG_DATA_HOME");else qputenv("XDG_DATA_HOME",oldData);
 }
 void managedCaptureAfterUserAction(){
  QTemporaryDir dir;auto oldPath=qgetenv("PATH"),oldData=qgetenv("XDG_DATA_HOME");qputenv("XDG_DATA_HOME",dir.path().toUtf8());
  const auto models=QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)+"/models";QDir().mkpath(models);
  QFile model(models+"/ggml-base.bin");QVERIFY(model.open(QIODevice::WriteOnly));model.write("fixture only");model.close();
  auto executable=[&](const QString &name,const QByteArray &script){QFile f(dir.path()+"/"+name);if(!f.open(QIODevice::WriteOnly))return false;f.write(script);f.close();return f.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner);};
  QVERIFY(executable("whisper-cli","#!/bin/sh\nexit 2\n"));QVERIFY(executable("parec","#!/bin/sh\nexit 2\n"));
  QVERIFY(executable("pactl","#!/bin/sh\nprintf '%s' '[{\"name\":\"fixture_mic\",\"monitor_of_sink\":4294967295}]'\n"));
  QVERIFY(executable("etheraudio","#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$ETHERAUDIO_TEST_CAPTURE_ARGS\"\nexit 2\n"));
  qputenv("PATH",dir.path().toUtf8()+":"+oldPath);qputenv("ETHERAUDIO_TEST_CAPTURE_ARGS",(dir.path()+"/capture-args").toUtf8());
  {Speech speech;QVERIFY(speech.available());speech.start("pl","ggml-base.bin","fixture_mic");
   QTRY_VERIFY(QFile::exists(dir.path()+"/capture-args"));QFile args(dir.path()+"/capture-args");QVERIFY(args.open(QIODevice::ReadOnly));const auto data=args.readAll();QVERIFY(data.contains("capture\n"));QVERIFY(data.contains("--consent\n"));QVERIFY(data.contains("--source\nfixture_mic\n"));speech.cancel();}
  qunsetenv("ETHERAUDIO_TEST_CAPTURE_ARGS");qputenv("PATH",oldPath);if(oldData.isNull())qunsetenv("XDG_DATA_HOME");else qputenv("XDG_DATA_HOME",oldData);
 }
 void qmlResponsiveAndExplicitSend(){
  QTemporaryDir dir;TestTransport t;SmsSettings settings;settings.set("notifications",false);Speech speech;Controller c(&t,&settings,&speech,dir.path()+"/messages.sqlite");
  QQmlApplicationEngine engine;QStringList warnings;
  connect(&engine,&QQmlEngine::warnings,this,[&](const QList<QQmlError> &errors){for(const auto &e:errors)warnings<<e.toString();});
  engine.rootContext()->setContextProperty("Sms",&c);engine.rootContext()->setContextProperty("SmsTransport",&t);engine.rootContext()->setContextProperty("SmsSettings",&settings);engine.rootContext()->setContextProperty("Speech",&speech);engine.rootContext()->setContextProperty("PocketDisplay",true);
  engine.load(QUrl("qrc:/Main.qml"));QVERIFY(!engine.rootObjects().isEmpty());auto *w=qobject_cast<QQuickWindow*>(engine.rootObjects().first());QVERIFY(w);
  t.inject({{"number","+48123456789"},{"text","Automated incoming fixture <script>plain text</script>; not a real SMS."},{"timestamp","2026-10-19T11:00:00.000Z"},{"key","isolated-ui-fixture"}});
  c.open("+48123456789");QCOMPARE(c.number(),QString("+48123456789"));w->setProperty("conversationOpen",true);c.setDraft("Automated UI test draft");
  QTest::qWait(100);auto *send=w->findChild<QQuickItem*>("sendButton");QVERIFY(send);QVERIFY2(send->isEnabled(),qPrintable(QString("draft=%1 number=%2 canSend=%3 cap=%4").arg(c.draft(),c.number()).arg(w->property("canSend").toBool()).arg(t.property("capabilities").toMap().value("canSend").toBool())));QCOMPARE(t.sends,0);
  t.enabled=false;emit t.capabilitiesChanged();QTest::qWait(30);QVERIFY(!send->isEnabled());
  for(const QSize size:{QSize(460,850),QSize(850,460)}){w->resize(size);QTest::qWait(50);QVERIFY(!w->property("desktop").toBool());}
  engine.rootContext()->setContextProperty("PocketDisplay",false);w->resize(1920,1080);QTest::qWait(50);QVERIFY(w->property("desktop").toBool());QCOMPARE(t.sends,0);
  QVERIFY2(warnings.isEmpty(),qPrintable(warnings.join("\n")));w->close();
 }
 void confirmedDeliveryDoesNotRegress(){
  QTemporaryDir dir;Repository r(dir.path()+"/messages.sqlite");auto id=r.enqueue("+48123456789","test");QVERIFY(r.update(id,"Delivered","key",{}));QVERIFY(r.update(id,"Submitted to network","key",{}));QCOMPARE(r.messages("+48123456789").first().toMap().value("state").toString(),QString("Delivered"));
 }
 void explicitSendAndDrafts(){
  QTemporaryDir dir;TestTransport t;SmsSettings settings;settings.set("notifications",false);Speech speech;Controller c(&t,&settings,&speech,dir.path()+"/messages.sqlite");
  c.open("invalid");c.setDraft("hello");QVERIFY(!c.send());QCOMPARE(t.sends,0);
  c.open("+48123456789");c.setDraft("draft");t.enabled=false;QVERIFY(!c.send());QCOMPARE(c.draft(),QString("draft"));t.enabled=true;
  c.open("+441234567890");c.setDraft("other");c.open("+48123456789");QCOMPARE(c.draft(),QString("draft"));
  // Recognition inserts text and never sends it.
  emit speech.transcribed("dyktowanie");QCOMPARE(t.sends,0);QVERIFY(c.draft().contains("dyktowanie"));
  QVERIFY(c.send());QCOMPARE(t.sends,1);QVERIFY(c.draft().isEmpty());QCOMPARE(c.messages().last().toMap().value("state").toString(),QString("Uncertain"));QTest::qWait(20);QCOMPARE(t.sends,1);
 }
};
QTEST_MAIN(Tests)
#include "tests.moc"
