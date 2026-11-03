#include "core.h"
#include "keyboardinput.h"
#include <QInputMethodQueryEvent>
#include "bluetooth.h"
#include <QGuiApplication>
#include <QIcon>
#include <QDirIterator>
#include <QSettings>
#include <QStandardPaths>
#include <QFile>
#include <QSaveFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QImageReader>
#include <QTime>
#include <QPainterPath>
#include <QProcessEnvironment>
#include <QDateTime>
#include <QRegularExpression>
#include <QScreen>
#include <QWindow>
#include <QPainter>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusReply>
#include <QDBusObjectPath>
#include <QDBusVariant>
#include <QDBusConnectionInterface>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDesktopServices>
#include <QUrl>
#include <algorithm>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/keysym.h>
#include <X11/Xutil.h>
#include <X11/extensions/XTest.h>
#include <X11/XKBlib.h>

static QString read(const QString &path) {QFile f(path); return f.open(QIODevice::ReadOnly)?QString::fromUtf8(f.readAll()).trimmed():QString();}
// Desktop entries are not INI: semicolons delimit XDG lists, not comments.
static QVariantMap desktopEntry(const QString &path){
    QVariantMap fields;bool active=false;
    for(const auto &line:read(path).split('\n')){
        if(line.startsWith('[')){active=line.trimmed()=="[Desktop Entry]";continue;}
        if(!active||line.startsWith('#'))continue;int eq=line.indexOf('=');if(eq<1)continue;
        QString value=line.mid(eq+1);value.replace("\\s"," ");value.replace("\\n","\n");value.replace("\\t","\t");value.replace("\\r","\r");value.replace("\\\\","\\");
        fields.insert(line.left(eq).trimmed(),value);
    }return fields;
}
QImage Icons::requestImage(const QString &id,QSize *size,const QSize &requested) {
    QSize s=requested.isValid()?requested:QSize(96,96);
    const QString glyph=id=="camera-photo"?"camera":id=="image-x-generic"?"gallery":id=="mark-location"?"location":id=="call-start"?"phone":id=="preferences-desktop"?"settings":QString();
    QIcon icon=glyph.isEmpty()?QIcon::fromTheme(id):QIcon(":/icons/"+glyph+".svg");
    if (id.startsWith('/')) icon=QIcon(id);
    QImage img=icon.pixmap(s).toImage();
    if(img.isNull()){img=QImage(s,QImage::Format_ARGB32_Premultiplied);img.fill(Qt::transparent);QPainter p(&img);p.setBrush(QColor("#087cff"));p.setPen(Qt::NoPen);p.drawRoundedRect(img.rect().adjusted(4,4,-4,-4),18,18);p.setPen(Qt::white);QFont font=p.font();font.setPixelSize(s.height()/2);p.setFont(font);p.drawText(img.rect(),Qt::AlignCenter,id.left(1).toUpper());}
    if(size)*size=img.size();return img;
}
Core::Core(QObject *parent):QObject(parent) {
    m_bluetooth=new Bluetooth(this,false);
    auto smsBus=QDBusConnection::sessionBus();
    smsBus.connect("org.etherneco.EtherSMS","/org/etherneco/EtherSMS","org.etherneco.EtherSMS","UnreadChanged",this,SLOT(updateSmsUnread(int)));
    auto *smsWatch=new QDBusServiceWatcher("org.etherneco.EtherSMS",smsBus,QDBusServiceWatcher::WatchForOwnerChange,this);
    connect(smsWatch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this]{readSmsUnread();});
    QTimer::singleShot(0,this,&Core::readSmsUnread);
    connect(m_bluetooth,&Bluetooth::changed,this,[this]{
        if(!m_bluetooth->property("error").toString().isEmpty())status(m_bluetooth->property("error").toString());
        readTelemetry();
    });
    m_display=XOpenDisplay(nullptr);
    // logind authorizes the active desktop user without writable sysfs files.
    const auto session=qEnvironmentVariable("XDG_SESSION_ID");
    if(!session.isEmpty()){
        auto get=QDBusMessage::createMethodCall("org.freedesktop.login1","/org/freedesktop/login1","org.freedesktop.login1.Manager","GetSession");get<<session;
        auto *watch=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(get,1500),this);
        connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch]{QDBusPendingReply<QDBusObjectPath> reply=*watch;if(!reply.isError())m_brightnessSession=reply.value().path();watch->deleteLater();readTelemetry();});
    }
    if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")!=1){
    auto get=QDBusMessage::createMethodCall("org.onboard.Onboard","/org/onboard/Onboard/Keyboard","org.freedesktop.DBus.Properties","Get");get<<"org.onboard.Onboard.Keyboard"<<"Visible";
    auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(get,1500),this);
    connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch]{const auto reply=watch->reply();watch->deleteLater();
    if(reply.type()==QDBusMessage::ReplyMessage&&!reply.arguments().isEmpty()&&qvariant_cast<QDBusVariant>(reply.arguments().first()).variant().toBool()){
        m_restoreOnboard=true;auto hide=QDBusMessage::createMethodCall("org.onboard.Onboard","/org/onboard/Onboard/Keyboard","org.onboard.Onboard.Keyboard","Hide");QDBusConnection::sessionBus().asyncCall(hide,1500);
    }});
    }
    m_config=qEnvironmentVariable("ETHERSHELL_CONFIG_DIR",QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/ethershell")+"/preferences.json";
    m_preferences={{"powerBrightnessBattery",-1},{"powerBrightnessExternal",-1},{"schema",1},{"homeLocked",false},{"dark",false},{"scale",1.0},{"keyboardScale",1.0},{"layout","EN"},{"favorites",QStringList()},{"accent","#087cff"},{"airDark",true},
        {"themeMode","light"},{"transparency",.94},{"wallpaper",""},{"animations",true},{"highContrast",false},{"lowPower",false},{"dockAutoHide",false},{"sidebarPinned",false},{"previews",true},{"fontScale",1.0},{"terminalFontSize",12},{"gestures",true},{"edgeBack",true},{"autoKeyboard",true},{"dockOrder",QStringList{"home","apps","tasks","keyboard","touchpad","settings"}}};
    m_preferences["mobileProfileUuid"]="";m_preferences["mobileSettingsSection"]="Mobile Data";
    m_preferences["mobileModeRequested"]="";m_preferences["mobileOperatorRequest"]="";
    const auto doc=QJsonDocument::fromJson(read(m_config).toUtf8());
    if(doc.isObject() && doc.object().value("schema").toInt()==1) {
        const auto obj=doc.object().toVariantMap();
        for(auto it=obj.begin();it!=obj.end();++it) if(m_preferences.contains(it.key()))m_preferences[it.key()]=it.value();
        m_preferences["scale"]=qBound(0.8,m_preferences["scale"].toDouble(),1.5);
        m_preferences["keyboardScale"]=qBound(.85,m_preferences["keyboardScale"].toDouble(),1.2);
        m_preferences["fontScale"]=qBound(.8,m_preferences["fontScale"].toDouble(),1.5);
        m_preferences["transparency"]=qBound(.65,m_preferences["transparency"].toDouble(),1.);
        m_preferences["terminalFontSize"]=qBound(9,m_preferences["terminalFontSize"].toInt(),28);
        if(!QStringList{"light","dark","auto"}.contains(m_preferences["themeMode"].toString()))m_preferences["themeMode"]="light";
        const auto order=m_preferences["dockOrder"].toStringList();if(order.size()!=6||QSet<QString>(order.begin(),order.end())!=QSet<QString>{"home","apps","tasks","keyboard","touchpad","settings"})m_preferences["dockOrder"]=QStringList{"home","apps","tasks","keyboard","touchpad","settings"};
        if(m_preferences["layout"]!="EN" && m_preferences["layout"]!="PL")m_preferences["layout"]="EN";
        if(!QColor(m_preferences["accent"].toString()).isValid())m_preferences["accent"]="#087cff";
    } else if(!read(m_config).isEmpty()) status("Nieprawidłowy format ustawień; użyto wartości domyślnych.");
    discover(); refresh();
    if(!QCoreApplication::arguments().contains("--safe-mode") && qEnvironmentVariableIntValue("ETHERSHELL_SAFE_MODE")!=1 && !QFile::exists(QFileInfo(m_config).absolutePath()+"/safe-mode"))
        run("ethershell-app-settings",{m_preferences["dark"].toBool()?"dark":"light"});
    m_timer.setInterval(10000); connect(&m_timer,&QTimer::timeout,this,&Core::refresh); m_timer.start();
    const auto inputRoot=qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1
        ?qEnvironmentVariable("ETHERSHELL_TEST_INPUT_ROOT","/sys/class/input"):QString("/sys/class/input");
    m_physicalKeyboardConnected=KeyboardInput::connected(inputRoot);
    m_inputTimer.setInterval(750);
    connect(&m_inputTimer,&QTimer::timeout,this,[this,inputRoot]{
        const bool connected=KeyboardInput::connected(inputRoot);
        if(connected!=m_physicalKeyboardConnected){m_physicalKeyboardConnected=connected;emit physicalKeyboardChanged();}
    });
    m_inputTimer.start();
    // Observe every native Qt editor, including search and third-party pages.
    auto localFocus=[this]{
        ++m_focusRevision;
        auto *object=qGuiApp->focusObject();
        QInputMethodQueryEvent query(Qt::ImEnabled);
        if(object)QCoreApplication::sendEvent(object,&query);
        if(qEnvironmentVariableIntValue("ETHERSHELL_KEYBOARD_TRACE")==1)qWarning()<<"Keyboard focus"<<object<<query.value(Qt::ImEnabled)<<QGuiApplication::focusWindow();
        emit textInputFocus(object&&query.value(Qt::ImEnabled).toBool());
    };
    connect(qGuiApp,&QGuiApplication::focusObjectChanged,this,localFocus);
    QTimer::singleShot(0,this,&Core::setupAccessibility);
}
void Core::setupAccessibility(){
    auto address=QDBusMessage::createMethodCall("org.a11y.Bus","/org/a11y/bus","org.a11y.Bus","GetAddress");
    auto *watcher=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(address,1000),this);
    connect(watcher,&QDBusPendingCallWatcher::finished,this,[this,watcher]{
        QDBusPendingReply<QString> reply=*watcher;watcher->deleteLater();if(reply.isError()||reply.value().isEmpty())return;
        m_accessibilityBus="ethershell-a11y-"+QString::number(QCoreApplication::applicationPid());
        auto bus=QDBusConnection::connectToBus(reply.value(),m_accessibilityBus);if(!bus.isConnected())return;
        if(!bus.connect(QString(),QString(),"org.a11y.atspi.Event.Object","StateChanged",this,SLOT(accessibleFocus(QDBusMessage))))return;
        auto call=QDBusMessage::createMethodCall("org.a11y.atspi.Registry","/org/a11y/atspi/registry","org.a11y.atspi.Registry","RegisterEvent");call<<"object:state-changed:focused"<<QStringList()<<QString();
        auto *registered=new QDBusPendingCallWatcher(bus.asyncCall(call,1000),this);
        connect(registered,&QDBusPendingCallWatcher::finished,this,[this,registered]{m_keyboardFocusAvailable=registered->reply().type()!=QDBusMessage::ErrorMessage;emit keyboardFocusChanged();registered->deleteLater();});
    });
}
void Core::accessibleFocus(const QDBusMessage &message){
    // Observe our editors directly. Qt's accessibility bridge uses a separate
    // bus connection and can report delayed focus on a surrounding container.
    if(QGuiApplication::focusWindow())return;
    if(message.arguments().size()<2||message.arguments()[0].toString()!="focused"||message.arguments()[1].toInt()!=1)return;
    const auto revision=++m_focusRevision;
    auto call=QDBusMessage::createMethodCall(message.service(),message.path(),"org.a11y.atspi.Accessible","GetInterfaces");
    auto *watcher=new QDBusPendingCallWatcher(QDBusConnection(m_accessibilityBus).asyncCall(call,500),this);
    connect(watcher,&QDBusPendingCallWatcher::finished,this,[this,watcher,revision]{QDBusPendingReply<QStringList> reply=*watcher;if(revision==m_focusRevision&&!QGuiApplication::focusWindow()&&!reply.isError())emit textInputFocus(reply.value().contains("org.a11y.atspi.EditableText"));watcher->deleteLater();});
}
Core::~Core(){if(m_restoreOnboard){auto show=QDBusMessage::createMethodCall("org.onboard.Onboard","/org/onboard/Onboard/Keyboard","org.onboard.Onboard.Keyboard","Show");QDBusConnection::sessionBus().call(show,QDBus::Block,500);}if(m_display){auto*d=static_cast<Display*>(m_display);if(m_injectionCode&&!m_originalMapping.isEmpty())XChangeKeyboardMapping(d,m_injectionCode,m_mappingWidth,m_originalMapping.data(),1);if(m_typing){XkbLockModifiers(d,XkbUseCoreKbd,0xff,m_previousLocked);XkbLatchModifiers(d,XkbUseCoreKbd,0xff,m_previousLatched);}XCloseDisplay(d);}if(!m_mappingJournal.isEmpty())QFile::remove(m_mappingJournal);}
void Core::status(const QString &s){m_message=s;emit messageChanged();}
void Core::nativeFrameTheme(bool desktop){if(qEnvironmentVariableIntValue("ETHERSHELL_NATIVE_FRAMES")!=1)return;QString theme="EtherSurface-"+QString(m_preferences["dark"].toBool()?"Dark":"Light")+(desktop?"-Desktop":"-Phone");if(theme==m_nativeFrameTheme)return;m_nativeFrameTheme=theme;run("xfconf-query",{"-c","xfwm4","-p","/general/theme","-s",theme});run("xfconf-query",{"-c","xfwm4","-p","/general/title_font","-s",desktop?"Sans Bold 10":"Sans Bold 13"});}
void Core::run(const QString &program,const QStringList &args,std::function<void(int,QString)> done,bool report) {
    auto *p=new QProcess(this); ++m_busy; emit messageChanged();
    p->setWorkingDirectory(QDir::homePath());
    auto launchEnvironment=QProcessEnvironment::systemEnvironment();
    launchEnvironment.remove("QT_ENABLE_HIGHDPI_SCALING");
    const QString locale=launchEnvironment.value("LC_ALL",launchEnvironment.value("LC_CTYPE",launchEnvironment.value("LANG")));
    if(locale.isEmpty()||locale=="C"||locale=="POSIX"){
        launchEnvironment.remove("LC_ALL");launchEnvironment.insert("LANG","C.UTF-8");launchEnvironment.insert("LC_CTYPE","C.UTF-8");
    }
    p->setProcessEnvironment(launchEnvironment);
    p->setProcessChannelMode(QProcess::MergedChannels);
    auto *deadline=new QTimer(p);deadline->setSingleShot(true);deadline->start(25000);
    connect(deadline,&QTimer::timeout,p,[p]{p->kill();});
    auto completed=std::make_shared<bool>(false);
    auto finish=[this,p,done,report,completed](int code){if(*completed)return;*completed=true;QString out=p->isOpen()?QString::fromUtf8(p->readAll()).trimmed():QString();--m_busy;if(report && code)status(out.isEmpty()?"Operacja niedostępna lub przekroczono czas.":out.left(400));emit messageChanged();if(done)done(code,out);p->deleteLater();};
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[finish](int c,QProcess::ExitStatus){finish(c);});
    connect(p,&QProcess::errorOccurred,this,[finish](QProcess::ProcessError e){if(e==QProcess::FailedToStart)finish(127);});
    if(program=="gio"&&args.size()==2&&args[0]=="launch"){
        QString path=QFileInfo(m_config).absolutePath()+"/profiles.json";if(!QFile::exists(path))path=qEnvironmentVariable("ETHERSHELL_PROFILE_DEFAULT","/usr/share/ethershell/profiles.json");
        const auto policy=QJsonDocument::fromJson(read(path).toUtf8()).object();auto env=launchEnvironment;
        for(const auto &entry:policy["profiles"].toArray()){
            auto profile=entry.toObject();if(profile["desktop"].toString()!=QFileInfo(args[1]).fileName())continue;
            auto overrides=profile["launchEnvironment"].toObject();
            for(auto it=overrides.begin();it!=overrides.end();++it){
                if(QStringList{"GDK_SCALE","GDK_DPI_SCALE","QT_SCALE_FACTOR"}.contains(it.key())){bool ok=false;double scale=it.value().toString().toDouble(&ok);if(ok&&scale>=.5&&scale<=4)env.insert(it.key(),it.value().toString());}
                else if(it.key()=="MOZ_USE_XINPUT2"&&it.value().toString()=="1")env.insert(it.key(),"1");
            }
        }
        p->setProcessEnvironment(env);
    }
    if(QStringList{"firefox-esr","xfce4-terminal","thunar","etherfiles","nm-connection-editor","pavucontrol","blueman-manager","xfce4-display-settings","xfce4-power-manager-settings","xfce4-session-settings"}.contains(program)){
        p->setProgram(program);p->setArguments(args);
        bool started=p->startDetached();finish(started?0:127);return;
    }
    p->start(program,args);
}
void Core::discover() {
    m_apps.clear(); QSet<QString> seen;
    QStringList roots={QDir::homePath()+"/.local/share/applications"};
    for(const auto &s:QStandardPaths::standardLocations(QStandardPaths::GenericDataLocation))if(!roots.contains(s+"/applications"))roots<<s+"/applications";
    for(const auto &root:roots){QDirIterator it(root,{"*.desktop"},QDir::Files,QDirIterator::Subdirectories);
        while(it.hasNext()){QString path=it.next(),id=QDir(root).relativeFilePath(path);id.replace('/','-');if(seen.contains(id))continue;seen.insert(id);
            const auto d=desktopEntry(path);
            if(d.value("Type").toString()!="Application"||d.value("Hidden",false).toBool()||d.value("NoDisplay",false).toBool())continue;
            const auto only=d.value("OnlyShowIn").toString();if(!only.isEmpty()&&!only.contains("XFCE")&&!only.contains("EtherShell"))continue;
            const QString tryExec=d.value("TryExec").toString();if(!tryExec.isEmpty()&&QStandardPaths::findExecutable(tryExec).isEmpty())continue;
            QString name=d.value("Name[pl]",d.value("Name")).toString();if(name.isEmpty()||id.startsWith("ethershell"))continue;
            m_apps<<QVariantMap{{"id",id},{"name",name},{"icon",d.value("Icon","application-x-executable")},{"path",path},{"category",d.value("Categories")}};
        }
    }
    std::sort(m_apps.begin(),m_apps.end(),[](const QVariant&a,const QVariant&b){return QString::localeAwareCompare(a.toMap()["name"].toString(),b.toMap()["name"].toString())<0;});
    if(!QFile::exists(m_config)){
        QStringList favorites;
        for(const QString &category:QStringList{"TerminalEmulator","FileManager","WebBrowser","TextEditor","Settings","Graphics","AudioVideo"}){
            for(const auto &v:m_apps){auto a=v.toMap();if(a["category"].toString().contains(category)&&!favorites.contains(a["id"].toString())){favorites<<a["id"].toString();break;}}
        }
        m_preferences["favorites"]=favorites;savePreferences();emit preferencesChanged();
    }
    emit appsChanged();
}
void Core::launch(const QString &id){for(const auto &v:m_apps){auto a=v.toMap();if(a["id"]==id){
    if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1&&id.contains("firefox")){QString profile=QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/ethershell/firefox-development";QDir().mkpath(profile);run("firefox-esr",{"--no-remote","--profile",profile,"--new-window","https://www.youtube.com"});}
    else run("gio",{"launch",a["path"].toString()});return;}}status("Aplikacja nie jest już dostępna. Odśwież listę.");}
