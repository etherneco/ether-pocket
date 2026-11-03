#include "mobile.h"
#include "policy.h"
#include <QDBusConnection>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QUuid>
#include <QDir>
#include <unistd.h>
#include <pwd.h>
#include <memory>

static const QString MM="org.freedesktop.ModemManager1", MP="/org/freedesktop/ModemManager1", MI=MM+".Modem";
static const QString NM="org.freedesktop.NetworkManager", NP="/org/freedesktop/NetworkManager", NI=NM;
static const QString PROPS="org.freedesktop.DBus.Properties";
static const QString SETTINGS=NM+".Settings", CONNECTION=SETTINGS+".Connection";
static QString pathOf(const QVariant &v) { return qvariant_cast<QDBusObjectPath>(v).path(); }
static QVariantMap mapOf(const QVariant &v) { return qdbus_cast<QVariantMap>(v); }

Mobile::Mobile(QObject *parent):ModemProvider(parent) {
    qDBusRegisterMetaType<Settings>(); qDBusRegisterMetaType<ManagedObjects>();
    qDBusRegisterMetaType<RadioMode>();qDBusRegisterMetaType<QList<RadioMode>>();qDBusRegisterMetaType<QList<QByteArray>>();qDBusRegisterMetaType<QList<quint32>>();
    qDBusRegisterMetaType<ControlPort>();qDBusRegisterMetaType<QList<ControlPort>>();
    m_debounce.setSingleShot(true);m_debounce.setInterval(180);
    connect(&m_debounce,&QTimer::timeout,this,&Mobile::refresh);
    auto bus=QDBusConnection::systemBus();
    // Subscribe before discovery so device additions/removal and daemon restarts
    // cannot leave stale connection or capability state on screen.
    bus.connect(MM,MP,"org.freedesktop.DBus.ObjectManager","InterfacesAdded",this,SLOT(scheduleRefresh()));
    bus.connect(MM,MP,"org.freedesktop.DBus.ObjectManager","InterfacesRemoved",this,SLOT(scheduleRefresh()));
    bus.connect(MM,QString(),PROPS,"PropertiesChanged",this,SLOT(scheduleRefresh()));
    bus.connect(NM,QString(),PROPS,"PropertiesChanged",this,SLOT(scheduleRefresh()));
    bus.connect(NM,QString(),CONNECTION,"Updated",this,SLOT(scheduleRefresh()));
    bus.connect(NM,QString(),CONNECTION,"Removed",this,SLOT(scheduleRefresh()));
    bus.connect(NM,NP+"/Settings",SETTINGS,"NewConnection",this,SLOT(scheduleRefresh()));
    auto *watch=new QDBusServiceWatcher(MM,bus,QDBusServiceWatcher::WatchForOwnerChange,this);
    watch->addWatchedService(NM);
    connect(watch,&QDBusServiceWatcher::serviceOwnerChanged,this,[this]{
        ++m_generation; ++m_networkGeneration; ++m_profileGeneration;
        m_objects.clear();m_device.clear();m_active.clear();m_activeProfile.clear();m_networkInfo.clear();m_ipInterface.clear();m_nmActivated=false;m_hasIp=false;m_mmAvailable=false;
        m_settings.clear();m_profiles.clear();m_simInfo.clear();m_simInfoPath.clear();
        recompute();scheduleRefresh();
    });
    connect(&m_doctor,&QProcess::finished,this,[this](int code,QProcess::ExitStatus){
        m_doctorTimeout.stop();
        auto doc=QJsonDocument::fromJson(m_doctor.readAllStandardOutput());
        m_doctor.readAllStandardError(); // Never forward raw service errors/identifiers.
        if(code==0 && doc.isObject() && doc.object().value("schema").toInt()==1) {
            m_stages=doc.object().value("stages").toArray().toVariantList();
            m_message="Read-only diagnostics complete. Internet access has not been tested.";
        } else m_message="Diagnostics unavailable or incomplete. Run the Doctor locally for additional permissions.";
        emit changed();
    });
    connect(&m_doctor,&QProcess::errorOccurred,this,[this]{fail("Unable to start the installed Doctor.");});
    m_doctorTimeout.setSingleShot(true);
    connect(&m_doctorTimeout,&QTimer::timeout,&m_doctor,&QProcess::kill);
    m_operationTimeout.setSingleShot(true);
    connect(&m_operationTimeout,&QTimer::timeout,this,[this]{m_verify={};m_reconnectProfile.clear();const bool ipa=m_ipaOperation;m_ipaOperation=false;result(ipa?"Błąd połączenia":"Verification failed",ipa?"Przekroczono czas oczekiwania na połączenie. "+m_status.value("dataMessage").toString():"Timed out waiting for effective state. No automatic retry or rollback was performed.");});
    m_dataTimer.setInterval(1500);connect(&m_dataTimer,&QTimer::timeout,this,&Mobile::fetchIpaData);m_dataTimer.start();
    connect(this,&Mobile::changed,this,&Mobile::finishObservedOperation);
    m_usageTimer.setInterval(30000);connect(&m_usageTimer,&QTimer::timeout,this,&Mobile::sampleUsage);m_usageTimer.start();
    recompute();
    QTimer::singleShot(0,this,&Mobile::refresh);
}

