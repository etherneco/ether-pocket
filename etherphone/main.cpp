#include "phoneclient.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QTimer>
#include <QScreen>
#include <QLockFile>
#include <QLocalServer>
#include <QLocalSocket>
#include <QStandardPaths>
#include <sys/stat.h>
int main(int argc,char **argv){
 umask(0077);qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
 QGuiApplication app(argc,argv);app.setOrganizationName("Etherneco");app.setApplicationName("EtherPhone");
 const auto endpoint=QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation)+"/etherphone-ui";
 QLockFile lock(endpoint+".lock");
 if(!lock.tryLock(100)){QLocalSocket socket;socket.connectToServer(endpoint);if(socket.waitForConnected(500)){socket.write(app.arguments().contains("--history")?"history":"show");socket.waitForBytesWritten(500);}return 0;}
 PhoneClient phone;QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("Phone",&phone);
 const auto args=app.arguments();
 bool pocket=false;for(auto *s:app.screens())if(s->name().startsWith("DSI")||s->name().startsWith("eDP"))pocket=true;
 engine.rootContext()->setContextProperty("PocketDisplay",pocket&&!args.contains("--desktop"));
 engine.load(QUrl("qrc:/Main.qml"));if(engine.rootObjects().isEmpty())return 2;
 auto *window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
 auto showHistory=[window]{window->setProperty("tab",1);window->showNormal();window->raise();window->requestActivate();};
 if(args.contains("--history"))showHistory();
 QObject::connect(&phone,&PhoneClient::openHistory,window,showHistory);
 QLocalServer server;QLocalServer::removeServer(endpoint);server.listen(endpoint);
 QObject::connect(&server,&QLocalServer::newConnection,window,[&]{auto *socket=server.nextPendingConnection();if(!socket)return;QObject::connect(socket,&QLocalSocket::readyRead,window,[socket,window,showHistory]{auto data=socket->read(32);if(data=="history")showHistory();else{window->showNormal();window->raise();window->requestActivate();}socket->disconnectFromServer();});QObject::connect(socket,&QLocalSocket::disconnected,socket,&QObject::deleteLater);});
 QObject::connect(&phone,&PhoneClient::incoming,window,[window]{window->setProperty("tab",0);});
 int capture=args.indexOf("--capture");
 if(capture>=0&&capture+1<args.size())QTimer::singleShot(2500,&app,[&]{app.exit(window->grabWindow().save(args[capture+1])?0:3);});
 return app.exec();
}