void Core::windowAction(const QString &id,const QString &action){bool ok=false;id.toULongLong(&ok,16);if(!ok)return;if(action=="close")run("wmctrl",{"-ic",id});else if(action=="minimize")run("xdotool",{"windowminimize",id});else run("wmctrl",{"-ia",id});}
void Core::refresh(){
    if(m_preferences["themeMode"]=="auto"){bool dark=QTime::currentTime().hour()<7||QTime::currentTime().hour()>=19;if(dark!=m_preferences["dark"].toBool())setting("dark",dark);}
    if(m_refreshing)return;m_refreshing=true;readTelemetry();
    run("wmctrl",{"-lp"},[this](int,QString s){m_windows.clear();for(const auto &line:s.split('\n')){auto match=QRegularExpression("^(0x[0-9a-fA-F]+)\\s+(-?\\d+)\\s+(\\d+)\\s+\\S+\\s+(.*)$").match(line);if(match.hasMatch()&&match.captured(3).toLongLong()!=QCoreApplication::applicationPid()&&match.captured(2).toInt()>=0)m_windows<<QVariantMap{{"id",match.captured(1)},{"title",match.captured(4)},{"desktop",match.captured(2)}};}emit windowsChanged();m_refreshing=false;},false);
    run("nmcli",{"-t","--escape","no","-f","IN-USE,SSID,SIGNAL,SECURITY","device","wifi","list","--rescan","no"},[this](int,QString s){m_networks.clear();QSet<QString> seen;for(auto line:s.split('\n')){auto parts=line.split(':');if(parts.size()<4)continue;QString ssid=parts.mid(1,parts.size()-3).join(':');if(ssid.isEmpty()||seen.contains(ssid))continue;seen.insert(ssid);m_networks<<QVariantMap{{"active",parts[0]=="*"},{"ssid",ssid},{"signal",parts[parts.size()-2]},{"security",parts.last()}};}emit networksChanged();},false);
    run("xrandr",{"--query"},[this](int,QString s){m_displays.clear();for(auto line:s.split('\n')){auto m=QRegularExpression("^(\\S+) (connected|disconnected)(.*)$").match(line);if(m.hasMatch())m_displays<<QVariantMap{{"name",m.captured(1)},{"connected",m.captured(2)=="connected"},{"detail",m.captured(3)}};}emit displaysChanged();},false);
}
void Core::setPowerState(const QVariantMap &state){
    m_powerState=state;
    const bool saver=state.value("profileState").toMap().value("effective").toString()=="power-saver";
    if(m_timer.interval()!=(saver?30000:10000))m_timer.setInterval(saver?30000:10000);
    readTelemetry();
}
void Core::readTelemetry(){
    QVariantMap t;const QString base="/sys/class/power_supply/battery/";
    if(m_powerState.value("ready").toBool()){
        t["battery"]=m_powerState.value("capacity").isNull()?QString():QString::number(m_powerState.value("capacity").toDouble(),'f',0);
        t["charging"]=m_powerState.value("status");t["temperature"]=m_powerState.value("batteryTemperatureC").isNull()?QString():QString::number(m_powerState.value("batteryTemperatureC").toDouble(),'f',1);
    }else{
        t["battery"]=read(base+"capacity");t["charging"]=read(base+"status");
        QString temp=read(base+"temp");t["temperature"]=temp.isEmpty()?QString():QString::number(temp.toDouble()/10.,'f',1);
    }
    t["kernel"]=read("/proc/sys/kernel/osrelease");t["hostname"]=read("/proc/sys/kernel/hostname");
    t["memory"]=read("/proc/meminfo").section('\n',0,2);t["load"]=read("/proc/loadavg").section(' ',0,2);
    const auto adapters=m_bluetooth->adapters();
    t["bluetooth"]=!adapters.isEmpty();
    t["bluetoothPowered"]=!adapters.isEmpty()&&adapters.first().toMap().value("Powered").toBool();
    int connected=0;for(const auto &device:m_bluetooth->devices())if(device.toMap().value("Connected").toBool())++connected;
    t["bluetoothConnections"]=connected;
    auto backlights=QDir("/sys/class/backlight").entryList(QDir::Dirs|QDir::NoDotAndDotDot);
    // GM1920 also exposes an unused PMIC WLED named "backlight". The DSI
    // panel is controlled by panel0-backlight, regardless of directory order.
    if(backlights.removeOne("panel0-backlight"))backlights.prepend("panel0-backlight");
    for(const auto &device:backlights){
        QString base="/sys/class/backlight/"+device;int maximum=read(base+"/max_brightness").toInt();
        if(maximum>0){t["brightness"]=qRound(100.0*read(base+"/brightness").toInt()/maximum);t["brightnessWritable"]=QFileInfo(base+"/brightness").isWritable()||!m_brightnessSession.isEmpty();t["brightnessPath"]=base;break;}
    }
    m_telemetry=t;emit telemetryChanged();
}
void Core::setting(const QString &name,const QVariant &v){if(!m_preferences.contains(name)||name=="schema")return;
    if(name.startsWith("powerBrightness")&&v.toInt()!=-1&&(v.toInt()<1||v.toInt()>100))return;
    if(name.startsWith("mobile")&&v.toString().size()>100)return;
    if(name=="scale"&&(v.toDouble()<.8||v.toDouble()>1.5))return;
    if(name=="keyboardScale"&&(v.toDouble()<.85||v.toDouble()>1.2))return;
    if(name=="layout"&&v!="PL"&&v!="EN")return;
    if(name=="accent"&&!QColor(v.toString()).isValid())return;
    if(name=="themeMode"&&!QStringList{"light","dark","auto"}.contains(v.toString()))return;
    if(name=="transparency"&&(v.toDouble()<.65||v.toDouble()>1))return;
    if(name=="fontScale"&&(v.toDouble()<.8||v.toDouble()>1.5))return;
    if(name=="terminalFontSize"&&(v.toInt()<9||v.toInt()>28))return;
    if(name=="wallpaper"&&!v.toString().isEmpty()&&(!QFileInfo(v.toString()).isFile()||!QImageReader(v.toString()).canRead()))return;
    if(name=="dockOrder"){auto order=v.toStringList();if(order.size()!=6||QSet<QString>(order.begin(),order.end())!=QSet<QString>{"home","apps","tasks","keyboard","touchpad","settings"})return;}
    const auto previous=m_preferences.value(name);m_preferences[name]=v;
    if(!savePreferences()){m_preferences[name]=previous;emit preferencesChanged();return;}emit preferencesChanged();
    if(name=="themeMode"){bool dark=v=="dark"||(v=="auto"&&(QTime::currentTime().hour()<7||QTime::currentTime().hour()>=19));setting("dark",dark);}
    if(name=="dark"&&qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")!=1)run("ethershell-app-settings",{v.toBool()?"dark":"light"});
    if(name=="terminalFontSize")run("xfconf-query",{"-c","xfce4-terminal","-p","/font-name","-n","-t","string","-s","Monospace "+QString::number(v.toInt())});}
bool Core::savePreferences(){
    QDir().mkpath(QFileInfo(m_config).absolutePath());QSaveFile f(m_config);const auto requested=QJsonObject::fromVariantMap(m_preferences);
    const auto bytes=QJsonDocument(requested).toJson();
    if(!f.open(QIODevice::WriteOnly)||f.write(bytes)!=bytes.size()||!f.commit()||QJsonDocument::fromJson(read(m_config).toUtf8()).object()!=requested){status("Nie udało się zapisać i potwierdzić ustawień.");return false;}
    return true;
}
void Core::control(const QString &a,const QString &v){
    if(a=="scan")run("nmcli",{"device","wifi","rescan"},[this](int,QString){refresh();});
    else if(a=="wifi")run("nmcli",{"radio","wifi",v=="on"?"on":"off"},[this,v](int c,QString){if(c){status("Wi-Fi radio request failed.");return;}run("nmcli",{"-t","-f","WIFI","general"},[this,v](int c,QString out){m_settingsData["wifiRadio"]=c?"Unavailable":out;emit settingsDataChanged();status(!c&&out==(v=="on"?"enabled":"disabled")?"Wi-Fi radio applied and verified.":"Wi-Fi radio verification failed.");refresh();},false);},false);
    else if(a=="bluetooth")m_bluetooth->power(v=="on");
    else if(a=="bluetooth-settings")run("etherbluetooth",{});
    else if(a=="network-settings")run("nm-connection-editor",{});
    else if(a=="audio-settings")run("pavucontrol",{});
    else if(a=="volume")run("pactl",{"set-sink-volume","@DEFAULT_SINK@",QString::number(qBound(0,v.toInt(),100))+"%"});
    else if(a=="mute")run("pactl",{"set-sink-mute","@DEFAULT_SINK@","toggle"});
    else if(a=="display-settings")run("xfce4-display-settings",{});
    else if(a=="power-settings")run("xfce4-power-manager-settings",{});
    else if(a=="startup-settings")run("xfce4-session-settings",{});
    else if(a=="rotate"){QString output;for(auto item:m_displays){auto d=item.toMap();if(d["name"].toString().startsWith("DSI")&&d["connected"].toBool())output=d["name"].toString();}if(!output.isEmpty()&&QStringList{"normal","left","right","inverted"}.contains(v))run("etherair-x11",{"rotate","--output",output,"--touch","touchpanel","--rotation",v});}
    else if(a=="display-profile" && QStringList{"extend","mirror"}.contains(v))run("etherair-x11",{"display","--layout",v});
    else if(a=="distributor")QDesktopServices::openUrl(QUrl("https://autoupddate.etherneco.com/login"));
    else if(a=="workspace" && v.toInt()>=0&&v.toInt()<4)run("wmctrl",{"-s",v});
    else if(a=="terminal")run("xfce4-terminal",{});
    else if(a=="files")run(QStandardPaths::findExecutable("etherfiles").isEmpty()?"thunar":"etherfiles",{QDir::homePath()});
    else if(a=="brightness"){
        bool valid=false;int percent=v.toInt(&valid);
        const QString path=m_telemetry["brightnessPath"].toString();
        const int maximum=read(path+"/max_brightness").toInt();
        if(!valid||maximum<=0||!m_telemetry["brightnessWritable"].toBool()){status("Regulacja jasności jest niedostępna.");return;}
        // Keep the screen readable at the bottom of the slider. Power/blank
        // remains responsible for turning it completely black.
        const int level=qMax(1,qRound(qBound(1,percent,100)*maximum/100.0));
        bool applied=false;
        if(QFileInfo(path+"/brightness").isWritable()){
            QFile f(path+"/brightness");const auto bytes=QByteArray::number(level);
            applied=f.open(QIODevice::WriteOnly)&&f.write(bytes)==bytes.size();f.close();
        }else if(!m_brightnessSession.isEmpty()){
            auto set=QDBusMessage::createMethodCall("org.freedesktop.login1",m_brightnessSession,"org.freedesktop.login1.Session","SetBrightness");
            set<<QString("backlight")<<QFileInfo(path).fileName()<<quint32(level);
            auto *watch=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(set,3000),this);
            connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,path,level]{const bool accepted=watch->reply().type()==QDBusMessage::ReplyMessage;watch->deleteLater();readTelemetry();status(accepted&&read(path+"/brightness").toInt()==level?"Brightness applied and verified.":"Brightness verification failed.");});
            return;
        }
        if(!applied)status("Nie udało się zmienić jasności wyświetlacza.");
        readTelemetry();
    }
    else if(a=="lock")run("etherlock",{"lock"});
    else if(a=="quit")QGuiApplication::quit();
}
void Core::connectWifi(const QString &ssid,const QString &password){
    // Secrets are sent over stdin to nmcli, never put into argv or diagnostics.
    auto *p=new QProcess(this);p->setProcessChannelMode(QProcess::MergedChannels);
    auto *timer=new QTimer(p);timer->setSingleShot(true);timer->start(45000);connect(timer,&QTimer::timeout,p,[p]{p->kill();});
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p](int c,QProcess::ExitStatus){status(c?"Nie udało się połączyć z siecią. Sprawdź hasło i uprawnienia.":"Połączono z siecią.");p->deleteLater();refresh();});
    connect(p,&QProcess::errorOccurred,this,[this,p](QProcess::ProcessError e){if(e==QProcess::FailedToStart){status("NetworkManager jest niedostępny.");p->deleteLater();}});
    p->start("nmcli",{"--ask","--wait","35","device","wifi","connect",ssid});
    connect(p,&QProcess::started,p,[p,password]{p->write(password.toUtf8()+"\n");p->closeWriteChannel();});
}
void Core::key(const QString &symbol,bool ctrl,bool alt,bool shift,bool super,bool altgr){m_textQueue.enqueue({{},symbol,ctrl,alt,shift,super,altgr});sendNextText();}
void Core::injectKey(const QString &symbol,bool ctrl,bool alt,bool shift,bool super,bool altgr){auto *d=static_cast<Display*>(m_display);if(!d)return;
    KeySym sym=XStringToKeysym(symbol.toLatin1().constData());KeyCode code=XKeysymToKeycode(d,sym);if(!code)return;
    auto mod=[d](KeySym k,bool down){auto c=XKeysymToKeycode(d,k);if(c)XTestFakeKeyEvent(d,c,down,CurrentTime);};
    if(ctrl)mod(XK_Control_L,true);if(alt)mod(XK_Alt_L,true);if(shift)mod(XK_Shift_L,true);
    if(super)mod(XK_Super_L,true);if(altgr)mod(XK_ISO_Level3_Shift,true);
    XTestFakeKeyEvent(d,code,True,CurrentTime);XTestFakeKeyEvent(d,code,False,CurrentTime);
    if(altgr)mod(XK_ISO_Level3_Shift,false);if(super)mod(XK_Super_L,false);
    if(shift)mod(XK_Shift_L,false);if(alt)mod(XK_Alt_L,false);if(ctrl)mod(XK_Control_L,false);XFlush(d);
}
void Core::text(const QString &s){if(s.size()>128||s.isEmpty())return;m_textQueue.enqueue({s,{},false,false,false});sendNextText();}
void Core::sendNextText(){
    if(m_typing||m_textQueue.isEmpty())return;auto*d=static_cast<Display*>(m_display);if(!d)return;
    if(!m_textQueue.head().symbol.isEmpty()){auto event=m_textQueue.dequeue();injectKey(event.symbol,event.ctrl,event.alt,event.shift,event.super,event.altgr);QTimer::singleShot(0,this,[this]{sendNextText();});return;}
    if(!m_injectionCode){
        int low,high;XDisplayKeycodes(d,&low,&high);int width=0;KeySym *mapping=XGetKeyboardMapping(d,low,high-low+1,&width);
        for(int code=high;code>=low;--code){bool unused=true;for(int i=0;i<width;++i)if(mapping[(code-low)*width+i]!=NoSymbol)unused=false;
            if(unused){m_injectionCode=code;m_mappingWidth=width;for(int i=0;i<width;++i)m_originalMapping<<mapping[(code-low)*width+i];break;}}
        XFree(mapping);if(!m_injectionCode){m_textQueue.clear();status("Brak wolnego kodu X11 dla znaków Unicode.");return;}
        QString display=qEnvironmentVariable("DISPLAY");display.remove(':');display.replace('.','-');
        m_mappingJournal=QFileInfo(m_config).absolutePath()+"/input-map-"+display+".json";
        QVariantList original;for(auto value:m_originalMapping)original.append(qulonglong(value));
        QDir().mkpath(QFileInfo(m_mappingJournal).absolutePath());QSaveFile journal(m_mappingJournal);
        if(!journal.open(QIODevice::WriteOnly)){m_textQueue.clear();m_injectionCode=0;status("Cannot journal the temporary keyboard mapping.");return;}
        journal.write(QJsonDocument::fromVariant(QVariantMap{{"display",qEnvironmentVariable("DISPLAY")},{"code",m_injectionCode},{"width",m_mappingWidth},{"mapping",original}}).toJson());
        if(!journal.commit()){m_textQueue.clear();m_injectionCode=0;return;}

    }
    m_typing=true;QString s=m_textQueue.dequeue().text;const auto points=s.toUcs4();uint u=points.first();if(points.size()>1)m_textQueue.prepend({s.mid(u>0xffff?2:1),{},false,false,false});
    KeySym symbol=u<256?u:0x01000000|u;QVector<KeySym> map(m_mappingWidth,symbol);
    XkbStateRec old{};XkbGetState(d,XkbUseCoreKbd,&old);
    m_previousLocked=old.locked_mods;m_previousLatched=old.latched_mods;
    XkbLockModifiers(d,XkbUseCoreKbd,0xff,0);XkbLatchModifiers(d,XkbUseCoreKbd,0xff,0);
    XChangeKeyboardMapping(d,m_injectionCode,m_mappingWidth,map.data(),1);XSync(d,False);
    // Allow clients to consume MappingNotify before injecting the key, and
    // consume the key before restoring the mapping. No text is logged/stored.
    QTimer::singleShot(35,this,[this,d,old]{
        XTestFakeKeyEvent(d,m_injectionCode,True,CurrentTime);XTestFakeKeyEvent(d,m_injectionCode,False,CurrentTime);XSync(d,False);
        QTimer::singleShot(35,this,[this,d,old]{
            XChangeKeyboardMapping(d,m_injectionCode,m_mappingWidth,m_originalMapping.data(),1);
            XkbLockModifiers(d,XkbUseCoreKbd,0xff,old.locked_mods);XkbLatchModifiers(d,XkbUseCoreKbd,0xff,old.latched_mods);XFlush(d);
            m_typing=false;sendNextText();
        });
    });
}
void Core::pointer(int dx,int dy){auto*d=static_cast<Display*>(m_display);if(d){XTestFakeRelativeMotionEvent(d,dx,dy,CurrentTime);XFlush(d);}}
void Core::mouse(int button,bool down){auto*d=static_cast<Display*>(m_display);if(d&&button>=1&&button<=5){XTestFakeButtonEvent(d,button,down,CurrentTime);XFlush(d);}}
void Core::configureWindow(QObject *object,const QString &kind,int reserve){auto*d=static_cast<Display*>(m_display);auto*w=qobject_cast<QWindow*>(object);if(!d||!w)return;const auto id=w->winId();
    if(kind=="lock-home"){
        if(!w->isVisible())return;
        XRaiseWindow(d,id);
        XSetInputFocus(d,id,RevertToParent,CurrentTime);
        XGrabKeyboard(d,id,False,GrabModeAsync,GrabModeAsync,CurrentTime);
        XGrabPointer(d,id,False,ButtonPressMask|ButtonReleaseMask|PointerMotionMask,GrabModeAsync,GrabModeAsync,id,None,CurrentTime);
        XFlush(d);return;
    }
    if(kind=="unlock-home"){XUngrabKeyboard(d,CurrentTime);XUngrabPointer(d,CurrentTime);XFlush(d);return;}
    if(kind=="shape"){QPainterPath path;path.addRoundedRect(QRectF(0,0,w->width(),w->height()),reserve,reserve);w->setMask(QRegion(path.toFillPolygon().toPolygon()));return;}
    Atom type=XInternAtom(d,"_NET_WM_WINDOW_TYPE",False),value=XInternAtom(d,kind=="desktop"?"_NET_WM_WINDOW_TYPE_DESKTOP":"_NET_WM_WINDOW_TYPE_DOCK",False);
    XChangeProperty(d,id,type,XA_ATOM,32,PropModeReplace,reinterpret_cast<unsigned char*>(&value),1);
    if(kind=="home"){
        // Home fills the shell work area above application frames, without
        // reserving space or joining the WM's movable/Alt-Tab client list.
        XWMHints hints{};hints.flags=InputHint|WindowGroupHint;hints.input=True;hints.window_group=id;XSetWMHints(d,id,&hints);
    }
    if(kind=="keyboard"||kind=="dock"||kind=="top"){unsigned long strut[12]={0};
        // xfwm4 otherwise iconifies Qt's entire client-leader group with Home.
        XWMHints hints{};hints.flags=InputHint|WindowGroupHint;hints.input=False;hints.window_group=id;XSetWMHints(d,id,&hints);
        unsigned long desktop=0xffffffff;
        XChangeProperty(d,id,XInternAtom(d,"_NET_WM_DESKTOP",False),XA_CARDINAL,32,PropModeReplace,reinterpret_cast<unsigned char*>(&desktop),1);
        XEvent sticky{};sticky.xclient.type=ClientMessage;sticky.xclient.window=id;sticky.xclient.message_type=XInternAtom(d,"_NET_WM_DESKTOP",False);sticky.xclient.format=32;sticky.xclient.data.l[0]=desktop;sticky.xclient.data.l[1]=2;
        XSendEvent(d,DefaultRootWindow(d),False,SubstructureNotifyMask|SubstructureRedirectMask,&sticky);
        XWindowAttributes rootAttributes{};XGetWindowAttributes(d,DefaultRootWindow(d),&rootAttributes);
        if(reserve>0){if(kind=="top"){strut[2]=w->screen()->geometry().top()+reserve;strut[8]=std::max(0,w->screen()->geometry().left());strut[9]=w->screen()->geometry().right();}else {strut[3]=std::max(0,rootAttributes.height-(w->screen()->geometry().bottom()+1)+reserve);strut[10]=std::max(0,w->screen()->geometry().left());strut[11]=w->screen()->geometry().right();}}
        XChangeProperty(d,id,XInternAtom(d,"_NET_WM_STRUT_PARTIAL",False),XA_CARDINAL,32,PropModeReplace,reinterpret_cast<unsigned char*>(strut),12);
        XChangeProperty(d,id,XInternAtom(d,"_NET_WM_STRUT",False),XA_CARDINAL,32,PropModeReplace,reinterpret_cast<unsigned char*>(strut),4);}
    XFlush(d);
}
void Core::notify(const QString &title,const QString &body){
 auto msg=QDBusMessage::createMethodCall("org.freedesktop.Notifications","/org/freedesktop/Notifications","org.freedesktop.Notifications","Notify");
 msg.setArguments({QString("EtherShell"),uint(0),QString("dialog-information"),title,body,QStringList{},QVariantMap{{"x-ether-privacy","sensitive"}},-1});
 QDBusConnection::sessionBus().asyncCall(msg);
}
void Core::clearNotices(){auto msg=QDBusMessage::createMethodCall("com.etherneco.EtherNotifications1","/com/etherneco/EtherNotifications1","com.etherneco.EtherNotifications1","Command");msg.setArguments({QString("clear"),uint(0),QString("{}")});QDBusConnection::sessionBus().asyncCall(msg);}
void Core::activateNotice(uint id){auto msg=QDBusMessage::createMethodCall("com.etherneco.EtherNotifications1","/com/etherneco/EtherNotifications1","com.etherneco.EtherNotifications1","Command");msg.setArguments({QString("invoke"),id,QString("{\"key\":\"default\"}")});QDBusConnection::sessionBus().asyncCall(msg);}
void Core::diagnose(const QString &path){QSaveFile f(path);if(f.open(QIODevice::WriteOnly)){QVariantMap data{{"telemetry",m_telemetry},{"displays",m_displays},{"appCount",m_apps.size()},{"windows",m_windows}};f.write(QJsonDocument::fromVariant(data).toJson());f.commit();}}

void Core::updateSmsUnread(int count){m_smsUnread=qBound(0,count,9999);emit smsUnreadChanged();}
void Core::readSmsUnread(){
 auto message=QDBusMessage::createMethodCall("org.etherneco.EtherSMS","/org/etherneco/EtherSMS","org.etherneco.EtherSMS","GetUnread");
 auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message,1000),this);
 connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch]{QDBusPendingReply<int> reply=*watch;if(!reply.isError())updateSmsUnread(reply.value());watch->deleteLater();});
}