void Mobile::call(const QString &service,const QString &path,const QString &iface,const QString &method,const QVariantList &args,Reply done,bool interactive,int timeoutMs) {
    auto msg=QDBusMessage::createMethodCall(service,path,iface,method);msg.setArguments(args);
    msg.setInteractiveAuthorizationAllowed(interactive);
    auto *watch=new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg,timeoutMs),this);
    connect(watch,&QDBusPendingCallWatcher::finished,this,[watch,done]{auto reply=watch->reply();watch->deleteLater();done(reply);});
}
void Mobile::scheduleRefresh(){m_dirty=true;if(!m_debounce.isActive())m_debounce.start();}
void Mobile::refresh(){
    if(m_fetching){m_dirty=true;return;}m_fetching=true;m_dirty=false;
    auto generation=++m_generation;
    call(MM,MP,"org.freedesktop.DBus.ObjectManager","GetManagedObjects",{},[this,generation](const QDBusMessage &reply){
        m_fetching=false;
        if(generation==m_generation){
            m_mmAvailable=reply.type()!=QDBusMessage::ErrorMessage;
            m_objects=m_mmAvailable && !reply.arguments().isEmpty()?qdbus_cast<ManagedObjects>(reply.arguments()[0]):ManagedObjects{};
            recompute();fetchSim();fetchNetwork();fetchProfiles();
        }
        if(m_dirty)scheduleRefresh();
    });
}
void Mobile::selectModem(const QString &path){
    if(busy())return;
    if(!m_objects.contains(QDBusObjectPath(path)) || !m_objects.value(QDBusObjectPath(path)).contains(MI))return;
    m_selected=path;m_device.clear();m_active.clear();m_activeProfile.clear();m_networkInfo.clear();m_ipInterface.clear();m_modeRollback=false;m_previousConnectionProfile.clear();m_nmActivated=false;m_hasIp=false;recompute();fetchSim();fetchNetwork();
}
void Mobile::recompute(){
    m_modems.clear();
    QStringList paths;
    for(auto i=m_objects.cbegin();i!=m_objects.cend();++i) if(i.value().contains(MI)) {
        auto p=i.value().value(MI);paths<<i.key().path();
        m_modems<<QVariantMap{{"path",i.key().path()},{"label",p.value("Manufacturer").toString()+" "+p.value("Model").toString()}};
    }
    if(!paths.contains(m_selected)) {
        m_selected=paths.value(0);m_device.clear();m_active.clear();m_activeProfile.clear();m_networkInfo.clear();m_ipInterface.clear();m_modeRollback=false;m_previousConnectionProfile.clear();m_nmActivated=false;m_hasIp=false;
    }
    auto interfaces=m_objects.value(QDBusObjectPath(m_selected.isEmpty()?"/":m_selected));
    auto p=interfaces.value(MI),gpp=interfaces.value(MI+".Modem3gpp");
    m_sim=pathOf(p.value("Sim"));
    if(m_simInfoPath!=m_sim){m_simInfo.clear();m_simInfoPath=m_sim;}
    const auto sim=m_simInfo;
    const bool present=!m_selected.isEmpty(),roaming=gpp.value("RegistrationState").toUInt()==5;
    bool bearer=false;
    for(const auto &bp:qdbus_cast<QList<QDBusObjectPath>>(p.value("Bearers")))
        bearer|=m_objects.value(bp).value(MM+".Bearer").value("Connected").toBool();
    QString signal="Unavailable";
    if(p.contains("SignalQuality")) {
        const auto arg=qvariant_cast<QDBusArgument>(p.value("SignalQuality"));quint32 value=0;bool recent=false;
        arg.beginStructure();arg >> value >> recent;arg.endStructure();
        if(recent)signal=QString::number(value)+"%";
    }
    m_modes.clear();
    for(const auto &mode:qdbus_cast<QList<RadioMode>>(p.value("SupportedModes"))){
        if(mode.allowed & (1u<<4))continue; // No functional NR selector for this integration.
        QStringList names;if(mode.allowed&8)names<<"LTE";if(mode.allowed&4)names<<"3G";if(mode.allowed&2)names<<"2G";
        if(names.isEmpty())continue;
        QString label=names.join(" / ");if(mode.preferred)label+=" · "+QString(mode.preferred==8?"LTE":mode.preferred==4?"3G":"2G")+" preferred";
        else if(names.size()>1)label+=" automatic";else label+=" only";
        m_modes<<QVariantMap{{"id",QString::number(mode.allowed)+"/"+QString::number(mode.preferred)},{"label",label},{"allowed",mode.allowed},{"preferred",mode.preferred}};
    }
    const auto effective=qdbus_cast<RadioMode>(p.value("CurrentModes"));
    QVariantList ports;for(const auto &port:qdbus_cast<QList<ControlPort>>(p.value("Ports")))ports<<QVariantMap{{"name",port.name},{"type",port.type},{"protocol",port.type==6?"QMI":port.type==7?"MBIM":port.type==3?"AT":port.type==2?"network":"other"}};
    QVariantMap metrics;const auto signalProperties=interfaces.value(MI+".Signal");
    for(const auto &family:QStringList{"Lte","Umts","Gsm","Cdma","Evdo","Nr5g"}){const auto values=mapOf(signalProperties.value(family));if(!values.isEmpty())metrics[family]=values;}
    const auto locks=qdbus_cast<QMap<quint32,quint32>>(p.value("UnlockRetries"));
    const auto required=p.value("UnlockRequired").toUInt();
    auto simSlots=qdbus_cast<QList<QDBusObjectPath>>(p.value("SimSlots"));int validSlots=0;for(const auto &slot:simSlots)if(slot.path()!="/")++validSlots;
    m_status={{"smsInterface",interfaces.contains(MI+".Messaging")},{"registered",gpp.value("RegistrationState").toUInt()==1||gpp.value("RegistrationState").toUInt()==5},{"available",present},{"selected",m_selected},{"serviceAvailable",m_mmAvailable},
        {"state",present?Policy::state(p.value("State").toInt(),bearer,m_nmActivated,m_hasIp,roaming):"Not detected"},
        {"operator",gpp.value("OperatorName","Unavailable")},{"technology",Policy::technology(p.value("AccessTechnologies").toUInt())},
        {"signal",signal},{"radio",p.value("PowerState").toUInt()==3},{"roaming",roaming},
        {"sim",m_sim.isEmpty() || m_sim=="/"?"Unavailable":"Detected"},{"simSlot",p.value("PrimarySimSlot")},
        {"pinRequired",p.value("UnlockRequired").toUInt()==2},{"canConnect",present && !m_device.isEmpty() && p.value("State").toInt()==8},
        {"canDisconnect",!m_active.isEmpty()},{"hasIp",m_hasIp},{"nmActivated",m_nmActivated},{"internet","Not verified"},
        {"dataActive",bearer&&m_nmActivated&&m_hasIp&&p.value("State").toInt()==11},
        {"dataPending",!m_active.isEmpty()&&!(bearer&&m_nmActivated&&m_hasIp&&p.value("State").toInt()==11)},
        {"connectionRollbackAvailable",m_active.isEmpty()&&!m_previousConnectionProfile.isEmpty()},
        {"model",p.value("Model","Unavailable")},{"firmware",p.value("Revision","Unavailable")},
        {"manufacturer",p.value("Manufacturer","Unavailable")},{"drivers",p.value("Drivers")},{"transport",p.value("PrimaryPort","Unavailable")},
        {"ports",ports},{"signalMetrics",metrics},{"powerState",p.value("PowerState")},{"currentCapabilities",p.value("CurrentCapabilities")},{"supportedModes",m_modes},
        {"simOperator",sim.value("OperatorName","Unavailable")},{"simHomeNetwork",sim.value("OperatorIdentifier","Unavailable")},
        {"simReady",!sim.isEmpty()&&(required==1||required==3)&&p.value("State").toInt()>=3},{"unlockRequired",required},
        {"pinLock",bool(gpp.value("EnabledFacilityLocks").toUInt()&1)},{"remainingAttempts",(required==2||required==4)&&locks.contains(required)?QVariant(locks.value(required)):QVariant()},
        {"slots",simSlots.size()},{"canSelectSlot",validSlots>1},{"registration",gpp.value("RegistrationState")},{"operatorCode",gpp.value("OperatorCode","Unavailable")},
        {"currentMode",QString::number(effective.allowed)+"/"+QString::number(effective.preferred)},
        {"enabledModes",QString("allowed=%1; preferred=%2").arg(effective.allowed).arg(effective.preferred)},
        {"network",m_networkInfo},{"activeProfile",m_activeProfile},{"interface",m_ipInterface},
        {"canScan",interfaces.contains(MI+".Modem3gpp")},{"selectionMode","Not exposed by ModemManager; saved operator association is per profile"},
        {"explanation",present?"Registration and a data session do not prove internet access.":m_mmAvailable?"No usable modem exported by ModemManager. Run Diagnostics to inspect the hardware and packet path.":"ModemManager is unavailable on the system bus."}};
    m_ipa=false;
    for(const auto &port:qdbus_cast<QList<ControlPort>>(p.value("Ports")))if(port.name=="rmnet_ipa0")m_ipa=true;
    if(m_ipa)mergeIpaData();
    emit changed();
}
void Mobile::fetchSim(){
    const auto path=m_sim;const auto generation=m_generation;
    if(path.isEmpty()||path=="/")return;
    call(MM,path,PROPS,"GetAll",{MM+".Sim"},[this,path,generation](const QDBusMessage &r){
        if(generation!=m_generation||path!=m_sim)return;
        m_simInfo.clear();m_simInfoPath=path;
        if(r.type()!=QDBusMessage::ErrorMessage&&!r.arguments().isEmpty()){
            const auto values=mapOf(r.arguments()[0]);
            for(const auto &key:QStringList{"Active","OperatorName","OperatorIdentifier"})if(values.contains(key))m_simInfo[key]=values[key];
        }
        recompute();
    });
}
void Mobile::fetchNetwork(){
    const auto generation=++m_networkGeneration;
    call(NM,NP,NI,"GetDevices",{},[this,generation](const QDBusMessage &r){
        if(generation!=m_networkGeneration || r.type()==QDBusMessage::ErrorMessage || r.arguments().isEmpty())return;
        auto devices=qdbus_cast<QList<QDBusObjectPath>>(r.arguments()[0]);
        auto remaining=std::make_shared<int>(devices.size());auto found=std::make_shared<bool>(false);
        if(devices.isEmpty()){m_device.clear();m_active.clear();m_activeProfile.clear();m_ipInterface.clear();m_nmActivated=false;m_hasIp=false;m_networkInfo.clear();recompute();}
        for(const auto &d:devices){
            call(NM,d.path(),PROPS,"GetAll",{NM+".Device"},[this,d,generation,remaining,found](const QDBusMessage &reply){
                if(generation!=m_networkGeneration)return;
                --*remaining;
                const auto p=reply.type()!=QDBusMessage::ErrorMessage?mapOf(reply.arguments().value(0)):QVariantMap{};
                const bool matches=p.value("DeviceType").toUInt()==8&&!m_selected.isEmpty()&&p.value("Udi").toString()==m_selected;
                if(!matches){if(!*remaining&&!*found){m_device.clear();m_active.clear();m_activeProfile.clear();m_ipInterface.clear();m_nmActivated=false;m_hasIp=false;m_networkInfo.clear();recompute();}return;}
                *found=true;
                m_device=d.path();m_nmActivated=p.value("State").toUInt()==100;
                const auto active=pathOf(p.value("ActiveConnection"));
                const auto nextActive=active=="/"?QString():active;
                if(nextActive!=m_active){m_hasIp=false;m_activeProfile.clear();m_networkInfo.clear();}
                m_active=nextActive;
                m_ipInterface=m_nmActivated?p.value("IpInterface").toString():QString();
                if(m_active.isEmpty()){m_activeProfile.clear();m_networkInfo.clear();m_hasIp=false;}
                else call(NM,m_active,PROPS,"GetAll",{NM+".Connection.Active"},[this,generation](const QDBusMessage &a){
                    if(generation!=m_networkGeneration||a.type()==QDBusMessage::ErrorMessage||a.arguments().isEmpty())return;
                    m_activeProfile=pathOf(mapOf(a.arguments()[0]).value("Connection"));recompute();
                });
                auto ipPaths=QMap<QString,QString>{{"ipv4",pathOf(p.value("Ip4Config"))},{"ipv6",pathOf(p.value("Ip6Config"))}};
                auto ipCount=std::make_shared<int>(0);auto ipFound=std::make_shared<bool>(false);auto details=std::make_shared<QVariantMap>();
                for(auto i=ipPaths.cbegin();i!=ipPaths.cend();++i)if(!i.value().isEmpty()&&i.value()!="/")++*ipCount;
                if(!*ipCount){m_hasIp=false;m_networkInfo.clear();recompute();}
                for(auto i=ipPaths.cbegin();i!=ipPaths.cend();++i){
                    if(i.value().isEmpty()||i.value()=="/")continue;
                    const auto family=i.key();
                    call(NM,i.value(),PROPS,"GetAll",{family=="ipv4"?NM+".IP4Config":NM+".IP6Config"},[this,generation,family,ipCount,ipFound,details](const QDBusMessage &a){
                        if(generation!=m_networkGeneration)return;
                        if(a.type()!=QDBusMessage::ErrorMessage&&!a.arguments().isEmpty()){
                            const auto info=mapOf(a.arguments()[0]);const auto addresses=qdbus_cast<QList<QVariantMap>>(info.value("AddressData"));
                            *ipFound|=!addresses.isEmpty();
                            (*details)[family]=QVariantMap{{"addresses",QVariant::fromValue(addresses)},{"gateway",info.value("Gateway")},
                                {"dns",QVariant::fromValue(qdbus_cast<QList<QVariantMap>>(info.value("NameserverData")))},
                                {"routes",QVariant::fromValue(qdbus_cast<QList<QVariantMap>>(info.value("RouteData")))}};
                        }
                        if(!--*ipCount){m_hasIp=*ipFound;m_networkInfo=*details;recompute();}
                    });
                }
                recompute();
            });
        }
    });
}
void Mobile::fetchProfiles(){
    const auto generation=++m_profileGeneration;
    call(NM,NP+"/Settings",SETTINGS,"ListConnections",{},[this,generation](const QDBusMessage &r){
        if(generation!=m_profileGeneration || r.type()==QDBusMessage::ErrorMessage || r.arguments().isEmpty())return;
        auto paths=qdbus_cast<QList<QDBusObjectPath>>(r.arguments()[0]);auto count=std::make_shared<int>(paths.size());
        auto profiles=std::make_shared<QVariantList>();auto settingsList=std::make_shared<QMap<QString,Settings>>();
        if(paths.isEmpty()){m_profiles.clear();m_settings.clear();emit changed();}
        for(const auto &p:paths)readProfile(p.path(),[this,p,generation,count,profiles,settingsList](bool ok,Settings settings,quint64 version){
            if(generation!=m_profileGeneration)return;
            if(ok&&settings.value("connection").value("type")=="gsm"){settingsList->insert(p.path(),settings);*profiles<<profileFields(p.path(),settings,version);}
            if(!--*count){m_settings=*settingsList;m_profiles=*profiles;emit changed();}
        });
    });
}
bool Mobile::knownProfile(const QString &p)const{return m_settings.contains(p);}
void Mobile::fail(const QString &s){m_message=s;emit changed();}
void Mobile::mutate(const QString &service,const QString &path,const QString &iface,const QString &method,const QVariantList &args,std::function<void()> accepted){
    if(m_busy)return;
    m_busy=true;m_message="Request in progress…";emit changed();
    call(service,path,iface,method,args,[this,accepted](const QDBusMessage &r){
        m_busy=false;
        // Deliberately do not log service error text, which may include secrets.
        m_message=r.type()==QDBusMessage::ErrorMessage?"Request failed ("+r.errorName()+"). Check authorization, modem readiness and Diagnostics. No automatic retry was made.":"Request accepted. Waiting for observed state; internet access remains unverified.";
        if(r.type()!=QDBusMessage::ErrorMessage && accepted)accepted();
        refresh();emit changed();
    },true);
}
void Mobile::saveProfile(const QString &path,const QString &name,const QString &apn,bool roaming,bool internetRoute,const QString &ipType){
    if(busy())return;
    auto save=[this,path,name,apn,roaming,internetRoute,ipType]{
        auto fields=profileFields(path,m_editBaseline,m_editVersion);
        fields["name"]=name.startsWith(QStringLiteral("EtherMobile · "))?name:QStringLiteral("EtherMobile · ")+name;
        fields["apn"]=apn;fields["roaming"]=roaming;fields["internetRoute"]=internetRoute;fields["ipType"]=ipType;
        if(path.isEmpty()){fields["metric"]=900;fields["priority"]=0;fields["autoconnect"]=false;}
        saveConfiguration(fields);
    };
    m_duplicate=false;
    if(path.isEmpty()){m_editPath.clear();m_editVersion=0;m_editBaseline.clear();save();}
    else if(knownProfile(path)&&beginOperation("Reading profile revision…"))readProfile(path,[this,path,save](bool ok,Settings settings,quint64 version){
        if(!ok){result("Verification failed","Cannot read this profile revision.");return;}
        m_editPath=path;m_editBaseline=settings;m_editVersion=version;m_busy=false;save();
    });
}
void Mobile::deleteProfile(const QString &path){
    for(const auto &v:m_profiles)if(v.toMap().value("path").toString()==path){deleteConfiguration(path,v.toMap().value("version").toString());return;}
}
void Mobile::connectProfile(const QString &path){
    if(m_ipa){ipaDataAction(true,path);return;}
    if(busy())return;
    if(!knownProfile(path)||!m_status.value("canConnect").toBool()||!m_status.value("simReady").toBool()){result("Verification failed","A ready SIM, registered modem and real network device are required.");return;}
    if(!m_active.isEmpty()){result("Verification failed","Disconnect or explicitly reconnect before changing the active profile.");return;}
    if(m_status.value("roaming").toBool()&&m_settings.value(path).value("gsm").value("home-only").toBool()){result("Verification failed","This profile blocks roaming.");return;}
    if(!beginOperation("Requesting mobile data activation…"))return;
    m_activationProfile=path;
    call(NM,NP,NI,"ActivateConnection",{QVariant::fromValue(QDBusObjectPath(path)),QVariant::fromValue(QDBusObjectPath(m_device)),QVariant::fromValue(QDBusObjectPath("/"))},[this](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result(r.errorName().contains("Permission")||r.errorName().contains("Authoriz")?"Permission denied":"Verification failed","Activation failed ("+r.errorName()+"). Saved profiles were retained.");return;}
        monitorConnection(true);
    },true,45000);
}
void Mobile::disconnectData(){
    if(m_ipa){ipaDataAction(false);return;}
    if(m_active.isEmpty()||!beginOperation("Disconnecting this modem's mobile data…"))return;
    call(NM,NP,NI,"DeactivateConnection",{QVariant::fromValue(QDBusObjectPath(m_active))},[this](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){m_reconnectProfile.clear();result("Verification failed","Disconnection request failed ("+r.errorName()+").");return;}
        monitorConnection(false);
    },true);
}
void Mobile::setRadio(bool enabled){
    if(m_selected.isEmpty()||!beginOperation("Changing the selected modem's radio state…"))return;
    call(MM,m_selected,MI,"Enable",{enabled},[this,enabled](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result("Verification failed","Radio request rejected ("+r.errorName()+").");return;}
        m_verify=[this,enabled]{return m_status.value("available").toBool()&&m_status.value("radio").toBool()==enabled;};m_operationTimeout.start(45000);refresh();
    },true,45000);
}
void Mobile::sendPin(const QString &pin){simAction("pin",pin);}
void Mobile::diagnose(){
    if(busy())return;
    m_message="Inspecting the current system without changing radio or network configuration…";
    m_doctor.start("/usr/libexec/ethermobile/ethermobile-doctor.py",{});emit changed();
    m_doctorTimeout.start(145000);
}
