// Built only with ETHERCAMERA_UI_TEST=ON. Drives production QML using mouse clicks.
#include "../capture_controller.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QTest>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDir>
#include <QFile>
#include <QElapsedTimer>
#include <functional>

bool until(std::function<bool()> predicate,int timeout=8000){QElapsedTimer t;t.start();while(!predicate()&&t.elapsed()<timeout)QTest::qWait(40);return predicate();}
int main(int argc,char **argv){
 qputenv("QT_QUICK_BACKEND","software");qputenv("QT_QUICK_CONTROLS_STYLE","Basic");QGuiApplication app(argc,argv);
 auto *images=new CaptureImage;CaptureController camera(images);QQmlApplicationEngine engine;
 QString previous;
 QObject::connect(&camera,&CaptureController::changed,&app,[&]{const QString current=QString("active=%1 busy=%2 recording=%3 private=%4 frame=%5 message=%6").arg(camera.active()).arg(camera.busy()).arg(camera.recording()).arg(camera.privateState()).arg(camera.hasFrame()).arg(camera.message());if(previous!=current){qInfo().noquote()<<current;previous=current;}});
 QObject::connect(&app,&QGuiApplication::applicationStateChanged,&app,[](Qt::ApplicationState state){qInfo()<<"Application state"<<state;});
 engine.addImageProvider("capture",images);engine.rootContext()->setContextProperty("Camera",&camera);engine.load(QUrl("qrc:/Capture.qml"));
 if(engine.rootObjects().isEmpty())return 2;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());const auto args=app.arguments();
 const auto scenario=args.value(1),output=args.value(2);if(scenario=="wide"){window->setWidth(1000);window->setHeight(600);}else window->setWidth(360);
 QJsonObject result;QString error;
 auto check=[&](bool ok,const QString &text){result[text]=ok;if(!ok&&error.isEmpty())error=text;return ok;};
 auto click=[&](const char *name){auto *item=window->findChild<QQuickItem*>(name);if(!item||!item->isEnabled()||!item->isVisible()){check(false,QString("click ")+name);return false;}QTest::mouseClick(window,Qt::LeftButton,Qt::NoModifier,item->mapToScene(QPointF(item->width()/2,item->height()/2)).toPoint());QTest::qWait(100);return true;};
 auto method=[&](const QString &method,const QVariantList &arguments=QVariantList{}){auto msg=QDBusMessage::createMethodCall("org.ethercamera.OfflineFixture","/fixture","org.ethercamera.OfflineFixture",method);msg.setArguments(arguments);return QDBusConnection::sessionBus().call(msg);};
 auto snap=[&](const QString &name){check(window->grabWindow().save(output+"/"+name+".png"),name+" screenshot");};
 QDir().mkpath(output);check(QTest::qWaitForWindowExposed(window),"window exposed");window->requestActivate();
 check(until([&]{return !camera.busy()&&!camera.privateState();}),"privacy ready");
 check(!camera.active()&&!camera.hasFrame(),"no automatic capture");
 if(scenario=="blocked"||scenario=="wide"){
  check(camera.devices().isEmpty(),"vendor nodes excluded");auto *shutter=window->findChild<QQuickItem*>("shutter");auto *start=window->findChild<QQuickItem*>("start");
  check(shutter&&!shutter->isEnabled()&&start&&!start->isEnabled(),"capture disabled without hardware");snap("blocked");
 }else{
  check(!camera.devices().isEmpty(),scenario=="physical-capture"?"physical camera available":"offline test source available");click("start");check(!camera.active(),"consent required");
  click("consentCancel");check(!camera.active(),"cancel never starts capture");click("start");click("consentAccept");
  if(scenario=="start-failure"){
   check(until([&]{return !camera.busy()&&camera.message().contains("OFFLINE start failure");}),"start failure reason preserved");
   check(!camera.active()&&!camera.hasFrame(),"failed source cannot enable shutter");snap("start-failure");
  }else{
  check(until([&]{return camera.hasFrame()&&!camera.busy();}),"JPEG fd displayed");snap("preview");
  if(scenario=="capture"||scenario=="physical-capture"){
   click("shutter");check(until([&]{return !camera.savedReference().isEmpty()&&!camera.busy();}),"photo saved");result["photoReference"]=camera.savedReference();
   click("videoMode");click("shutter");click("recordCancel");check(!camera.recording(),"video dialog cancel");
   click("shutter");click("recordSilent");check(until([&]{return camera.recording()&&!camera.busy();}),"video recording");
   QTest::qWait(1500);snap("recording");click("shutter");check(until([&]{return !camera.busy()&&!camera.active()&&!camera.recording();}),"video finalized and released");
   check(!camera.savedReference().isEmpty()&&camera.savedReference()!=result["photoReference"].toString(),"video reference received");result["videoReference"]=camera.savedReference();snap("saved");
  }else if(scenario=="revoked"){
   method("Lock");check(until([&]{return camera.privateState()&&!camera.active()&&!camera.hasFrame();}),"lock clears preview and lease");snap("revoked");
  }else if(scenario=="disconnected"){
   method("Disconnect");check(until([&]{return !camera.active()&&!camera.hasFrame();}),"disconnect clears preview and lease");snap("disconnected");
  }else if(scenario=="owner-loss"){
   method("StopBackend");check(until([&]{return camera.privateState()&&!camera.active()&&!camera.hasFrame();}),"backend loss clears preview");snap("owner-loss");
  }else if(scenario=="background"){
   window->hide();check(until([&]{return !camera.active()&&!camera.hasFrame();}),"background releases capture");
  }else if(scenario=="denied"){
   method("Deny");check(until([&]{return camera.permissionDenied()&&!camera.active()&&!camera.hasFrame();}),"policy revocation clears preview");snap("denied");
  }
  }
 }
 result["error"]=error;QFile file(output+"/result.json");file.open(QIODevice::WriteOnly);file.write(QJsonDocument(result).toJson());camera.release();QTest::qWait(200);
 return error.isEmpty()?0:3;
}
