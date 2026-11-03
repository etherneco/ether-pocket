#include "media.h"
#include <QGuiApplication>
#include <QScreen>
#include <QPixmap>
#include <QPainter>
#include <QStandardPaths>
#include <QDirIterator>
#include <QImageReader>
#include <QSaveFile>
#include <QDateTime>
#include <QUuid>
#include <QUrl>
#include <QProcess>
#include <QSocketNotifier>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusVariant>
#include <QDBusReply>
#include <QDBusPendingCallWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QRegularExpression>
#include <QDebug>
#include <algorithm>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/XKBlib.h>
#include <X11/XF86keysym.h>
#include <X11/extensions/XInput2.h>
#include <X11/extensions/scrnsaver.h>
#include <X11/extensions/dpms.h>

static QDBusMessage powerProperty(const QString &method) {
    auto call=QDBusMessage::createMethodCall("org.xfce.Xfconf","/org/xfce/Xfconf","org.xfce.Xfconf",method);
    call<<"xfce4-power-manager"<<"/xfce4-power-manager/power-button-action";
    return call;
}

Media::Media(QObject *parent):QObject(parent) {
    // Nested development never grabs host side buttons or inhibits host power.
    if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){QTimer::singleShot(0,this,&Media::scan);return;}
    auto *d=XOpenDisplay(nullptr);m_display=d;
    if(d){
        // This downstream command-mode DSI panel can remain black after a
        // successful DPMS resume. Keep it powered and use X11's black saver
        // when the device launcher explicitly selects the workaround.
        m_softBlank=qEnvironmentVariableIntValue("ETHERSHELL_SOFT_BLANK")==1;
        if(m_softBlank){
            CARD16 level=DPMSModeOn;BOOL enabled=False;
            m_restoreDpms=DPMSInfo(d,&level,&enabled)&&enabled;
            if(enabled){DPMSForceLevel(d,DPMSModeOn);DPMSDisable(d);}
            XResetScreenSaver(d);
            // The built-in Xorg saver also calls xf86SaveScreen and powers
            // down this DSI output, even with DPMS disabled. Register a black
            // external saver window so blanking is purely a painted surface.
            XSetWindowAttributes attributes{};attributes.background_pixel=BlackPixel(d,DefaultScreen(d));
            attributes.override_redirect=True;
            XScreenSaverSetAttributes(d,DefaultRootWindow(d),0,0,
                DisplayWidth(d,DefaultScreen(d)),DisplayHeight(d,DefaultScreen(d)),
                0,CopyFromParent,InputOutput,nullptr,CWBackPixel|CWOverrideRedirect,&attributes);
            // Keep our own unmanaged cover above the shell's floating windows.
            // XFWM can reparent the server-owned saver window on this build.
            m_blankWindow=XCreateWindow(d,DefaultRootWindow(d),0,0,
                DisplayWidth(d,DefaultScreen(d)),DisplayHeight(d,DefaultScreen(d)),
                0,CopyFromParent,InputOutput,nullptr,CWBackPixel|CWOverrideRedirect,&attributes);
            XStoreName(d,m_blankWindow,"EtherShell Screen Blank");
            XFlush(d);
            qInfo()<<"Power policy: software blank; panel DPMS disabled";
        }
        int event,error,major=2,minor=2;
        if(XScreenSaverQueryExtension(d,&m_saverEvent,&error))
            XScreenSaverSelectInput(d,DefaultRootWindow(d),ScreenSaverNotifyMask);
        m_screenOff=screenOff();
        m_dpmsOff=m_screenOff;
        // Physical input can wake DPMS before XI2 reaches us. XScreenSaver
        // notifications alone do not reliably report DPMS-only blanking.
        // Keep the pre-input state and a short record of the wake transition.
        m_displayPoll.setInterval(100);
        connect(&m_displayPoll,&QTimer::timeout,this,[this,d]{
            const bool off=screenOff();
            if(m_dpmsOff&&!off)m_screenWake.start();
            const bool changed=m_dpmsOff!=off;m_dpmsOff=off;if(changed)emit powerStateChanged();
            syncBlankWindow(off);
            // DPMSInfo/XScreenSaverQueryInfo are synchronous Xlib calls.
            // They can read key events into Xlib's queue while waiting for a
            // reply, leaving the socket empty and QSocketNotifier silent.
            // Dispatch those events now instead of waiting for another key.
            const int queued=XEventsQueued(d,QueuedAlready);
            if(queued)qInfo()<<"Display poll: dispatching buffered X11 events"<<queued;
            events();
        });
        m_displayPoll.start();
        if(XQueryExtension(d,"XInputExtension",&m_opcode,&event,&error)&&XIQueryVersion(d,&major,&minor)==Success){
            m_up=XKeysymToKeycode(d,XF86XK_AudioRaiseVolume);
            m_down=XKeysymToKeycode(d,XF86XK_AudioLowerVolume);
            m_power=XKeysymToKeycode(d,XF86XK_PowerOff);
            unsigned char bits[XIMaskLen(XI_RawKeyRelease)]={};
            XISetMask(bits,XI_RawKeyPress);XISetMask(bits,XI_RawKeyRelease);
            XIEventMask mask{XIAllMasterDevices,sizeof(bits),bits};
            XISelectEvents(d,DefaultRootWindow(d),&mask,1);XFlush(d);
            // Consume volume keys so a focused player cannot apply the same step twice.
            auto oldHandler=XSetErrorHandler([](Display *,XErrorEvent *){return 0;});
            Bool detectable=False;XkbSetDetectableAutoRepeat(d,True,&detectable);
            for(int key:{m_up,m_down})if(key)XGrabKey(d,key,AnyModifier,DefaultRootWindow(d),False,GrabModeAsync,GrabModeAsync);
            XSync(d,False);XSetErrorHandler(oldHandler);
            auto *notifier=new QSocketNotifier(ConnectionNumber(d),QSocketNotifier::Read,this);
            connect(notifier,&QSocketNotifier::activated,this,[this]{events();});
        } else emit failed("Brak obsługi bocznych przycisków w XInput2.");
    }
    // Temporarily stop XFCE opening its power dialog during the chord.
    // Restore the exact previous action when EtherShell exits normally.
    auto bus=QDBusConnection::sessionBus();
    QDBusReply<QDBusVariant> old=bus.call(powerProperty("GetProperty"));
    if(old.isValid()){
        m_oldPowerAction=old.value().variant();
        auto set=powerProperty("SetProperty");set<<QVariant::fromValue(QDBusVariant(uint(0)));bus.call(set);
    }
    auto inhibit=QDBusMessage::createMethodCall("org.freedesktop.login1","/org/freedesktop/login1","org.freedesktop.login1.Manager","Inhibit");
    inhibit<<"handle-power-key"<<"EtherShell"<<"Power + Volume Down screenshot"<<"block";
    QDBusReply<QDBusUnixFileDescriptor> reply=QDBusConnection::systemBus().call(inhibit);
    if(reply.isValid())m_inhibitor=reply.value();
    m_defer.setSingleShot(true);m_defer.setInterval(180);
    connect(&m_defer,&QTimer::timeout,this,[this]{if(!m_combo&&!m_powerHeld){adjustVolume(m_upHeld?5:-5);m_repeat.start(400);}});
    connect(&m_repeat,&QTimer::timeout,this,[this]{if(!m_combo&&!m_powerHeld&&(m_upHeld||m_downHeld)){adjustVolume(m_upHeld?5:-5);m_repeat.setInterval(110);}});
    m_audioPoll.setInterval(5000);connect(&m_audioPoll,&QTimer::timeout,this,&Media::readVolume);m_audioPoll.start();readVolume();
    m_powerHold.setSingleShot(true);m_powerHold.setInterval(1500);
    connect(&m_powerHold,&QTimer::timeout,this,[this]{if(m_powerHeld&&!m_combo&&!m_wakePress){m_longPress=true;emit powerMenuRequested();}});
    QTimer::singleShot(0,this,&Media::scan);
}
Media::~Media(){
    if(m_oldPowerAction.isValid()){auto set=powerProperty("SetProperty");set<<QVariant::fromValue(QDBusVariant(m_oldPowerAction));QDBusConnection::sessionBus().call(set);}
    if(m_display){
        auto *d=static_cast<Display*>(m_display);
        if(m_originalTimeout>=0)XSetScreenSaver(d,m_originalTimeout,m_originalInterval,m_originalBlanking,m_originalExposures);
        if(m_softBlank){XResetScreenSaver(d);XScreenSaverUnsetAttributes(d,DefaultRootWindow(d));if(m_blankWindow)XDestroyWindow(d,m_blankWindow);if(m_restoreDpms)DPMSEnable(d);XFlush(d);}
        XCloseDisplay(d);
    }
}
void Media::events(){
    auto *d=static_cast<Display*>(m_display);
    while(XPending(d)){
        XEvent e;XNextEvent(d,&e);
        if(m_saverEvent&&e.type==m_saverEvent+ScreenSaverNotify){
            const auto *saver=reinterpret_cast<XScreenSaverNotifyEvent*>(&e);
            const bool off=saver->state==ScreenSaverOn||saver->state==ScreenSaverCycle;
            if(m_screenOff&&!off)m_screenWake.start();
            const bool changed=m_screenOff!=off;m_screenOff=off;if(changed)emit powerStateChanged();
            syncBlankWindow(off);
            continue;
        }
        if(e.type==KeyPress||e.type==KeyRelease){button(e.xkey.keycode,e.type==KeyPress);continue;}
        if(e.type!=GenericEvent||e.xcookie.extension!=m_opcode||!XGetEventData(d,&e.xcookie))continue;
        if(e.xcookie.evtype==XI_RawKeyPress||e.xcookie.evtype==XI_RawKeyRelease){
            auto *raw=static_cast<XIRawEvent*>(e.xcookie.data);
            if(!(raw->flags&XIKeyRepeat))button(raw->detail,e.xcookie.evtype==XI_RawKeyPress);
        }
        XFreeEventData(d,&e.xcookie);
    }
}
bool Media::screenOff() const {
    auto *d=static_cast<Display*>(m_display);
    if(!d)return false;
    CARD16 level=DPMSModeOn;BOOL enabled=False;
    const bool dpmsOff=DPMSInfo(d,&level,&enabled)&&enabled&&level!=DPMSModeOn;
    auto *info=XScreenSaverAllocInfo();
    const bool blank=info&&XScreenSaverQueryInfo(d,DefaultRootWindow(d),info)&&info->state==ScreenSaverOn;
    if(info)XFree(info);
    return dpmsOff||blank;
}
void Media::syncBlankWindow(bool off){
    if(!m_blankWindow)return;
    auto *d=static_cast<Display*>(m_display);
    if(off)XMapRaised(d,m_blankWindow);
    else XUnmapWindow(d,m_blankWindow);
    XFlush(d);
}
void Media::setPowerTimeout(int seconds,bool preserveExternal){
    if(!m_display||qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT")||!QList<int>{0,15,30,60,120,300}.contains(seconds))return;
    auto *d=static_cast<Display*>(m_display);m_preserveExternal=preserveExternal;
    m_requestedPowerTimeout=seconds;
    const int effective=m_secureLock|| (preserveExternal&&QGuiApplication::screens().size()>1)?0:seconds;
    if(effective==m_powerTimeout)return;
    if(m_originalTimeout<0)XGetScreenSaver(d,&m_originalTimeout,&m_originalInterval,&m_originalBlanking,&m_originalExposures);
    XSetScreenSaver(d,effective,m_originalInterval,m_originalBlanking,m_originalExposures);XFlush(d);
    int interval,blanking,exposures;XGetScreenSaver(d,&m_powerTimeout,&interval,&blanking,&exposures);
    if(m_powerTimeout!=effective)emit failed("Screen timeout readback did not match the requested policy.");emit powerStateChanged();
}
void Media::setSecureLockPolicy(bool enabled){
    if(m_secureLock==enabled)return;m_secureLock=enabled;setPowerTimeout(m_requestedPowerTimeout,m_preserveExternal);
}
void Media::setScreenBlank(bool blank){
    if(!m_display||qEnvironmentVariableIsSet("ETHERSHELL_DEVELOPMENT"))return;
    if(blank&&m_lockGuard&&!m_lockGuard()){emit failed("Screen off blocked: session lock not confirmed");return;}
    if(blank&&m_preserveExternal&&QGuiApplication::screens().size()>1){emit failed("External display session is active; whole-screen blanking is blocked by the preserve-session policy.");return;}
    auto *d=static_cast<Display*>(m_display);
    if(m_softBlank){if(blank)XForceScreenSaver(d,ScreenSaverActive);else XResetScreenSaver(d);}
    else if(blank)DPMSForceLevel(d,DPMSModeOff);
    else{XResetScreenSaver(d);DPMSForceLevel(d,DPMSModeOn);}
    m_dpmsOff=blank;syncBlankWindow(blank);XFlush(d);emit powerStateChanged();
}
void Media::button(int key,bool down){
    bool *held=key==m_up?&m_upHeld:key==m_down?&m_downHeld:key==m_power?&m_powerHeld:nullptr;
    if(held&&QGuiApplication::arguments().contains("--media-test"))qInfo()<<"Side key"<<key<<down<<"held"<<*held;
    if(!held||*held==down)return;
    *held=down;
    if(down){
        // Xorg may already have unblanked for this key before delivering XI2.
        // Remember that this press woke the screen, including idle DPMS blanking.
        if(key==m_power){m_wakePress=m_dpmsOff||m_screenOff||screenOff()||(m_screenWake.isValid()&&m_screenWake.elapsed()<500);m_longPress=false;m_powerHold.start();}
        if(key==m_power)qInfo()<<"Power press: cachedOff"<<m_dpmsOff<<"saverOff"<<m_screenOff<<"wake"<<m_wakePress;
        if(m_powerHeld&&m_downHeld&&!m_combo){m_combo=true;m_powerHold.stop();m_defer.stop();m_repeat.stop();screenshot();}
        else if(key!=m_power&&!m_combo&&!m_powerHeld){m_defer.start();}
    }else{
        if(key!=m_power){
            if(m_defer.isActive()&&!m_combo&&!m_powerHeld)adjustVolume(key==m_up?5:-5);
            m_defer.stop();m_repeat.stop();
        }else if(!m_combo&&!m_longPress){
            qInfo()<<"Power release:"<<(m_softBlank?"software":"DPMS")<<(m_wakePress?"on":"off")<<QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
            setScreenBlank(!m_wakePress);
        }
        if(key==m_power)m_powerHold.stop();
        // Keep the chord consumed until BOTH keys are released.
        if(!m_powerHeld&&!m_downHeld)m_combo=false;
    }
}
void Media::readVolume(){
    auto *p=new QProcess(this);
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p](int code,QProcess::ExitStatus){
        if(!code){
            auto match=QRegularExpression("(\\d+)%").match(QString::fromUtf8(p->readAllStandardOutput()));
            if(match.hasMatch()){m_volume=match.captured(1).toInt();emit volumeChanged();}
        }p->deleteLater();
    });
    connect(p,&QProcess::errorOccurred,p,[p](QProcess::ProcessError e){if(e==QProcess::FailedToStart)p->deleteLater();});
    auto env=QProcessEnvironment::systemEnvironment();env.insert("LC_ALL","C");p->setProcessEnvironment(env);
    p->start("pactl",{"get-sink-volume","@DEFAULT_SINK@"});
    auto *mute=new QProcess(this);mute->setProcessEnvironment(env);
    connect(mute,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,mute](int code,QProcess::ExitStatus){if(!code){m_muted=QString::fromUtf8(mute->readAllStandardOutput()).contains("yes");emit volumeChanged();}mute->deleteLater();});
    connect(mute,&QProcess::errorOccurred,mute,[mute](QProcess::ProcessError e){if(e==QProcess::FailedToStart)mute->deleteLater();});
    mute->start("pactl",{"get-sink-mute","@DEFAULT_SINK@"});
}
void Media::audioCommand(const QStringList &args){
    m_audioBusy=true;auto *p=new QProcess(this);
    auto finish=[this,p](bool ok){m_audioBusy=false;if(!ok)emit failed("Nie udało się zmienić głośności.");readVolume();emit volumeShown();p->deleteLater();if(m_pendingDelta){int delta=m_pendingDelta;m_pendingDelta=0;adjustVolume(delta);}};
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[finish](int code,QProcess::ExitStatus){finish(code==0);});
    connect(p,&QProcess::errorOccurred,this,[finish](QProcess::ProcessError e){if(e==QProcess::FailedToStart)finish(false);});
    p->start("pactl",args);
}
void Media::adjustVolume(int delta){
    if(m_audioBusy){m_pendingDelta+=delta;return;}
    if(qEnvironmentVariableIntValue("ETHERSHELL_DEVELOPMENT")==1){adjustMasterVolume(delta);return;}
    m_audioBusy=true;
    auto message=QDBusMessage::createMethodCall("com.etherneco.EtherAudio1","/com/etherneco/EtherAudio1","com.etherneco.EtherAudio1","AdjustVolume");message.setArguments({delta});
    auto *watch=new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(message,10000),this);
    connect(watch,&QDBusPendingCallWatcher::finished,this,[this,watch,delta]{
        auto reply=watch->reply();watch->deleteLater();m_audioBusy=false;
        if(reply.type()==QDBusMessage::ErrorMessage){
            if(reply.errorName()=="org.freedesktop.DBus.Error.ServiceUnknown"||reply.errorName()=="org.freedesktop.DBus.Error.NameHasNoOwner")adjustMasterVolume(delta);
            else emit failed(reply.errorMessage());
        }else{auto state=QJsonDocument::fromJson(reply.arguments().value(0).toString().toUtf8()).object();m_volume=state.value("percent").toInt();emit volumeChanged();emit volumeShown();}
        if(!m_audioBusy&&m_pendingDelta){auto pending=m_pendingDelta;m_pendingDelta=0;adjustVolume(pending);}
    });
}
void Media::adjustMasterVolume(int delta){
    if(m_audioBusy){m_pendingDelta+=delta;return;}
    // Query the current route before changing it; never amplify beyond 100%.
    m_audioBusy=true;auto *p=new QProcess(this);
    auto env=QProcessEnvironment::systemEnvironment();env.insert("LC_ALL","C");p->setProcessEnvironment(env);
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p,delta](int code,QProcess::ExitStatus){
        auto match=QRegularExpression("(\\d+)%").match(QString::fromUtf8(p->readAllStandardOutput()));p->deleteLater();
        if(code||!match.hasMatch()){m_audioBusy=false;emit failed("Brak dostępnego wyjścia dźwięku.");return;}
        audioCommand({"set-sink-volume","@DEFAULT_SINK@",QString::number(qBound(0,match.captured(1).toInt()+delta,100))+"%"});
    });
    connect(p,&QProcess::errorOccurred,this,[this,p](QProcess::ProcessError e){if(e==QProcess::FailedToStart){m_audioBusy=false;p->deleteLater();emit failed("Nie znaleziono pactl.");}});
    p->start("pactl",{"get-sink-volume","@DEFAULT_SINK@"});
}
void Media::setVolume(int value){audioCommand({"set-sink-volume","@DEFAULT_SINK@",QString::number(qBound(0,value,100))+"%"});}
void Media::toggleMute(){audioCommand({"set-sink-mute","@DEFAULT_SINK@","toggle"});}
void Media::scan(){
    const auto pictures=QStandardPaths::writableLocation(QStandardPaths::PicturesLocation);
    if(pictures.isEmpty())return;
    QDir().mkpath(pictures+"/Screenshots");
    QFileInfoList files;QDirIterator it(pictures,QDir::Files|QDir::Readable,QDirIterator::Subdirectories);
    const auto formats=QImageReader::supportedImageFormats();
    while(it.hasNext()){it.next();if(formats.contains(it.fileInfo().suffix().toLower().toLatin1()))files<<it.fileInfo();}
    std::sort(files.begin(),files.end(),[](const QFileInfo &a,const QFileInfo &b){return a.lastModified()>b.lastModified();});
    m_images.clear();
    for(const auto &file:files)m_images<<QVariantMap{{"name",file.fileName()},{"url",QUrl::fromLocalFile(file.absoluteFilePath())},{"path",file.absoluteFilePath()},{"date",file.lastModified().toString("dd.MM.yyyy HH:mm")},{"screenshot",file.absoluteFilePath().startsWith(pictures+"/Screenshots/")}};
    emit imagesChanged();
}
void Media::screenshot(){
    if(m_saving)return;m_saving=true;
    emit capturing();
    // Give the compositor a frame to remove our previous toast/flash.
    QTimer::singleShot(80,this,&Media::captureScreen);
}
void Media::captureScreen(){
    // Grab the X11 ROOT, not the EtherShell window: includes other apps and dock.
    auto *d=static_cast<Display*>(m_display);XWindowAttributes attributes{};
    const auto root=d?DefaultRootWindow(d):0;
    QImage shot;
    if(d&&XGetWindowAttributes(d,root,&attributes)){
        auto *native=XGetImage(d,root,0,0,attributes.width,attributes.height,AllPlanes,ZPixmap);
        if(native){
            if(native->bits_per_pixel==32&&native->red_mask==0xff0000&&native->green_mask==0xff00&&native->blue_mask==0xff&&native->byte_order==LSBFirst)
                shot=QImage(reinterpret_cast<uchar*>(native->data),native->width,native->height,native->bytes_per_line,QImage::Format_RGB32).copy();
            else{
                shot=QImage(native->width,native->height,QImage::Format_RGB32);
                auto channel=[](unsigned long pixel,unsigned long mask){if(!mask)return 0UL;while(!(mask&1)){mask>>=1;pixel>>=1;}return (pixel&mask)*255/mask;};
                for(int y=0;y<native->height;++y)for(int x=0;x<native->width;++x){auto pixel=XGetPixel(native,x,y);shot.setPixel(x,y,qRgb(channel(pixel,native->red_mask),channel(pixel,native->green_mask),channel(pixel,native->blue_mask)));}
            }
            XDestroyImage(native);
        }
    }
    if(shot.isNull()){m_saving=false;emit failed("Nie udało się przechwycić całego ekranu.");return;}
    QString dir=QStandardPaths::writableLocation(QStandardPaths::PicturesLocation)+"/Screenshots";
    if(!QDir().mkpath(dir)){m_saving=false;emit failed("Nie udało się utworzyć folderu zrzutów.");return;}
    const QString path=dir+"/Screenshot-"+QDateTime::currentDateTime().toString("yyyyMMdd-HHmmss-zzz")+"-"+QUuid::createUuid().toString(QUuid::Id128).left(8)+".png";
    QSaveFile file(path);
    if(!file.open(QIODevice::WriteOnly)||!shot.save(&file,"PNG")||!file.commit()){m_saving=false;emit failed("Nie udało się zapisać zrzutu ekranu.");return;}
    // Feedback is emitted only after a successful atomic save, outside the captured frame.
    emit saved(path);
    QProcess::startDetached("paplay",{"/usr/share/sounds/freedesktop/stereo/camera-shutter.oga"});
    scan();QTimer::singleShot(500,this,[this]{m_saving=false;});
}
