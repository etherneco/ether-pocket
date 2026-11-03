#include "controller.h"
#include "mobile.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QScreen>
#include <QStandardPaths>
#include <QDir>
#include <QTimer>
#include <QDBusInterface>
#include <QDBusConnection>
#include <sys/stat.h>
int main(int argc,char **argv){
 umask(0077);qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
 QGuiApplication app(argc,argv);app.setOrganizationName("Etherneco");app.setApplicationName("EtherSMS");
 const auto args=app.arguments();auto option=[&](const QString &key){int i=args.indexOf(key);return i>=0&&i+1<args.size()?args[i+1]:QString();};
 const auto capture=option("--capture");auto bus=QDBusConnection::sessionBus();
 if(capture.isEmpty()&&!bus.registerService("org.etherneco.EtherSMS")){QDBusInterface existing("org.etherneco.EtherSMS","/org/etherneco/EtherSMS","org.etherneco.EtherSMS",bus);existing.asyncCall("Activate");return 0;}
 Mobile mobile;MobileSmsTransport transport(&mobile);SmsSettings settings;Speech speech;
 Controller sms(&transport,&settings,&speech,QStandardPaths::writableLocation(QStandardPaths::AppDataLocation)+"/messages.sqlite");
 if(capture.isEmpty())bus.registerObject("/org/etherneco/EtherSMS",&sms,QDBusConnection::ExportAllSlots);
 QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("Sms",&sms);engine.rootContext()->setContextProperty("SmsTransport",&transport);engine.rootContext()->setContextProperty("SmsSettings",&settings);engine.rootContext()->setContextProperty("Speech",&speech);
 bool pocket=false;for(auto *s:QGuiApplication::screens())if(s->name().startsWith("DSI")||s->name().startsWith("eDP"))pocket=true;
 engine.rootContext()->setContextProperty("PocketDisplay",pocket&&!args.contains("--desktop"));
 engine.load(QUrl("qrc:/Main.qml"));if(engine.rootObjects().isEmpty())return 2;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
 auto updateDisplay=[&]{const auto name=window->screen()?window->screen()->name():QString();engine.rootContext()->setContextProperty("PocketDisplay",!args.contains("--desktop")&&(name.startsWith("DSI")||name.startsWith("eDP")));};
 QObject::connect(window,&QWindow::screenChanged,&engine,updateDisplay);updateDisplay();
 QObject::connect(&sms,&Controller::activated,window,[window]{window->show();window->raise();window->requestActivate();});
 if(args.contains("--desktop"))window->resize(1280,720);
 if(!capture.isEmpty())QTimer::singleShot(2500,&app,[&]{bool ok=window->grabWindow().save(capture);app.exit(ok?0:3);});
 return app.exec();
}
