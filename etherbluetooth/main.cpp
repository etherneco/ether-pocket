#include "bluetooth.h"
#include "audio.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QFile>
#include <QQuickWindow>
#include <unistd.h>
#include <sys/stat.h>
int main(int argc,char **argv){
    if(geteuid()==0){fprintf(stderr,"Run EtherBluetooth as the desktop user, never root.\n");return 1;}
    umask(0077);
    qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
    QGuiApplication app(argc,argv);app.setApplicationName("EtherBluetooth");app.setOrganizationName("Etherneco");
    Bluetooth bluetooth;Audio audio;
    QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("Audio",&audio);engine.rootContext()->setContextProperty("Bluetooth",&bluetooth);
    engine.load(QUrl("qrc:/Main.qml"));if(engine.rootObjects().isEmpty())return 2;
    if(app.arguments().contains("--compact")){engine.rootObjects()[0]->setProperty("width",420);engine.rootObjects()[0]->setProperty("height",780);}
    if(app.arguments().contains("--doctor")){engine.rootObjects()[0]->setProperty("page","doctor");bluetooth.diagnose();}
    if(app.arguments().contains("--audio")){engine.rootObjects()[0]->setProperty("page","audio");audio.refresh();}
    if(app.arguments().contains("--smoke-test")){
        bluetooth.diagnose();
        QTimer::singleShot(6000,&app,[&]{
            auto result=QJsonObject{{"adapters",QJsonArray::fromVariantList(bluetooth.adapters())},{"devices",QJsonArray::fromVariantList(bluetooth.devices())},{"rootObjects",engine.rootObjects().size()}};
            auto window=qobject_cast<QQuickWindow*>(engine.rootObjects()[0]);if(window)window->grabWindow().save("/tmp/etherbluetooth-smoke.png");
            printf("%s\n",QJsonDocument(result).toJson(QJsonDocument::Compact).constData());app.quit();
        });
    }
    return app.exec();
}
