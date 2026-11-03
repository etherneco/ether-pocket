#include <QGuiApplication>
#include <QQuickView>
#include <QQmlContext>
#include <QProcess>
#include <QSocketNotifier>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <QWindow>
#include <QFile>
#include <QMouseEvent>
#include <unistd.h>
#include <sys/resource.h>
#include <fcntl.h>
#include <X11/Xlib.h>
#include <X11/extensions/XInput2.h>
#undef Bool

class Authentication:public QObject {
    Q_OBJECT
    Q_PROPERTY(QString feedback READ feedback NOTIFY changed)
    Q_PROPERTY(bool waiting READ waiting NOTIFY changed)
public:
    QString feedback()const{return m_feedback;}
    bool waiting()const{return m_waiting;}
    bool authenticated()const{return m_authenticated;}
    Authentication() {
        m_timer.setSingleShot(true);m_timer.setInterval(60000);
        connect(&m_timer,&QTimer::timeout,this,[]{QCoreApplication::exit(1);});
        connect(&m_process,&QProcess::readyReadStandardOutput,this,[this]{
            m_buffer+=m_process.readAllStandardOutput();
            if(m_buffer.size()>8192){QCoreApplication::exit(1);return;}
            while(m_buffer.contains('\n')){
                int split=m_buffer.indexOf('\n');auto obj=QJsonDocument::fromJson(m_buffer.left(split)).object();m_buffer.remove(0,split+1);
                if(obj["event"]=="prompt"){m_waiting=true;m_feedback="Enter your Linux account credential";emit changed();}
                if(obj["event"]=="result")m_verified=obj["success"].toBool(false);
            }
        });
        connect(&m_process,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int code,QProcess::ExitStatus status){
            if(code==0&&status==QProcess::NormalExit&&m_verified){m_authenticated=true;QCoreApplication::exit(0);return;}
            m_waiting=false;m_feedback="Authentication failed. Repeated failures cause a temporary PAM lockout.";emit clearInput();emit changed();
        });
        connect(&m_process,&QProcess::errorOccurred,this,[this]{m_waiting=false;m_feedback="Authentication unavailable; use trusted recovery access";emit clearInput();emit changed();});
        m_timer.start();
    }
    ~Authentication(){if(m_process.state()!=QProcess::NotRunning){m_process.kill();m_process.waitForFinished(1000);}}
    Q_INVOKABLE void begin(){
        if(m_process.state()!=QProcess::NotRunning)return;
        m_verified=false;m_waiting=false;m_buffer.clear();m_feedback="Checking authentication policy…";emit changed();
        m_process.setProcessChannelMode(QProcess::SeparateChannels);
        m_process.start("/usr/lib/etherlock/etherlock-pam",{});m_timer.start();
    }
    Q_INVOKABLE void submit(const QString &response){
        if(!m_waiting||response.toUtf8().size()>1024)return;
        auto data=QJsonDocument(QJsonObject{{"response",response}}).toJson(QJsonDocument::Compact)+'\n';
        m_process.write(data);data.fill(0);m_waiting=false;m_feedback="Verifying…";emit clearInput();emit changed();m_timer.start();
    }
    Q_INVOKABLE void cancel(){QCoreApplication::exit(1);}
    void forwarded(const QByteArray &bytes){emit keyInput(QString::fromUtf8(bytes));}
signals:
    void changed();void clearInput();void keyInput(const QString &text);
