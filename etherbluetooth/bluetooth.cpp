#include "bluetooth.h"
#include "policy.h"
#include <QDBusInterface>
#include <QCoreApplication>
#include <QFile>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QFileInfo>
#include <QDir>
#include <QStandardPaths>
#include <algorithm>
static QString A="org.bluez.Adapter1",D="org.bluez.Device1",P="org.freedesktop.DBus.Properties";
bool Bluetooth::recoveryAvailable() const{return !QStandardPaths::findExecutable("pkexec").isEmpty();}
Bluetooth::Bluetooth(QObject *parent,bool sendNotifications):QObject(parent),agent(this),settings("Etherneco","EtherBluetooth"),notificationsAllowed(sendNotifications) {
    qDBusRegisterMetaType<Interfaces>();qDBusRegisterMetaType<Objects>();
    settings.setValue("schema",1);
    auto config=QStandardPaths::writableLocation(QStandardPaths::ConfigLocation)+"/Etherneco";
    QDir(config).mkpath(".");QFile::setPermissions(config,QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner);
    connect(&agent,&Agent::changed,this,[this]{emit pairingChanged();if(!agent.prompt.isEmpty())notify("Bluetooth pairing request","Open EtherBluetooth to review and confirm the request.");});
    bus.registerObject("/org/etherneco/EtherBluetooth/agent",&agent,QDBusConnection::ExportAllSlots);
    bus.connect("org.bluez","/","org.freedesktop.DBus.ObjectManager","InterfacesAdded",this,SLOT(added(QDBusObjectPath,Interfaces)));
    bus.connect("org.bluez","/","org.freedesktop.DBus.ObjectManager","InterfacesRemoved",this,SLOT(removed(QDBusObjectPath,QStringList)));
    bus.connect("org.bluez",{},P,"PropertiesChanged",this,SLOT(properties(QString,QVariantMap,QStringList,QDBusMessage)));
    auto watcher=new QDBusServiceWatcher("org.bluez",bus,QDBusServiceWatcher::WatchForOwnerChange,this);
    connect(watcher,&QDBusServiceWatcher::serviceOwnerChanged,this,[this](const QString &,const QString &,const QString &owner){
        ++generation;objects.clear();scanOwner.clear();scanTimeout.stop();agent.answer(false,{});transient.clear();busy.clear();attempts.clear();
        for(auto timer:retries)timer->stop();
        emit changed();if(!owner.isEmpty()){registerAgent();refresh();}
    });
    scanTimeout.setSingleShot(true);connect(&scanTimeout,&QTimer::timeout,this,[this]{scan(false);});
    registerAgent();refresh();
}
Bluetooth::~Bluetooth(){
    scan(false);agent.answer(false,{});
    auto msg=QDBusMessage::createMethodCall("org.bluez","/org/bluez","org.bluez.AgentManager1","UnregisterAgent");
    msg<<QVariant::fromValue(QDBusObjectPath("/org/etherneco/EtherBluetooth/agent"));bus.asyncCall(msg);
    bus.unregisterObject("/org/etherneco/EtherBluetooth/agent");
    settings.sync();QFile::setPermissions(settings.fileName(),QFile::ReadOwner|QFile::WriteOwner);
}
void Bluetooth::registerAgent(){call("/org/bluez","org.bluez.AgentManager1","RegisterAgent",{QVariant::fromValue(QDBusObjectPath("/org/etherneco/EtherBluetooth/agent")),"KeyboardDisplay"});}
void Bluetooth::call(const QString &path,const QString &iface,const QString &method,const QVariantList &args,std::function<void(bool)> done){
    auto msg=QDBusMessage::createMethodCall("org.bluez",path,iface,method);msg.setArguments(args);
    auto w=new QDBusPendingCallWatcher(bus.asyncCall(msg,method=="Pair"?90000:20000),this);
    connect(w,&QDBusPendingCallWatcher::finished,this,[this,w,done,path,epoch=generation]{
        auto reply=w->reply();w->deleteLater();if(epoch!=generation)return;
        bool ok=reply.type()!=QDBusMessage::ErrorMessage;
        if(!ok){error=Policy::explain(reply.errorName())+"\n"+reply.errorName()+": "+reply.errorMessage();if(objects.value(QDBusObjectPath(path)).contains(D))deviceErrors[path]=error;emit changed();}
        if(done)done(ok);
    });
}
void Bluetooth::set(const QString &path,const QString &iface,const QString &key,const QVariant &value){call(path,P,"Set",{iface,key,QVariant::fromValue(QDBusVariant(value))});}
void Bluetooth::refresh(){
    if(refreshing)return;refreshing=true;
    auto m=QDBusMessage::createMethodCall("org.bluez","/","org.freedesktop.DBus.ObjectManager","GetManagedObjects");
    auto w=new QDBusPendingCallWatcher(bus.asyncCall(m),this);
    connect(w,&QDBusPendingCallWatcher::finished,this,[this,w,epoch=generation]{
        refreshing=false;QDBusPendingReply<Objects> reply=*w;w->deleteLater();if(epoch!=generation){refresh();return;}
        if(reply.isError()){error=reply.error().message();emit changed();return;}
        objects=reply.value();if(!objects.value(QDBusObjectPath(selected.isEmpty()?"/":selected)).contains(A)){selected.clear();for(auto it=objects.cbegin();it!=objects.cend();++it)if(it->contains(A)){selected=it.key().path();break;}}
        emit changed();
    });
}
QVariantList Bluetooth::adapters() const {QVariantList out;for(auto it=objects.cbegin();it!=objects.cend();++it)if(it->contains(A)){auto v=it->value(A);v["path"]=it.key().path();out<<v;}return out;}
QVariantList Bluetooth::devices() const {
    QVariantList out;
    for(auto it=objects.cbegin();it!=objects.cend();++it)if(it->contains(D)){
        auto v=it->value(D);QString path=it.key().path();
        if(qvariant_cast<QDBusObjectPath>(v.value("Adapter")).path()!=selected)continue;
        v["path"]=path;v["name"]=v.value("Alias",v.value("Name","Unnamed device"));
        v["category"]=Policy::category(v.value("Icon").toString(),qdbus_cast<QStringList>(v.value("UUIDs")));
        v["profiles"]=qdbus_cast<QStringList>(v.value("UUIDs"));
        auto battery=it->value("org.bluez.Battery1");if(battery.contains("Percentage"))v["battery"]=battery["Percentage"];
        v["state"]=transient.value(path,v.value("Connected").toBool()?"Connected":v.value("Paired").toBool()?"Paired · disconnected":"Discovered");
        v["error"]=deviceErrors.value(path);
        QString key=v.value("Address").toString();v["autoConnect"]=settings.value("devices/"+key+"/autoConnect",false);
        v["lastConnected"]=settings.value("devices/"+key+"/lastConnected");
        v["lastSeen"]=settings.value("devices/"+key+"/lastSeen");
        v["history"]=settings.value("devices/"+key+"/history",QVariantList{});
        QStringList nodes;
        for(const auto &input:QDir("/sys/class/input").entryList({"input*"},QDir::Dirs)){
            QFile unique("/sys/class/input/"+input+"/uniq");
            if(unique.open(QIODevice::ReadOnly)&&QString::fromUtf8(unique.readAll()).trimmed().compare(key,Qt::CaseInsensitive)==0)nodes<<input;
        }
        v["inputNodes"]=nodes;
        out<<v;
    }
    std::sort(out.begin(),out.end(),[](const QVariant &a,const QVariant &b){auto x=a.toMap(),y=b.toMap();if(x["Connected"]!=y["Connected"])return x["Connected"].toBool();if(x["Paired"]!=y["Paired"])return x["Paired"].toBool();return x["name"].toString().localeAwareCompare(y["name"].toString())<0;});
    return out;
}
bool Bluetooth::powered(const QString &path) const {return objects.value(QDBusObjectPath(path.isEmpty()?"/":path)).value(A).value("Powered").toBool();}
void Bluetooth::selectAdapter(const QString &path){if(!objects.value(QDBusObjectPath(path)).contains(A))return;scan(false);selected=path;emit changed();}
void Bluetooth::power(bool on){if(selected.isEmpty()){error="No controller registered. Open Driver Doctor.";emit changed();return;}if(!on)scan(false);set(selected,A,"Powered",on);}
void Bluetooth::discoverable(bool on){if(selected.isEmpty())return;if(on){const auto path=selected;call(path,P,"Set",{A,"DiscoverableTimeout",QVariant::fromValue(QDBusVariant(uint(120)))},[this,path](bool ok){if(ok)set(path,A,"Discoverable",true);});}else set(selected,A,"Discoverable",false);}
void Bluetooth::scan(bool on){
    if(!on){scanTimeout.stop();if(!scanOwner.isEmpty()){QString path=scanOwner;scanOwner.clear();call(path,A,"StopDiscovery");}return;}
    if(!scanOwner.isEmpty())return;
    if(!powered(selected)){error="Discovery needs a powered HCI controller. Open Driver Doctor.";emit changed();return;}
    const QString path=selected;scanOwner=path;
    call(path,A,"StartDiscovery",{},[this,path](bool ok){if(!ok){if(scanOwner==path)scanOwner.clear();return;}if(scanOwner==path)scanTimeout.start(30000);else call(path,A,"StopDiscovery");});
}
void Bluetooth::update(const QString &path,const QString &iface,const QVariantMap &values){
    auto &v=objects[QDBusObjectPath(path)][iface];bool wasConnected=v.value("Connected").toBool();
    for(auto i=values.cbegin();i!=values.cend();++i)v[i.key()]=i.value();
    if(iface==D){QString key="devices/"+v.value("Address").toString();
        if(values.contains("RSSI"))settings.setValue(key+"/lastSeen",QDateTime::currentDateTimeUtc());
        if(values.contains("Connected")){
            transient.remove(path);
            if(wasConnected!=v.value("Connected").toBool()){
                notify("Bluetooth",v.value("Connected").toBool()?"Device connected.":"Device disconnected.");
                auto history=settings.value(key+"/history").toList();history.prepend(QVariantMap{{"time",QDateTime::currentDateTimeUtc()},{"event",v.value("Connected").toBool()?"Connected":"Disconnected"}});
                while(history.size()>50)history.removeLast();settings.setValue(key+"/history",history);
            }
            if(v.value("Connected").toBool()){attempts.remove(path);if(retries.contains(path))retries[path]->stop();settings.setValue(key+"/lastConnected",QDateTime::currentDateTimeUtc());}
            else if(wasConnected)retry(path);
        }
    }
    emit changed();
}
void Bluetooth::recover(const QString &operation){
    if(operation!="restart-service"&&operation!="unblock-bluetooth")return;
    if(!recoveryAvailable()){error="Privileged recovery requires the distribution's pkexec package. No recovery action was run.";emit changed();return;}
    auto p=new QProcess(this);
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this,p](int code,QProcess::ExitStatus){error=code?"Recovery declined or failed: "+QString::fromUtf8(p->readAllStandardError()).left(2000):"Recovery command completed; re-checking actual controller state.";p->deleteLater();emit changed();refresh();diagnose();});
    connect(p,&QProcess::errorOccurred,this,[this,p](QProcess::ProcessError e){if(e==QProcess::FailedToStart){error=p->errorString();emit changed();p->deleteLater();}});
    p->start("pkexec",{"/usr/libexec/etherbluetooth/etherbluetooth-recover.py",operation,"--apply"});
}
void Bluetooth::notifyGatt(const QString &path,bool enabled){
    auto v=objects.value(QDBusObjectPath(path)).value("org.bluez.GattCharacteristic1");
    auto flags=qdbus_cast<QStringList>(v.value("Flags"));if(!flags.contains("notify")&&!flags.contains("indicate"))return;
    call(path,"org.bluez.GattCharacteristic1",enabled?"StartNotify":"StopNotify");
}
void Bluetooth::added(const QDBusObjectPath &path,const Interfaces &ifaces){for(auto i=ifaces.cbegin();i!=ifaces.cend();++i)update(path.path(),i.key(),i.value());if(selected.isEmpty()&&ifaces.contains(A)){selected=path.path();emit changed();}}
void Bluetooth::removed(const QDBusObjectPath &path,const QStringList &ifaces){for(const auto &i:ifaces)objects[path].remove(i);if(objects[path].isEmpty())objects.remove(path);if(retries.contains(path.path()))retries[path.path()]->stop();if(selected==path.path()){selected.clear();scanOwner.clear();scanTimeout.stop();refresh();}emit changed();}
void Bluetooth::properties(const QString &iface,const QVariantMap &values,const QStringList &invalid,const QDBusMessage &msg){for(auto &key:invalid)objects[QDBusObjectPath(msg.path())][iface].remove(key);update(msg.path(),iface,values);}
void Bluetooth::action(const QString &path,const QString &operation,const QString &value){
    auto v=objects.value(QDBusObjectPath(path)).value(D);if(v.isEmpty())return;
    QString key="devices/"+v.value("Address").toString();
    if(operation=="autoConnect"){settings.setValue(key+"/autoConnect",value=="on");if(value!="on"&&retries.contains(path))retries[path]->stop();emit changed();return;}
    if(operation=="alias"){if(value.size()<=248&&!value.trimmed().isEmpty())set(path,D,"Alias",value.trimmed());return;}
    if(operation=="trust"){set(path,D,"Trusted",value=="on");return;}
    if(operation=="cancel"){agent.answer(false,{});call(path,D,"CancelPairing");return;}
    if(busy.contains(path))return;
    if(operation=="forget"){manual.insert(path);settings.remove(key);call(qvariant_cast<QDBusObjectPath>(v.value("Adapter")).path(),A,"RemoveDevice",{QVariant::fromValue(QDBusObjectPath(path))});return;}
    QString method;
    if(operation=="pair")method="Pair";
    else if(operation=="connect"){method="Connect";manual.remove(path);attempts.remove(path);if(retries.contains(path))retries[path]->stop();}
    else if(operation=="disconnect"){method="Disconnect";manual.insert(path);if(retries.contains(path))retries[path]->stop();}
    else return;
    busy.insert(path);transient[path]=method=="Pair"?"Pairing":method=="Connect"?"Connecting":"Disconnecting";emit changed();
    call(path,D,method,{},[this,path,method](bool ok){busy.remove(path);transient.remove(path);if(!ok){transient[path]="Failed";notify("Bluetooth operation failed",deviceErrors.value(path));}else{deviceErrors.remove(path);if(method=="Pair")notify("Bluetooth","Pairing completed. Select Connect when ready.");}emit changed();});
}
void Bluetooth::notify(const QString &summary,const QString &body){
    if(!notificationsAllowed||!notifications())return;
    auto msg=QDBusMessage::createMethodCall("org.freedesktop.Notifications","/org/freedesktop/Notifications","org.freedesktop.Notifications","Notify");
    msg<<"EtherBluetooth"<<uint(0)<<"bluetooth"<<summary<<body<<QStringList{}<<QVariantMap{}<<5000;
    QDBusConnection::sessionBus().asyncCall(msg);
}
void Bluetooth::retry(const QString &path){
    auto v=objects.value(QDBusObjectPath(path)).value(D);QString key="devices/"+v.value("Address").toString();
    int delay=Policy::retryDelay(attempts.value(path),powered(qvariant_cast<QDBusObjectPath>(v.value("Adapter")).path()),v.value("Trusted").toBool(),settings.value(key+"/autoConnect",false).toBool(),manual.contains(path));
    if(delay<0)return;
    if(!retries.contains(path)){auto t=new QTimer(this);t->setSingleShot(true);retries[path]=t;
        connect(t,&QTimer::timeout,this,[this,path]{
            auto v=objects.value(QDBusObjectPath(path)).value(D);
            QString key="devices/"+v.value("Address").toString();
            if(v.isEmpty()||v.value("Connected").toBool()||busy.contains(path)||Policy::retryDelay(attempts.value(path),powered(qvariant_cast<QDBusObjectPath>(v.value("Adapter")).path()),v.value("Trusted").toBool(),settings.value(key+"/autoConnect",false).toBool(),manual.contains(path))<0)return;
            attempts[path]++;busy.insert(path);transient[path]="Connecting";emit changed();
            call(path,D,"Connect",{},[this,path](bool ok){busy.remove(path);transient.remove(path);if(!ok){transient[path]="Failed";retry(path);}emit changed();});
        });
    }
    retries[path]->start(delay);
}
void Bluetooth::diagnose(){
    if(diagnosing)return;diagnosing=true;emit diagnosisChanged();
    auto p=new QProcess(this);QString script="/usr/libexec/etherbluetooth/etherbluetooth-doctor.py";
    if(!QFileInfo::exists(script))script=QCoreApplication::applicationDirPath()+"/../scripts/etherbluetooth-doctor.py";
    auto finish=[this,p](int code){diagnosing=false;QJsonParseError parse;auto doc=QJsonDocument::fromJson(p->readAllStandardOutput(),&parse);if(code==0&&doc.isObject())diagnosis=doc.object().toVariantMap();else diagnosis={{"error","Audit failed or timed out: "+QString::fromUtf8(p->readAllStandardError()).left(2000)}};emit diagnosisChanged();p->deleteLater();};
    connect(p,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[finish](int code,QProcess::ExitStatus){finish(code);});
    connect(p,&QProcess::errorOccurred,this,[this,p](QProcess::ProcessError e){if(e==QProcess::FailedToStart){diagnosing=false;diagnosis={{"error",p->errorString()}};emit diagnosisChanged();p->deleteLater();}});
    QTimer::singleShot(90000,p,[p]{if(p->state()!=QProcess::NotRunning)p->kill();});p->start("python3",{script});
}
void Bluetooth::inspectGatt(const QString &device){
    gatt.clear();for(auto it=objects.cbegin();it!=objects.cend();++it)if(it.key().path().startsWith(device+"/"))for(auto iface:QStringList{"org.bluez.GattService1","org.bluez.GattCharacteristic1"})if(it->contains(iface)){auto v=it->value(iface);v["path"]=it.key().path();v["interface"]=iface;v["flags"]=qdbus_cast<QStringList>(v.value("Flags"));gatt<<v;}emit changed();
}
void Bluetooth::readGatt(const QString &path){
    auto v=objects.value(QDBusObjectPath(path)).value("org.bluez.GattCharacteristic1");
    if(!qdbus_cast<QStringList>(v.value("Flags")).contains("read"))return;
    auto m=QDBusMessage::createMethodCall("org.bluez",path,"org.bluez.GattCharacteristic1","ReadValue");m<<QVariantMap{};
    auto w=new QDBusPendingCallWatcher(bus.asyncCall(m),this);
    connect(w,&QDBusPendingCallWatcher::finished,this,[this,w,path]{QDBusPendingReply<QByteArray> r=*w;if(r.isError())error=r.error().message();else error="GATT read: "+QString::fromLatin1(r.value().left(512).toHex(' '));w->deleteLater();emit changed();});
}
