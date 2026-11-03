#include "core.h"
#include "mobile.h"
#include "sms.h"
#include "settings.h"
#include "client.h"
#include "hardwareclient.h"
#include "powerclient.h"
#include "audioclient.h"
#include "cameraclient.h"
#include "fingerprintclient.h"
#include "locationclient.h"
#include "updateclient.h"
#include "backupclient.h"
#include "sensorclient.h"
#include "phoneclient.h"
#include "notificationclient.h"
#include "lockclient.h"
#include "mobile_ui_test.h"
#include "settings_ui_test.h"
#include "integration.h"
#include "distributor.h"
#include "media.h"
#include "media_test.h"
#include "pocket.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QDBusConnection>
#include <QLockFile>
#include <QStandardPaths>
#include <QTimer>
#include <QScreen>
#include <QDir>
#include <QIcon>
#include <QLocalServer>
#include <QLocalSocket>
#include <QSocketNotifier>
#include <QNetworkProxy>
#include <QJsonDocument>
#include <QJsonObject>
#include <csignal>
#include <fcntl.h>
#include <unistd.h>
#include <memory>
static int signalWrite=-1;
static void exitSignal(int){if(signalWrite>=0){const char byte=1;const auto result=::write(signalWrite,&byte,1);(void)result;}}
int main(int argc,char **argv){
    if(geteuid()==0){fprintf(stderr,"EtherShell must run as the desktop user.\n");return 1;}
    QStringList arguments;for(int i=1;i<argc;++i)arguments<<QString::fromLocal8Bit(argv[i]);
    const bool development=arguments.contains("--development");
    if(arguments.contains("--mobile-ui-test")&&(!development||qEnvironmentVariable("ETHERSHELL_MOBILE_TEST_OUTPUT").isEmpty())){fprintf(stderr,"Mobile UI acceptance requires an isolated development session and output directory.\n");return 2;}
    if(development&&(qEnvironmentVariableIntValue("ETHERSHELL_NESTED_CONFIRMED")!=1||!qEnvironmentVariable("DISPLAY").startsWith(":93"))){fprintf(stderr,"Start development through ethershell2-preview so display, settings and D-Bus are isolated.\n");return 2;}
    const bool experience=development||arguments.contains("--experience");
    if(experience&&arguments.contains("--floating"))qputenv("ETHERSHELL_FLOATING","1");
    if(experience&&arguments.contains("--native-frames"))qputenv("ETHERSHELL_NATIVE_FRAMES","1");
    if(development)qputenv("ETHERSHELL_DEVELOPMENT","1");
    if(development&&arguments.contains("--desktop"))qputenv("ETHERSHELL_DESKTOP_TEST","1");
    if(experience)qputenv("ETHERSHELL_EXPERIENCE","1");
    if(experience&&!development&&qEnvironmentVariableIntValue("ETHERSHELL_EXPERIMENTAL")!=1&&qEnvironmentVariableIntValue("ETHERSHELL_CURRENT_SESSION")!=1){fprintf(stderr,"Use ethershell2-start to integrate with the current X11 session.\n");return 2;}
    const auto locale=qEnvironmentVariable("LC_ALL",qEnvironmentVariable("LC_CTYPE",qEnvironmentVariable("LANG")));
    if(locale.isEmpty()||locale=="C"||locale=="POSIX"){qunsetenv("LC_ALL");qputenv("LANG","C.UTF-8");qputenv("LC_CTYPE","C.UTF-8");}
    qputenv("QT_QPA_PLATFORM","xcb");
    qputenv("QT_QUICK_BACKEND","software");
    // QML sizes itself from panel pixels. Keep its X11 geometry/struts in the
    // same coordinate space; XFCE's 264 DPI still scales other applications.
    qputenv("QT_ENABLE_HIGHDPI_SCALING","0");
    qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
    if(QFile::exists("/usr/lib/aarch64-linux-gnu/qt6/plugins/platformthemes/libqgtk3.so"))qputenv("QT_QPA_PLATFORMTHEME","gtk3");
    // Applications launched by the shell inherit native X11 touch support,
    // including when EtherShell is started in an existing XFCE session.
    qputenv("MOZ_USE_XINPUT2","1");
    qputenv("QT_QUICK_CONTROLS_MOBILE","1");
    qunsetenv("GDK_CORE_DEVICE_EVENTS");
    qunsetenv("QT_XCB_NO_XI2");
    qunsetenv("QT_XCB_NO_TOUCH");
    QGuiApplication app(argc,argv);app.setApplicationName("EtherShell");app.setOrganizationName("Etherneco");app.setQuitOnLastWindowClosed(true);
    const auto runtime=QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
    QString suffix=experience?"-experience-"+qEnvironmentVariable("DISPLAY").remove(':').replace('.','-'):QString();
    const auto socketPath=runtime+"/ethershell-control"+suffix;
    QLockFile lock(runtime+"/ethershell"+suffix+".lock");if(!lock.tryLock(100)){QLocalSocket socket;socket.connectToServer(socketPath);socket.waitForConnected(500);return 0;}
    int signalPipe[2];if(::pipe(signalPipe)==0){signalWrite=signalPipe[1];fcntl(signalPipe[0],F_SETFL,O_NONBLOCK);fcntl(signalPipe[1],F_SETFL,O_NONBLOCK);auto *notifier=new QSocketNotifier(signalPipe[0],QSocketNotifier::Read,&app);QObject::connect(notifier,&QSocketNotifier::activated,&app,[&]{char buf[16];::read(signalPipe[0],buf,sizeof(buf));app.exit(0);});std::signal(SIGTERM,exitSignal);std::signal(SIGINT,exitSignal);}
    if(QIcon::themeName().isEmpty())QIcon::setThemeName("Adwaita");
    Core core;
    Mobile mobile;
    MobileSmsTransport smsTransport(&mobile,nullptr,false);
    SmsSettings smsSettings;
    ShareClient share;
    HardwareClient hardware;
    QObject::connect(&share,&ShareClient::notice,&core,[&core](const QString &title,const QString &message){core.notify(title,message);});
    QObject::connect(&mobile,&Mobile::operationChanged,&core,[&]{
        const auto op=mobile.operation();const auto state=op.value("state").toString();
        if(state=="Verification failed"||state=="Permission denied"||state=="Unsupported")core.notify("Mobile Network",op.value("message").toString());
    });
    Pocket pocket;
    Media media;
    PowerClient power(&core,&media);
    AudioClient audio;
    CameraClient camera;
    FingerprintClient fingerprint;
    LocationClient location;
    UpdateClient updates;
    BackupClient backups;
    SensorClient sensors;
    PhoneClient phone;
    QObject::connect(&phone,&PhoneClient::openHistory,&core,[&]{if(!core.preferences().value("homeLocked").toBool())QProcess::startDetached("/usr/bin/etherphone",{"--history"});});
    QObject::connect(&audio,&AudioClient::notice,&core,[&core](const QString &title,const QString &message){core.notify(title,message);});
    QObject::connect(&power,&PowerClient::notice,&core,[&core](const QString &title,const QString &message){core.notify(title,message);});
    QObject::connect(&media,&Media::failed,&core,[&core](const QString &message){core.notify("EtherShell",message);});
    if(app.arguments().contains("--catalog-offline-test"))QNetworkProxy::setApplicationProxy(QNetworkProxy(QNetworkProxy::HttpProxy,"127.0.0.1",9));
    Distributor distributor;
    NotificationClient notifications;
    LockClient lockControl;
    media.setLockGuard([&]{return lockControl.beforeBlank();});
    QObject::connect(&lockControl,&LockClient::changed,&media,[&]{media.setSecureLockPolicy(lockControl.automatic());});
    QObject::connect(&notifications,&NotificationClient::changed,&core,[&]{core.synchronizeNotices(notifications.state().value("cards").toList());});
    auto notificationSession=[&]{notifications.session(lockControl.privacyRequired()||core.preferences().value("homeLocked").toBool(),!phone.state().value("calls").toList().isEmpty(),media.property("screenBlank").toBool());};
    QObject::connect(&core,&Core::preferencesChanged,&notifications,notificationSession);
    QObject::connect(&phone,&PhoneClient::changed,&notifications,notificationSession);
    QObject::connect(&media,&Media::powerStateChanged,&notifications,notificationSession);
    QObject::connect(&lockControl,&LockClient::changed,&notifications,notificationSession);
    notificationSession();
    QQmlApplicationEngine engine;engine.addImageProvider("icons",new Icons);
    engine.rootContext()->setContextProperty("Core",&core);
    engine.rootContext()->setContextProperty("Mobile",&mobile);
    engine.rootContext()->setContextProperty("SmsSettings",&smsSettings);
    engine.rootContext()->setContextProperty("Share",&share);
    engine.rootContext()->setContextProperty("Hardware",&hardware);
    engine.rootContext()->setContextProperty("Power",&power);
    engine.rootContext()->setContextProperty("AudioControl",&audio);
    engine.rootContext()->setContextProperty("CameraControl",&camera);
    engine.rootContext()->setContextProperty("FingerprintControl",&fingerprint);
    engine.rootContext()->setContextProperty("LocationControl",&location);
    engine.rootContext()->setContextProperty("UpdateControl",&updates);
    engine.rootContext()->setContextProperty("BackupControl",&backups);
    engine.rootContext()->setContextProperty("SensorControl",&sensors);
    engine.rootContext()->setContextProperty("Phone",&phone);
    engine.rootContext()->setContextProperty("Notifications",&notifications);
    engine.rootContext()->setContextProperty("LockControl",&lockControl);
    engine.rootContext()->setContextProperty("SmsTransport",&smsTransport);
    engine.rootContext()->setContextProperty("Pocket",&pocket);
    engine.addImageProvider("windows",new WindowPreviews(&pocket));
    engine.rootContext()->setContextProperty("DevelopmentSession",development);
    engine.rootContext()->setContextProperty("DevelopmentDesktop",qEnvironmentVariableIntValue("ETHERSHELL_DESKTOP_TEST")==1);
    engine.rootContext()->setContextProperty("FloatingWindows",qEnvironmentVariableIntValue("ETHERSHELL_FLOATING")==1);
    engine.rootContext()->setContextProperty("NativeFrames",qEnvironmentVariableIntValue("ETHERSHELL_NATIVE_FRAMES")==1);
    engine.rootContext()->setContextProperty("Media",&media);
    engine.rootContext()->setContextProperty("Distributor",&distributor);
    engine.rootContext()->setContextProperty("AvailableScreens",QVariant::fromValue(QGuiApplication::screens()));
    auto updateScreens=[&]{
        if(!engine.rootObjects().isEmpty())for(auto*s:QGuiApplication::screens())if(s->name().startsWith("DSI")||s->name().startsWith("eDP"))qobject_cast<QQuickWindow*>(engine.rootObjects().first())->setScreen(s);
        engine.rootContext()->setContextProperty("AvailableScreens",QVariant::fromValue(QGuiApplication::screens()));
    };
    QObject::connect(&app,&QGuiApplication::screenAdded,&engine,updateScreens);
    QObject::connect(&app,&QGuiApplication::screenRemoved,&engine,updateScreens);
    engine.load(QUrl(experience?"qrc:/qml/Experience.qml":"qrc:/qml/Main.qml"));if(engine.rootObjects().isEmpty())return 3;
    updateScreens();
    if(app.arguments().contains("--catalog-test")||app.arguments().contains("--catalog-offline-test")){
        auto *w=qobject_cast<QQuickWindow*>(engine.rootObjects().first());w->setProperty("page","store");
        QObject::connect(&distributor,&Distributor::refreshed,&app,[&](bool ok){bool offline=app.arguments().contains("--catalog-offline-test");QString suffix=offline?"offline":"live";distributor.diagnose(QDir::homePath()+"/ethershell-validation/distributor-"+suffix+".json");bool preserved=false;for(auto v:distributor.catalog())if(!v.toMap()["variants"].toList().isEmpty())preserved=true;bool passed=offline?(!ok&&preserved):ok;QTimer::singleShot(500,&app,[&,suffix,passed]{auto*w=qobject_cast<QQuickWindow*>(engine.rootObjects().first());w->grabWindow().save(QDir::homePath()+"/ethershell-validation/distributor-"+suffix+".png");app.exit(passed?0:5);});});
    }
    QLocalServer control;QLocalServer::removeServer(socketPath);control.listen(socketPath);
    QObject::connect(&control,&QLocalServer::newConnection,&engine,[&]{
        auto *client=control.nextPendingConnection();if(!client)return;
        // Local user socket, one newline-delimited request (bounded to 8 KiB).
        auto buffer=std::make_shared<QByteArray>();auto handled=std::make_shared<bool>(false);
        auto dispatch=[&,client,buffer,handled](bool legacy){
            if(*handled)return;buffer->append(client->readAll());if(buffer->size()>8192){*handled=true;client->disconnectFromServer();return;}
            if(!legacy&&!buffer->contains('\n'))return;*handled=true;
            auto *w=qobject_cast<QQuickWindow*>(engine.rootObjects().first());auto request=QJsonDocument::fromJson(*buffer).object();auto command=request["command"].toString();
            if(experience&&w->property("homeLocked").toBool()&&command!="diagnose"){
                if(command=="home"){QMetaObject::invokeMethod(w,"home",Q_ARG(QVariant,QVariant("home")));client->write("ok\n");}
                else client->write("locked\n");
                client->disconnectFromServer();return;
            }
            if(command=="window")pocket.action(request["action"].toString(),request["id"].toString());
            else if(command=="keyboard")w->setProperty("keyboardVisible",request["visible"].toBool());
            else if(command=="power-display"){
                const auto action=request["action"].toString();
                if(action=="off")power.screenOff();else if(action=="on")power.wake();
                client->write(QJsonDocument(QJsonObject{{"blank",media.property("screenBlank").toBool()},{"timeoutSeconds",media.property("powerTimeout").toInt()},{"brightness",QJsonValue::fromVariant(core.telemetry().value("brightness"))}}).toJson(QJsonDocument::Compact)+'\n');client->disconnectFromServer();return;
            }
            else if(command=="power-brightness")power.setBrightness(request["value"].toInt());
            else if(command=="pocket")pocket.setEnabled(request["enabled"].toBool());
            else if(command=="theme")core.setting("dark",request["dark"].toBool());
            else if(command=="setting")core.setting(request["name"].toString(),request["value"].toVariant());
            else if(command=="launch"){core.launch(request["id"].toString());if(experience)w->hide();else w->showMinimized();}
            else if(command=="control"){core.control(request["action"].toString(),request["value"].toString());if(QStringList{"terminal","files","network-settings","bluetooth-settings","display-settings"}.contains(request["action"].toString())){if(experience)w->hide();else w->showMinimized();}}
            else if(command=="text")core.text(request["text"].toString());
            else if(command=="key")core.key(request["symbol"].toString(),request["ctrl"].toBool(),request["alt"].toBool(),request["shift"].toBool());
            else if(command=="ui"){if(request.contains("sidebar"))w->setProperty("sidebarVisible",request["sidebar"].toBool());if(request.contains("overview"))w->setProperty("overviewVisible",request["overview"].toBool());if(request.contains("quick"))w->setProperty("quickVisible",request["quick"].toBool());if(request["menu"].toBool())QMetaObject::invokeMethod(w,"showMenu",Q_ARG(QVariant,QVariant(request["id"].toString())));else if(request.contains("menu"))w->setProperty("menuVisible",false);}
            else if(command=="diagnose"){
                QString dir=experience?QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/ethershell/validation":QDir::homePath()+"/ethershell-validation";QDir().mkpath(dir);pocket.diagnose(dir+"/pocket.json");
                QFile f(dir+"/pocket.json");if(f.open(QIODevice::ReadOnly)){auto data=QJsonDocument::fromJson(f.readAll()).object();f.close();QJsonObject ui;for(auto name:{"page","homeLocked","overviewVisible","quickVisible","sidebarVisible","menuVisible","keyboardVisible","closeCandidate","homeShown"})ui[name]=QJsonValue::fromVariant(w->property(name));data["ui"]=ui;data["pid"]=int(QCoreApplication::applicationPid());if(f.open(QIODevice::WriteOnly))f.write(QJsonDocument(data).toJson());}
            }
            else if(command=="settings-page"){
                if(auto *settings=w->findChild<QObject*>("settingsWorkspace")){
                    w->setProperty("page","settings");QMetaObject::invokeMethod(settings,"go",Q_ARG(QVariant,QVariant(request.value("route").toString("home"))),Q_ARG(QVariant,QVariant("")));w->showNormal();w->raise();w->requestActivate();
                }
            }
            else if(command=="notification-state"){
                const auto state=notifications.state();
                client->write(QJsonDocument::fromVariant(QVariantMap{{"ready",state.value("ready")},{"unread",state.value("unread")},{"locked",state.value("locked")},{"dnd",state.value("dnd")},{"cards",state.value("cards").toList().size()},{"bannerId",notifications.banner().value("id")},{"audioStatus",state.value("audioStatus")},{"message",notifications.message()}}).toJson(QJsonDocument::Compact)+'\n');client->disconnectFromServer();return;
            }
            else if(command=="settings-state"){
                QJsonObject state{{"page",QJsonValue::fromVariant(w->property("page"))},{"keyboard",QJsonValue::fromVariant(w->property("keyboardVisible"))},{"width",w->width()},{"height",w->height()}};
                state["phoneServiceReady"]=phone.state().value("ready").toBool();
                state["phoneServiceMessage"]=phone.message();
                if(auto *settings=w->findChild<QObject*>("settingsWorkspace")){
                    state["route"]=QJsonValue::fromVariant(settings->property("route"));
                    if(auto *scroll=settings->findChild<QObject*>("settingsPageScroll")){
                        auto *flick=scroll->property("contentItem").value<QQuickItem*>();if(flick)state["scrollY"]=QJsonValue::fromVariant(flick->property("contentY"));
                    }
                }
                client->write(QJsonDocument(state).toJson(QJsonDocument::Compact)+'\n');client->disconnectFromServer();return;
            }
            else if(command=="settings-screenshot"&&(w->property("page")=="settings"||w->property("page")=="mobile")){
                const auto dir=QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/ethershell/validation";QDir().mkpath(dir);
                w->grabWindow().save(dir+"/settings2-window.png");w->screen()->grabWindow(0).save(dir+"/settings2-screen.png");
            }
            else if(command=="preview")pocket.preview(request["id"].toString(),420).save(QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/ethershell/last-preview.png");
            else {w->setProperty("page",request.value("page").toString("home"));w->showNormal();w->raise();w->requestActivate();}
            client->write("ok\n");client->disconnectFromServer();
        };
        QObject::connect(client,&QLocalSocket::readyRead,&engine,[dispatch]{dispatch(false);});
        QObject::connect(client,&QLocalSocket::disconnected,&engine,[client]{client->deleteLater();});
        QTimer::singleShot(100,client,[dispatch]{dispatch(true);});
    });
    if(app.arguments().contains("--integration-test"))new Integration(&core,qobject_cast<QQuickWindow*>(engine.rootObjects().first()));
    if(app.arguments().contains("--mobile-ui-test"))new MobileUiTest(&core,&mobile,qobject_cast<QQuickWindow*>(engine.rootObjects().first()));
    if(app.arguments().contains("--settings-ui-test")){
        if(!development||qEnvironmentVariable("ETHERSHELL_MOBILE_TEST_OUTPUT").isEmpty())return 2;
        new SettingsUiTest(&core,qobject_cast<QQuickWindow*>(engine.rootObjects().first()));
    }
    if(app.arguments().contains("--media-test"))new MediaTest(&media,qobject_cast<QQuickWindow*>(engine.rootObjects().first()));
    if(app.arguments().contains("--smoke-test")){QTimer::singleShot(5000,&app,[&]{core.diagnose(QDir::homePath()+"/ethershell-smoke.json");for(auto *o:engine.rootObjects()){auto*w=qobject_cast<QQuickWindow*>(o);if(w)w->grabWindow().save(QDir::homePath()+"/ethershell-smoke.png");}app.quit();});}
    return app.exec();
}