private:
    QProcess m_process;QTimer m_timer;QByteArray m_buffer;QString m_feedback="Ready";bool m_waiting=false,m_verified=false,m_authenticated=false;
};
int main(int argc,char **argv){
    rlimit limit{0,0};setrlimit(RLIMIT_CORE,&limit);
    if(getuid()==0)return 2;
    bool ok=false;auto parentId=qEnvironmentVariable("XSCREENSAVER_WINDOW").toULongLong(&ok,0);
    if(!ok||!parentId)return 2; // Never pretend a standalone window is a locker.
    qputenv("QT_QPA_PLATFORM","xcb");qputenv("QT_QUICK_BACKEND","software");qputenv("QT_QUICK_CONTROLS_STYLE","Basic");
    QGuiApplication app(argc,argv);app.setQuitOnLastWindowClosed(false);Authentication auth;QQuickView view;
    auto parent=QWindow::fromWinId(parentId);if(!parent)return 2;
    view.setParent(parent);view.setFlags(Qt::FramelessWindowHint);view.setGeometry(0,0,parent->width(),parent->height());
    view.setResizeMode(QQuickView::SizeRootObjectToView);view.rootContext()->setContextProperty("Auth",&auth);
    view.setSource(QUrl("qrc:/Lock.qml"));if(view.status()==QQuickView::Error)return 2;
    QObject::connect(parent,&QWindow::widthChanged,&view,[&]{view.resize(parent->width(),parent->height());});
    QObject::connect(parent,&QWindow::heightChanged,&view,[&]{view.resize(parent->width(),parent->height());});
    fcntl(STDIN_FILENO,F_SETFL,O_NONBLOCK);QSocketNotifier input(STDIN_FILENO,QSocketNotifier::Read);
    QObject::connect(&input,&QSocketNotifier::activated,&auth,[&]{char data[256];auto n=read(0,data,sizeof(data));if(n>0)auth.forwarded(QByteArray(data,n));else if(n==0)app.exit(1);});
    view.show();
    // XSecureLock deliberately leaves this window unmapped: its auth module
    // must map it after painting. Mapping only our Qt child leaves it invisible.
    auto display=XOpenDisplay(nullptr);if(!display)return 2;
    XMapRaised(display,parentId);XSync(display,False);
    // The locker keeps the core pointer grab. Observe raw pointer events and
    // deliver them only inside this trusted child; never inject events into X11
    // or ungrab the protected session. This includes touch-to-pointer emulation.
    int opcode=0,eventBase=0,errorBase=0,major=2,minor=1;
    if(!XQueryExtension(display,"XInputExtension",&opcode,&eventBase,&errorBase)||XIQueryVersion(display,&major,&minor)!=Success)return 2;
    unsigned char bits[XIMaskLen(XI_RawMotion)]={};
    XISetMask(bits,XI_RawButtonPress);XISetMask(bits,XI_RawButtonRelease);XISetMask(bits,XI_RawMotion);
    XIEventMask mask{XIAllMasterDevices,sizeof(bits),bits};
    XISelectEvents(display,DefaultRootWindow(display),&mask,1);XFlush(display);
    bool pointerDown=false;
    QSocketNotifier pointer(ConnectionNumber(display),QSocketNotifier::Read);
    QObject::connect(&pointer,&QSocketNotifier::activated,&view,[&]{
        while(XPending(display)){
            XEvent event;XNextEvent(display,&event);
            if(event.type!=GenericEvent||event.xcookie.extension!=opcode||!XGetEventData(display,&event.xcookie))continue;
            auto raw=static_cast<XIRawEvent*>(event.xcookie.data);const int kind=event.xcookie.evtype;
            if(kind==XI_RawMotion||((kind==XI_RawButtonPress||kind==XI_RawButtonRelease)&&raw->detail==1)){
                ::Window unusedRoot,unusedChild;int rx,ry,wx,wy;unsigned int modifiers;
                if(XQueryPointer(display,DefaultRootWindow(display),&unusedRoot,&unusedChild,&rx,&ry,&wx,&wy,&modifiers)){
                    const QPoint global(qRound(rx/view.devicePixelRatio()),qRound(ry/view.devicePixelRatio()));
                    const auto local=view.mapFromGlobal(global);
                    if(kind==XI_RawButtonPress)pointerDown=true;
                    if(kind==XI_RawButtonRelease)pointerDown=false;
                    auto type=kind==XI_RawMotion?QEvent::MouseMove:kind==XI_RawButtonPress?QEvent::MouseButtonPress:QEvent::MouseButtonRelease;
                    QMouseEvent click(type,local,global,kind==XI_RawMotion?Qt::NoButton:Qt::LeftButton,pointerDown?Qt::LeftButton:Qt::NoButton,Qt::NoModifier);
                    click.setTimestamp(raw->time);QCoreApplication::sendEvent(&view,&click);
                }
            }
            XFreeEventData(display,&event.xcookie);
        }
    });
    QTimer::singleShot(0,&auth,&Authentication::begin);int result=app.exec();pointer.setEnabled(false);XCloseDisplay(display);view.setParent(nullptr);delete parent;return result==0&&auth.authenticated()?0:1;
}
#include "auth.moc"
