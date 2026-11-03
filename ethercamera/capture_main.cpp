#include "capture_controller.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QTimer>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <unistd.h>
int main(int argc,char **argv){
 if(geteuid()==0){fprintf(stderr,"Run EtherCamera as the desktop user\n");return 1;}
 if(!qEnvironmentVariableIsSet("QT_QUICK_BACKEND"))qputenv("QT_QUICK_BACKEND","software");
 qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
 QGuiApplication app(argc,argv);app.setApplicationName("EtherCamera");app.setOrganizationName("Etherneco");app.setDesktopFileName("ethercamera-app");
 auto *images=new CaptureImage;CaptureController camera(images);QQmlApplicationEngine engine;
 engine.addImageProvider("capture",images);engine.rootContext()->setContextProperty("Camera",&camera);
 engine.load(QUrl("qrc:/Capture.qml"));if(engine.rootObjects().isEmpty())return 2;
 // Screenshot mode never grants camera/microphone consent or starts a capture.
 const auto args=app.arguments();const int screenshot=args.indexOf("--screenshot");
 if(screenshot>0&&screenshot+1<args.size())QTimer::singleShot(2500,&app,[&]{
  auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());const auto target=args[screenshot+1];
  const bool rendered=window&&window->grabWindow().save(target);QFile result(target+".json");
  if(result.open(QIODevice::WriteOnly))result.write(QJsonDocument(QJsonObject{{"rendered",rendered},{"devices",int(camera.devices().size())},{"active",camera.active()},{"private",camera.privateState()},{"hasFrame",camera.hasFrame()}}).toJson());
  app.exit(rendered?0:3);
 });
 return app.exec();
}
