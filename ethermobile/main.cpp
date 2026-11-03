#include "mobile.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QTimer>
#include <sys/stat.h>
#include <unistd.h>

int main(int argc,char **argv){
    if(geteuid()==0){fprintf(stderr,"Run EtherMobile as the desktop user.\n");return 1;}
    umask(0077);qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
    QGuiApplication app(argc,argv);app.setApplicationName("EtherMobile");app.setOrganizationName("Etherneco");
    Mobile mobile;QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("Mobile",&mobile);
    engine.load(QUrl("qrc:/Main.qml"));if(engine.rootObjects().isEmpty())return 2;
    auto *root=engine.rootObjects()[0];
    if(app.arguments().contains("--compact")){root->setProperty("width",420);root->setProperty("height",820);}
    if(app.arguments().contains("--dark"))root->setProperty("dark",true);
    if(app.arguments().contains("--external")){root->setProperty("width",1920);root->setProperty("height",1080);}
    if(app.arguments().contains("--doctor")){root->setProperty("page","Diagnostics");mobile.diagnose();}
    if(app.arguments().contains("--smoke-test"))QTimer::singleShot(7000,&app,[&]{
        auto *window=qobject_cast<QQuickWindow*>(root);
        const QString screenshot=QString("/tmp/ethermobile-smoke-%1.png").arg(getuid());
        const bool captured=window && window->grabWindow().save(screenshot);
        // Status contains presentation fields only, never SIM identifiers/secrets.
        printf("%s\n",QJsonDocument(QJsonObject{{"status",QJsonObject::fromVariantMap(mobile.snapshot())},{"rootObjects",int(engine.rootObjects().size())},{"stages",int(mobile.stages().size())},{"captured",captured},{"screenshot",screenshot}}).toJson(QJsonDocument::Compact).constData());app.exit(captured?0:3);
    });
    return app.exec();
}
