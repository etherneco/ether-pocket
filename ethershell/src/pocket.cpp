#include "pocket.h"
#include <QGuiApplication>
#include <QScreen>
#include <QFile>
#include <QDir>
#include <QStandardPaths>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QCoreApplication>
#include <QSocketNotifier>
#include <QWindow>
#include <QPainterPath>
#include <QRegion>
#include <QJsonArray>
#include <QDateTime>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/Xutil.h>
#include <X11/extensions/shape.h>
#include <X11/extensions/Xcomposite.h>
#include <algorithm>

namespace {
int ignoreXError(Display *, XErrorEvent *) { return 0; } // Clients can disappear between requests.
QVector<unsigned long> prop(Display *d,Window w,const char *name,Atom wanted=XA_CARDINAL) {
    Atom actual;int format;unsigned long count,remaining;unsigned char *data=nullptr;
    QVector<unsigned long> out;
    if(XGetWindowProperty(d,w,XInternAtom(d,name,False),0,4096,False,wanted,&actual,&format,&count,&remaining,&data)==Success && data && format==32)
        for(unsigned long i=0;i<count;++i)out.append(reinterpret_cast<unsigned long*>(data)[i]);
    if(data)XFree(data);return out;
}
QString klass(Display *d,Window w) {XClassHint hint{};QString s;if(XGetClassHint(d,w,&hint)){s=QString::fromLocal8Bit(hint.res_class).toLower();if(hint.res_name)XFree(hint.res_name);if(hint.res_class)XFree(hint.res_class);}return s;}
QString title(Display *d,Window w) {Atom actual;int format;unsigned long n,left;unsigned char *data=nullptr;QString s;if(XGetWindowProperty(d,w,XInternAtom(d,"_NET_WM_NAME",False),0,512,False,AnyPropertyType,&actual,&format,&n,&left,&data)==Success&&data&&format==8)s=QString::fromUtf8(reinterpret_cast<char*>(data),n);if(data)XFree(data);if(s.isEmpty()){char*name=nullptr;if(XFetchName(d,w,&name)&&name)s=QString::fromLocal8Bit(name);if(name)XFree(name);}return s;}
QRect geometry(Display *d,Window w) {XWindowAttributes a{};int x=0,y=0;Window child;if(!XGetWindowAttributes(d,w,&a))return {};XTranslateCoordinates(d,w,DefaultRootWindow(d),0,0,&x,&y,&child);return {x,y,a.width,a.height};}
}
Pocket::Pocket(QObject *parent):QObject(parent) {
    const QString config=qEnvironmentVariable("ETHERSHELL_CONFIG_DIR",QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/ethershell");
    m_surface=qEnvironmentVariableIntValue("ETHERSHELL_EXPERIENCE")==1;
    m_nativeFrames=qEnvironmentVariableIntValue("ETHERSHELL_NATIVE_FRAMES")==1;
    m_safe=QCoreApplication::arguments().contains("--safe-mode") || qEnvironmentVariableIntValue("ETHERSHELL_SAFE_MODE")==1 || (!QCoreApplication::arguments().contains("--enable-surface")&&QFile::exists(config+"/safe-mode"));
    QFile f(config+"/profiles.json");
    if(!f.exists())f.setFileName(qEnvironmentVariable("ETHERSHELL_PROFILE_DEFAULT","/usr/share/ethershell/profiles.json"));
    if(f.open(QIODevice::ReadOnly)){auto doc=QJsonDocument::fromJson(f.readAll());if(doc.isObject()&&doc.object()["schema"].toInt()==1)m_config=doc.object().toVariantMap();else m_safe=true;}
    else m_safe=true; // Missing/invalid policies fail open to the existing desktop.
    for(const auto &entry:m_config["profiles"].toList()){
        const auto p=entry.toMap();if(p["name"].toString().isEmpty()||p["classes"].toStringList().isEmpty()||!QStringList{"free","maximize","fit","fullscreen","split-top","split-bottom"}.contains(p.value("geometry","maximize").toString()))m_safe=true;
    }
    const auto zones=m_config["gestures"].toMap();
    m_gestureStart=qBound(0.,zones.value("start",.08).toDouble(),1.);
    m_gestureEnd=qBound(m_gestureStart,zones.value("end",.92).toDouble(),1.);
    XSetErrorHandler(ignoreXError);
    m_display=XOpenDisplay(nullptr);
    if(auto*d=static_cast<Display*>(m_display)){
        int opcode,event,error;m_shape=XShapeQueryExtension(d,&event,&error);
        for(const auto *name:{"Composite","DAMAGE","XFIXES","SHAPE","RANDR","XInputExtension"})m_capabilities[name]=bool(XQueryExtension(d,name,&opcode,&event,&error));
        m_capabilities["compositor"]=bool(XGetSelectionOwner(d,XInternAtom(d,"_NET_WM_CM_S0",False)));
        XSelectInput(d,DefaultRootWindow(d),PropertyChangeMask|SubstructureNotifyMask);
        m_debounce.setSingleShot(true);m_debounce.setInterval(45);connect(&m_debounce,&QTimer::timeout,this,&Pocket::scan);
        auto *notifier=new QSocketNotifier(ConnectionNumber(d),QSocketNotifier::Read,this);
        connect(notifier,&QSocketNotifier::activated,this,[this,d]{bool relevant=false;while(XPending(d)){XEvent event;XNextEvent(d,&event);if(event.type==PropertyNotify||event.type==MapNotify||event.type==UnmapNotify||event.type==DestroyNotify||event.type==ConfigureNotify)relevant=true;}if(relevant&&!m_debounce.isActive())m_debounce.start();});
    }
    QString display=qEnvironmentVariable("DISPLAY");display.remove(':');display.replace('.','-');
    m_recoveryFile=config+"/surface-state-"+display+".json";
    m_timer.setInterval(2000);connect(&m_timer,&QTimer::timeout,this,&Pocket::scan);m_timer.start();
    QTimer::singleShot(1000,this,&Pocket::scan);
}
Pocket::~Pocket(){restore();if(m_display)XCloseDisplay(static_cast<Display*>(m_display));}
QRect Pocket::phone() const {for(auto*s:QGuiApplication::screens())if(s->name().startsWith("DSI")||s->name().startsWith("eDP"))return s->geometry();return QGuiApplication::primaryScreen()->geometry();}
QVariantMap Pocket::profile(const QString &wmClass) const {
    for(const auto &v:m_config["profiles"].toList()){auto p=v.toMap();for(const auto &c:p["classes"].toStringList())if(c.compare(wmClass,Qt::CaseInsensitive)==0)return p;}
    return m_config["generic"].toMap();
}
QVariantMap Pocket::activeWindow() const {for(auto item:m_windows)if(item.toMap()["id"].toString()==activeId())return item.toMap();return {};}
QStringList Pocket::windowIds() const {QStringList ids;for(const auto &item:m_windows)if(!item.toMap()["dialog"].toBool())ids.append(item.toMap()["id"].toString());return ids;}
void Pocket::releasePreviews(){if(auto*d=static_cast<Display*>(m_display)){for(auto w:m_redirected)XCompositeUnredirectWindow(d,w,CompositeRedirectAutomatic);XFlush(d);}m_redirected.clear();}
void Pocket::presentation(int margin,int radius,bool previews,bool lowPower){m_previews=previews&&!lowPower;if(!m_previews)releasePreviews();int nextMargin=qBound(0,margin,100),nextRadius=lowPower?0:qBound(0,radius,100);if(m_margin==nextMargin&&m_radius==nextRadius)return;m_margin=nextMargin;m_radius=nextRadius;for(auto it=m_saved.begin();it!=m_saved.end();++it)it->signature.clear();m_debounce.start();}
void Pocket::decorate(unsigned long w,Saved &s,const QSize &size,bool fullscreen){
    if(!m_surface)return;auto*d=static_cast<Display*>(m_display);
    if(!s.styled){s.motif=prop(d,w,"_MOTIF_WM_HINTS",AnyPropertyType);Bool shaped=False,clip=False;int x,y,cx,cy;unsigned int width,height,cw,ch;if(m_shape)XShapeQueryExtents(d,w,&shaped,&x,&y,&width,&height,&clip,&cx,&cy,&cw,&ch);s.originalShaped=shaped;
        s.styled=true;persist(); // Journal the original before changing a client.
        unsigned long hints[5]={2,0,m_nativeFrames?1UL:0UL,0,0};Atom motif=XInternAtom(d,"_MOTIF_WM_HINTS",False);XChangeProperty(d,w,motif,motif,32,PropModeReplace,reinterpret_cast<unsigned char*>(hints),5);
    }
    if(m_nativeFrames)return; // The WM owns the complete frame, shape and resize input.
    if(!m_shape||s.originalShaped)return;int radius=fullscreen?0:std::min({m_radius,size.width()/4,size.height()/4});if(s.shapeSize==size&&s.shapeRadius==radius)return;
    if(!radius)XShapeCombineMask(d,w,ShapeBounding,0,0,0,ShapeSet);
    else {QPainterPath path;path.addRoundedRect(QRectF(QPointF(0,0),QSizeF(size)),radius,radius);QRegion region(path.toFillPolygon().toPolygon());QVector<XRectangle> rects;for(auto r:region)rects.append(XRectangle{short(r.x()),short(r.y()),ushort(r.width()),ushort(r.height())});XShapeCombineRectangles(d,w,ShapeBounding,0,0,rects.data(),rects.size(),ShapeSet,Unsorted);}
    s.shapeSize=size;s.shapeRadius=radius;s.shapeApplied=true;XFlush(d);
}
void Pocket::restoreDecoration(unsigned long w,const Saved &s){if(!s.styled)return;auto*d=static_cast<Display*>(m_display);Atom motif=XInternAtom(d,"_MOTIF_WM_HINTS",False);if(s.motif.isEmpty())XDeleteProperty(d,w,motif);else XChangeProperty(d,w,motif,motif,32,PropModeReplace,reinterpret_cast<const unsigned char*>(s.motif.data()),s.motif.size());if(s.shapeApplied&&!s.originalShaped)XShapeCombineMask(d,w,ShapeBounding,0,0,0,ShapeSet);}
void Pocket::persist(){if(!m_surface)return;QVariantList entries;for(auto it=m_saved.begin();it!=m_saved.end();++it){auto s=it.value();QVariantList motif;for(auto value:s.motif)motif.append(qulonglong(value));entries.append(QVariantMap{{"id",QString("0x%1").arg(it.key(),0,16)},{"identity",s.identity},{"styled",s.styled},{"motif",motif},{"resetShape",s.styled&&!s.originalShaped},{"geometry",QVariantList{s.geometry.x(),s.geometry.y(),s.geometry.width(),s.geometry.height()}},{"maxH",s.maxH},{"maxV",s.maxV},{"fullscreen",s.fullscreen}});}
    QDir().mkpath(QFileInfo(m_recoveryFile).absolutePath());QSaveFile f(m_recoveryFile);if(f.open(QIODevice::WriteOnly)){f.write(QJsonDocument::fromVariant(QVariantMap{{"schema",1},{"display",qEnvironmentVariable("DISPLAY")},{"shellPid",QCoreApplication::applicationPid()},{"windows",entries}}).toJson());f.commit();QFile::setPermissions(m_recoveryFile,QFile::ReadOwner|QFile::WriteOwner);}}
void Pocket::bindHeader(QObject *object,const QString &id){auto*d=static_cast<Display*>(m_display);auto*w=qobject_cast<QWindow*>(object);if(!d||!w)return;XSetTransientForHint(d,w->winId(),id.toULong(nullptr,16));XWMHints hints{};hints.flags=InputHint|WindowGroupHint;hints.input=False;hints.window_group=w->winId();XSetWMHints(d,w->winId(),&hints);XFlush(d);}
void Pocket::moveBy(const QString &id,int dx,int dy){auto*d=static_cast<Display*>(m_display);if(!d)return;auto w=id.toULong(nullptr,16);if(!m_saved.contains(w))return;QRect g=geometry(d,w);g.translate(qBound(-300,dx,300),qBound(-300,dy,300));QRect monitor=phone();for(auto*s:QGuiApplication::screens())if(s->geometry().contains(g.center()))monitor=s->geometry();QRect screen=usable(monitor);int header=qRound(60*(monitor==phone()?std::max(1.,m_margin/8.):1.));g.moveLeft(qBound(screen.left()-g.width()+80,g.left(),screen.right()-80));g.moveTop(qBound(screen.top()+header,g.top(),std::max(screen.top()+header,screen.bottom()-80)));m_saved[w].policy="free";fit(w,g);}
void Pocket::resizeBy(const QString &id,int dx,int dy){auto*d=static_cast<Display*>(m_display);if(!d)return;auto w=id.toULong(nullptr,16);if(!m_saved.contains(w))return;QRect g=geometry(d,w);g.setSize(QSize(qBound(220,g.width()+dx,3840),qBound(160,g.height()+dy,2160)));m_saved[w].policy="free";fit(w,g);}
void Pocket::resizeTo(const QString &id,int width,int height){auto*d=static_cast<Display*>(m_display);if(!d)return;auto w=id.toULong(nullptr,16);if(!m_saved.contains(w))return;QRect g=geometry(d,w);g.setSize(QSize(qBound(220,width,3840),qBound(160,height,3120)));m_saved[w].policy="free";fit(w,g);}
QImage Pocket::preview(const QString &id,int width){
    auto*d=static_cast<Display*>(m_display);if(!d||!m_previews||!m_capabilities["Composite"].toBool())return {};
    m_capabilities["compositor"]=bool(XGetSelectionOwner(d,XInternAtom(d,"_NET_WM_CM_S0",False)));if(!m_capabilities["compositor"].toBool())return {};
    Window w=id.toULong(nullptr,16);bool known=false;for(auto item:m_windows)if(item.toMap()["id"].toString()==id)known=true;if(!known)return {};
    XWindowAttributes a{};if(!XGetWindowAttributes(d,w,&a)||a.map_state!=IsViewable||a.width>4096||a.height>4096)return {};
    // The WM redirects its frame windows; clients may be grandchildren rather
    // than directly redirected. Automatic redirection is reference-counted and
    // does not claim the compositor selection or the WM's manual redirection.
    if(!m_redirected.contains(w)){XCompositeRedirectWindow(d,w,CompositeRedirectAutomatic);XSync(d,False);m_redirected.insert(w);}
    Pixmap pix=XCompositeNameWindowPixmap(d,w);XSync(d,False);if(!pix)return {};Window root;int x,y;unsigned int pw,ph,border,depth;if(!XGetGeometry(d,pix,&root,&x,&y,&pw,&ph,&border,&depth)||pw>4096||ph>4096){XFreePixmap(d,pix);return {};}
    auto *raw=XGetImage(d,pix,0,0,pw,ph,AllPlanes,ZPixmap);XFreePixmap(d,pix);if(!raw)return {};if(!raw->red_mask){raw->red_mask=a.visual->red_mask;raw->green_mask=a.visual->green_mask;raw->blue_mask=a.visual->blue_mask;}QImage out(std::min(width,int(pw)),std::max(1,int(ph)*std::min(width,int(pw))/int(pw)),QImage::Format_RGB32);
    auto component=[](unsigned long pixel,unsigned long mask){if(!mask)return 0;int shift=0;while(!(mask&1)){mask>>=1;++shift;}return int(((pixel>>shift)&mask)*255/mask);};
    for(int yy=0;yy<out.height();++yy){auto *line=reinterpret_cast<QRgb*>(out.scanLine(yy));for(int xx=0;xx<out.width();++xx){auto pixel=XGetPixel(raw,xx*pw/out.width(),yy*ph/out.height());line[xx]=qRgb(component(pixel,raw->red_mask),component(pixel,raw->green_mask),component(pixel,raw->blue_mask));}}
    XDestroyImage(raw);return out;
}
void Pocket::send(unsigned long w,const char *type,long a,long b,long c,long v,long e){auto*d=static_cast<Display*>(m_display);if(!d)return;XEvent ev{};ev.xclient.type=ClientMessage;ev.xclient.window=w;ev.xclient.message_type=XInternAtom(d,type,False);ev.xclient.format=32;ev.xclient.data.l[0]=a;ev.xclient.data.l[1]=b;ev.xclient.data.l[2]=c;ev.xclient.data.l[3]=v;ev.xclient.data.l[4]=e;XSendEvent(d,DefaultRootWindow(d),False,SubstructureNotifyMask|SubstructureRedirectMask,&ev);XFlush(d);}
void Pocket::state(unsigned long w,const char *name,bool on,const char *second){auto*d=static_cast<Display*>(m_display);send(w,"_NET_WM_STATE",on?1:0,XInternAtom(d,name,False),second?XInternAtom(d,second,False):0,2);}
void Pocket::fit(unsigned long w,const QRect &r){auto*d=static_cast<Display*>(m_display);auto ex=prop(d,w,"_NET_FRAME_EXTENTS");int l=0,t=0,right=0,b=0;if(ex.size()==4){l=ex[0];right=ex[1];t=ex[2];b=ex[3];}send(w,"_NET_MOVERESIZE_WINDOW",StaticGravity|(15<<8)|(2<<12),r.x()+l,r.y()+t,std::max(100,r.width()-l-right),std::max(100,r.height()-t-b));}
QRect Pocket::usable(const QRect &screen) const {
    auto*d=static_cast<Display*>(m_display);auto root=DefaultRootWindow(d);QRect r=screen;
    // Read each visible panel's partial strut, not the global workarea. Global
    // workareas can incorrectly reserve the phone keyboard on an AR output.
    XWindowAttributes rootAttributes{};XGetWindowAttributes(d,root,&rootAttributes);
    const int width=rootAttributes.width,height=rootAttributes.height;
    for(auto w:prop(d,root,"_NET_CLIENT_LIST",XA_WINDOW)){
        XWindowAttributes a{};if(!XGetWindowAttributes(d,w,&a)||a.map_state!=IsViewable)continue;
        auto s=prop(d,w,"_NET_WM_STRUT_PARTIAL");if(s.size()!=12)continue;
        if(s[0]&&int(s[4])<=screen.bottom()&&int(s[5])>=screen.top())r.setLeft(std::max(r.left(),int(s[0])));
        if(s[1]&&int(s[6])<=screen.bottom()&&int(s[7])>=screen.top())r.setRight(std::min(r.right(),width-int(s[1])-1));
        if(s[2]&&int(s[8])<=screen.right()&&int(s[9])>=screen.left())r.setTop(std::max(r.top(),int(s[2])));
        if(s[3]&&int(s[10])<=screen.right()&&int(s[11])>=screen.left())r.setBottom(std::min(r.bottom(),height-int(s[3])-1));
    }
    return r.width()>100&&r.height()>100?r:screen;
}
void Pocket::scan(){
    auto*d=static_cast<Display*>(m_display);if(!d)return;auto root=DefaultRootWindow(d);auto clients=prop(d,root,"_NET_CLIENT_LIST",XA_WINDOW);auto active=prop(d,root,"_NET_ACTIVE_WINDOW",XA_WINDOW);
    QRect panel=phone();bool desktopOnly=qEnvironmentVariableIntValue("ETHERSHELL_DESKTOP_TEST")==1;m_external=desktopOnly;for(auto*s:QGuiApplication::screens())if(s->geometry()!=panel)m_external=true;
    const QRect phoneArea=usable(panel).adjusted(m_surface?m_margin:0,m_surface?m_margin:0,m_surface?-m_margin:0,m_surface?-m_margin:0);
    bool keyboard=false;for(auto w:clients)if(title(d,w)=="EtherKeyboard"){XWindowAttributes a{};if(XGetWindowAttributes(d,w,&a)&&a.map_state==IsViewable)keyboard=true;}
    QVariantList windows;
    for(auto w:clients){
        QString cl=klass(d,w);auto pid=prop(d,w,"_NET_WM_PID");if(cl=="ethershell"||(!pid.isEmpty()&&pid[0]==unsigned(QCoreApplication::applicationPid())))continue;
        auto types=prop(d,w,"_NET_WM_WINDOW_TYPE",XA_ATOM);Window parent=0;XGetTransientForHint(d,w,&parent);
        bool dialog=parent||types.contains(XInternAtom(d,"_NET_WM_WINDOW_TYPE_DIALOG",False));
        bool normal=types.isEmpty()||types.contains(XInternAtom(d,"_NET_WM_WINDOW_TYPE_NORMAL",False));
        if(!normal&&!dialog)continue;
        auto states=prop(d,w,"_NET_WM_STATE",XA_ATOM);
        if(states.contains(XInternAtom(d,"_NET_WM_STATE_SKIP_TASKBAR",False))&&!dialog)continue;
        QRect g=geometry(d,w);if(!g.isValid())continue;
        auto policy=profile(cl);QString name=policy.value("name","Generic X11 Application").toString();
        QString windowTitle=title(d,w),shortName=name=="Generic X11 Application"?cl:name;if(name=="Firefox"&&windowTitle.contains("YouTube"))shortName+=" · YouTube";
        QString icon=policy.value("icon",cl.contains("terminal")?"utilities-terminal":cl.contains("firefox")?"firefox-esr":cl=="thunar"?"system-file-manager":"application-x-executable").toString();
        bool fullscreen=states.contains(XInternAtom(d,"_NET_WM_STATE_FULLSCREEN",False));bool hidden=states.contains(XInternAtom(d,"_NET_WM_STATE_HIDDEN",False));
        auto desktop=prop(d,w,"_NET_WM_DESKTOP");
        windows.append(QVariantMap{{"id",QString("0x%1").arg(w,0,16)},{"title",windowTitle},{"class",cl},{"profile",name},{"name",shortName},{"icon",icon},{"dialog",dialog},{"x",g.x()},{"y",g.y()},{"width",g.width()},{"height",g.height()},{"phone",!desktopOnly&&panel.contains(g.center())},{"floating",qEnvironmentVariableIntValue("ETHERSHELL_FLOATING")==1},{"fullscreen",fullscreen},{"hidden",hidden},{"desktop",desktop.isEmpty()?0:int(desktop[0])},{"active",!active.isEmpty()&&active[0]==w}});
        XSelectInput(d,w,PropertyChangeMask|StructureNotifyMask);
        if(!active.isEmpty()&&active[0]==w){m_active=w;m_activeClass=cl;}
        if(m_safe)continue;
        const bool newlyManaged=!m_saved.contains(w);
        if(!m_saved.contains(w)){Saved s;s.geometry=g;s.maxH=states.contains(XInternAtom(d,"_NET_WM_STATE_MAXIMIZED_HORZ",False));s.maxV=states.contains(XInternAtom(d,"_NET_WM_STATE_MAXIMIZED_VERT",False));s.fullscreen=fullscreen;s.policy=policy.value("geometry","maximize").toString();s.identity=cl+":"+(pid.isEmpty()?QString():QString::number(pid[0]));m_saved.insert(w,s);persist();}
        auto &saved=m_saved[w];
        if(qEnvironmentVariableIntValue("ETHERSHELL_FLOATING")==1&&newlyManaged&&!dialog){saved.policy="free";state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");}
        if(normal&&!dialog&&policy.value("decoration","surface")!="native")decorate(w,saved,g.size(),fullscreen||!policy.value("rounding",true).toBool());
        bool onPhone=!desktopOnly&&panel.contains(g.center());
        bool gone=true;for(auto*s:QGuiApplication::screens())if(s->geometry().intersects(g))gone=false;
        if(!m_external&&!onPhone){saved.policy=qEnvironmentVariableIntValue("ETHERSHELL_FLOATING")==1?"free":"maximize";saved.signature.clear();}
        if(desktopOnly&&saved.signature.isEmpty()){QRect target=usable(panel).adjusted(36,86,-36,-40);target.setSize(QSize(std::min(1200,target.width()),std::min(780,target.height())));state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");fit(w,target);saved.signature="external";continue;}
        if(m_external&&onPhone&&!dialog&&saved.signature.isEmpty()&&policy.value("placement","phone")=="external"){
            for(auto*s:QGuiApplication::screens())if(s->geometry()!=panel){state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");QRect target=usable(s->geometry());target.setSize(QSize(std::min(1200,target.width()),std::min(850,target.height())));fit(w,target);saved.signature="external";break;}
            continue;
        }
        if(m_external&&!onPhone&&!gone){saved.signature="external";continue;}
        if(!dialog&&keyboard&&states.contains(XInternAtom(d,"_NET_WM_STATE_FULLSCREEN",False))){
            state(w,"_NET_WM_STATE_FULLSCREEN",false);
            // xfwm4 retains the old maximised rectangle under fullscreen.
            // Re-enter maximisation so it recomputes the keyboard workarea.
            state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");
            saved.keyboardFullscreen=true;saved.signature.clear();
        }
        if(saved.keyboardFullscreen&&!keyboard){state(w,"_NET_WM_STATE_FULLSCREEN",true);saved.keyboardFullscreen=false;saved.signature.clear();continue;}
        QRect area=phoneArea;QString sig=QString("%1,%2,%3,%4:%5:%6").arg(area.x()).arg(area.y()).arg(area.width()).arg(area.height()).arg(saved.policy).arg(m_external);
        if(m_surface)for(auto extent:prop(d,w,"_NET_FRAME_EXTENTS"))sig+=":"+QString::number(extent);
        const int headerSpace=m_nativeFrames?0:qRound(60*std::max(1.,m_margin/8.));
        const int gripSpace=m_nativeFrames?0:qRound(44*std::max(1.,m_margin/8.));
        QRect frame=g;
        if(m_nativeFrames){const auto extents=prop(d,w,"_NET_FRAME_EXTENTS");if(extents.size()==4)frame.adjust(-int(extents[0]),-int(extents[2]),int(extents[1]),int(extents[3]));}
        bool stranded=g.right()<area.left()+40||g.left()>area.right()-40||g.top()>area.bottom()-40||g.bottom()<area.top()+40;
        if(saved.policy=="free"&&!fullscreen){if(m_nativeFrames)stranded=frame.right()<area.left()+80||frame.left()>area.right()-80||frame.top()>area.bottom()-40||g.top()<area.top()+24;else stranded|=frame.top()<area.top()+headerSpace||frame.left()<area.left()||frame.right()>area.right()||frame.bottom()>area.bottom()-gripSpace;}
        if(saved.signature==sig&&!stranded)continue;saved.signature=sig;
        if(dialog){
            // Keep modality and focus with xfwm; only repair oversized/offscreen dialogs.
            if(!area.contains(g)){QSize size(std::min(g.width(),area.width()-20),std::min(g.height(),area.height()-20));QRect target(QPoint(area.center().x()-size.width()/2,area.center().y()-size.height()/2),size);fit(w,target);}continue;
        }
        if(states.contains(XInternAtom(d,"_NET_WM_STATE_FULLSCREEN",False))&&!saved.keyboardFullscreen)continue;
        if(m_nativeFrames&&saved.policy=="free"&&(states.contains(XInternAtom(d,"_NET_WM_STATE_MAXIMIZED_HORZ",False))||states.contains(XInternAtom(d,"_NET_WM_STATE_MAXIMIZED_VERT",False))))continue;
        if(saved.policy=="fullscreen"&&!keyboard)state(w,"_NET_WM_STATE_FULLSCREEN",true);
        else if(saved.policy=="fullscreen"&&keyboard)state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",true,"_NET_WM_STATE_MAXIMIZED_VERT");
        else if(saved.policy=="maximize"){if(m_surface){state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");fit(w,area);}else state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",true,"_NET_WM_STATE_MAXIMIZED_VERT");}
        else if(saved.policy=="split-top"||saved.policy=="split-bottom"){
            state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");int h=area.height()/2;if(saved.policy=="split-bottom")area.setTop(area.top()+h);else area.setHeight(h);fit(w,area);
        }else if(saved.policy=="fit") {state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");fit(w,area);}
        else if(saved.policy=="free") {QRect bounds=area.adjusted(0,headerSpace,0,-gripSpace);if(bounds.height()<100)bounds=area;QRect target=frame;if(keyboard&&saved.keyboardGeometry.isEmpty())saved.keyboardGeometry=frame;else if(!keyboard&&!saved.keyboardGeometry.isEmpty()){target=saved.keyboardGeometry;saved.keyboardGeometry=QRect();}target.setSize(QSize(std::min(target.width(),bounds.width()),std::min(target.height(),bounds.height())));target.moveLeft(qBound(bounds.left(),target.left(),bounds.right()-target.width()+1));target.moveTop(qBound(bounds.top(),target.top(),bounds.bottom()-target.height()+1));if(target!=frame)fit(w,target);}
    }
    for(auto it=m_saved.begin();it!=m_saved.end();)if(!clients.contains(it.key()))it=m_saved.erase(it);else ++it;
    for(auto it=m_redirected.begin();it!=m_redirected.end();)if(!clients.contains(*it))it=m_redirected.erase(it);else ++it;
    if(!clients.contains(m_active)){m_active=0;m_activeClass.clear();}
    bool update=m_windows!=windows;const auto previousIds=windowIds();m_windows=windows;if(previousIds!=windowIds())emit windowIdsChanged();if(update)emit changed();
}
void Pocket::restore(){if(!m_display)return;for(auto it=m_saved.begin();it!=m_saved.end();++it){auto w=it.key();auto s=it.value();restoreDecoration(w,s);state(w,"_NET_WM_STATE_FULLSCREEN",false);state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");auto*d=static_cast<Display*>(m_display);auto ex=prop(d,w,"_NET_FRAME_EXTENTS");QRect r=s.geometry;if(ex.size()==4)r.adjust(-int(ex[0]),-int(ex[2]),int(ex[1]),int(ex[3]));fit(w,r);if(s.maxH)state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",true);if(s.maxV)state(w,"_NET_WM_STATE_MAXIMIZED_VERT",true);if(s.fullscreen)state(w,"_NET_WM_STATE_FULLSCREEN",true);}m_saved.clear();persist();}
void Pocket::setEnabled(bool on){if(!on){releasePreviews();restore();}m_safe=!on;scan();emit changed();}
void Pocket::action(const QString &a,const QString &id){
    auto*d=static_cast<Display*>(m_display);if(!d)return;unsigned long w=id.isEmpty()?m_active:id.toULong(nullptr,16);
    auto clients=prop(d,DefaultRootWindow(d),"_NET_CLIENT_LIST",XA_WINDOW);
    QRect currentScreen=phone();if(w)for(auto*s:QGuiApplication::screens())if(s->geometry().contains(geometry(d,w).center()))currentScreen=s->geometry();
    if(a=="next"||a=="previous") {QVector<unsigned long> list;for(auto v:m_windows){auto item=v.toMap();if(!item["dialog"].toBool())list.append(item["id"].toString().toULong(nullptr,16));}if(list.isEmpty())return;int i=list.indexOf(w);w=list[i<0?(a=="next"?0:list.size()-1):(i+(a=="next"?1:list.size()-1))%list.size()];}
    if(!w||!clients.contains(w))return;
    if(a=="activate"||a=="next"||a=="previous"){auto desk=prop(d,w,"_NET_WM_DESKTOP");if(!desk.isEmpty()&&desk[0]!=0xffffffff)send(DefaultRootWindow(d),"_NET_CURRENT_DESKTOP",desk[0],CurrentTime);send(w,"_NET_ACTIVE_WINDOW",2,CurrentTime);}
    else if(a=="close")send(w,"_NET_CLOSE_WINDOW",CurrentTime,2);
    else if(a=="minimize")XIconifyWindow(d,w,DefaultScreen(d));
    else if(a=="restore"){if(m_saved.contains(w)){auto &s=m_saved[w];s.policy="free";s.signature=qEnvironmentVariableIntValue("ETHERSHELL_DESKTOP_TEST")==1?"external":QString();state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");QRect area=usable(currentScreen);QRect target=area.adjusted(area.width()/10,area.height()/6,-area.width()/10,-area.height()/6);fit(w,target);}}
    else if(a=="external"||a=="phone"){QRect target=phone();if(a=="external"){bool found=false;for(auto*s:QGuiApplication::screens())if(s->geometry()!=phone()){target=s->geometry();found=true;break;}if(!found)return;}state(w,"_NET_WM_STATE_FULLSCREEN",false);state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");target=usable(target).adjusted(24,70,-24,-24);target.setSize(QSize(std::min(1200,target.width()),std::min(850,target.height())));fit(w,target);if(m_saved.contains(w)){m_saved[w].signature.clear();m_saved[w].policy=a=="phone"?"maximize":"free";}}
    else if(a=="move"||a=="resize"){Window root,child;int rx,ry,wx,wy;unsigned int mask;XQueryPointer(d,DefaultRootWindow(d),&root,&child,&rx,&ry,&wx,&wy,&mask);send(w,"_NET_WM_MOVERESIZE",rx,ry,a=="move"?8:4,1,2);}
    else if(a=="fullscreen"){send(w,"_NET_WM_STATE",2,XInternAtom(d,"_NET_WM_STATE_FULLSCREEN",False),0,2);if(m_saved.contains(w))m_saved[w].signature.clear();}
    else if(a=="maximize"||a=="fit"||a.startsWith("split-")){state(w,"_NET_WM_STATE_FULLSCREEN",false);if(m_saved.contains(w)){m_saved[w].policy=a;m_saved[w].keyboardFullscreen=false;m_saved[w].signature.clear();}
        if(currentScreen!=phone()||qEnvironmentVariableIntValue("ETHERSHELL_DESKTOP_TEST")==1){QRect target=usable(currentScreen).adjusted(12,58,-12,-12);if(a=="split-top")target.setHeight(target.height()/2);else if(a=="split-bottom"){int half=target.height()/2;target.setTop(target.top()+half);}state(w,"_NET_WM_STATE_MAXIMIZED_HORZ",false,"_NET_WM_STATE_MAXIMIZED_VERT");fit(w,target);if(m_saved.contains(w)){m_saved[w].policy="free";m_saved[w].signature="external";}}else scan();}
    XFlush(d);
}
void Pocket::diagnose(const QString &path){QVariantList saved;for(auto it=m_saved.begin();it!=m_saved.end();++it)saved.append(QVariantMap{{"id",QString("0x%1").arg(it.key(),0,16)},{"policy",it->policy},{"signature",it->signature}});QSaveFile f(path);if(f.open(QIODevice::WriteOnly)){f.write(QJsonDocument::fromVariant(QVariantMap{{"enabled",enabled()},{"external",external()},{"windows",m_windows},{"managed",saved}}).toJson());f.commit();}}
