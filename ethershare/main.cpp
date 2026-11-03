#include "client.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <QQuickWindow>
#include <QScreen>
#include <QTimer>
#include <QIcon>
#include <unistd.h>
int main(int argc,char **argv){
 if(geteuid()==0){fprintf(stderr,"Run EtherShare as the desktop user.\n");return 1;}
 QGuiApplication app(argc,argv);app.setApplicationName("EtherShare");app.setOrganizationName("Etherneco");app.setDesktopFileName("ethershare");app.setWindowIcon(QIcon::fromTheme("ethershare"));
 ShareClient client;
 QObject::connect(&client,&ShareClient::notice,&app,[](const QString &title,const QString &message){
  auto m=QDBusMessage::createMethodCall("org.freedesktop.Notifications","/org/freedesktop/Notifications","org.freedesktop.Notifications","Notify");
  m.setArguments({"EtherShare",uint(0),"ethershare",title,message,QStringList(),QVariantMap(),5000});QDBusConnection::sessionBus().asyncCall(m);
 });
 QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("Share",&client);
 engine.rootContext()->setContextProperty("Core",QVariantMap{{"preferences",QVariantMap{{"dark",false},{"accent","#087DFF"},{"fontScale",1.0},{"animations",true}}}});
 engine.rootContext()->setContextProperty("PocketDisplay",false);
 engine.load(QUrl("qrc:/ethershare/Main.qml"));if(engine.rootObjects().isEmpty())return 1;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
 auto adapt=[&]{auto n=window->screen()?window->screen()->name():QString();engine.rootContext()->setContextProperty("PocketDisplay",n.startsWith("DSI")||n.startsWith("eDP"));};
 QObject::connect(window,&QWindow::screenChanged,&engine,adapt);adapt();
 const auto args=app.arguments();if(args.contains("--desktop"))window->resize(1920,1080);
 int capture=args.indexOf("--capture");if(capture>=0&&capture+1<args.size())QTimer::singleShot(2500,&app,[&,capture]{app.exit(window->grabWindow().save(args[capture+1])?0:3);});
 return app.exec();
}
