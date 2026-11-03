#include "mobile.h"
#include "policy.h"
#include <QDBusMetaType>
#include <QHostAddress>
#include <QJsonDocument>
#include <QJsonObject>
#include <QUuid>
#include <QtEndian>
#include <pwd.h>
#include <unistd.h>
#include <algorithm>

namespace {
const QString NM="org.freedesktop.NetworkManager", NP="/org/freedesktop/NetworkManager", CI=NM+".Settings.Connection", PROPS="org.freedesktop.DBus.Properties";
QStringList dns(const QVariantMap &p,bool ipv6){
    if(p.contains("dns-data"))return p.value("dns-data").toStringList();
    QStringList out;
    if(ipv6){for(const auto &v:qdbus_cast<QList<QByteArray>>(p.value("dns")))if(v.size()==16){Q_IPV6ADDR a;std::copy(v.begin(),v.end(),a.c);out<<QHostAddress(a).toString();}}
    else for(auto v:qdbus_cast<QList<quint32>>(p.value("dns")))out<<QHostAddress(qFromBigEndian(v)).toString();
    return out;
}
QString auth(const Settings &s){
    auto p=s.value("ppp");
    if(p.value("refuse-eap").toBool()&&p.value("refuse-mschap").toBool()&&p.value("refuse-mschapv2").toBool()){
        if(!p.value("refuse-pap").toBool()&&p.value("refuse-chap").toBool())return "PAP";
        if(p.value("refuse-pap").toBool()&&!p.value("refuse-chap").toBool())return "CHAP";
        if(!p.value("refuse-pap").toBool()&&!p.value("refuse-chap").toBool())return "PAP or CHAP";
    }
    return "Automatic";
}
QVariant decodeArgument(const QDBusArgument &a){
    if(a.currentType()==QDBusArgument::BasicType){auto v=a.asVariant();if(v.metaType()==QMetaType::fromType<QDBusObjectPath>())return qvariant_cast<QDBusObjectPath>(v).path();return v;}
    if(a.currentType()==QDBusArgument::VariantType){QDBusVariant v;a>>v;const auto value=v.variant();if(value.metaType()==QMetaType::fromType<QDBusArgument>())return decodeArgument(qvariant_cast<QDBusArgument>(value));return value;}
    if(a.currentType()==QDBusArgument::MapType){QVariantMap out;a.beginMap();while(!a.atEnd()){a.beginMapEntry();const auto key=decodeArgument(a).toString();out[key]=decodeArgument(a);a.endMapEntry();}a.endMap();return out;}
    QVariantList out;
    const bool array=a.currentType()==QDBusArgument::ArrayType;
    if(array)a.beginArray();else a.beginStructure();
    while(!a.atEnd())out<<decodeArgument(a);
    if(array)a.endArray();else a.endStructure();return out;
}
QVariantMap canonical(const Settings &s){
    QVariantMap result;
    for(auto group=s.cbegin();group!=s.cend();++group){
        QVariantMap fields;
        for(auto v=group.value().cbegin();v!=group.value().cend();++v)
            fields[v.key()]=v.value().metaType()==QMetaType::fromType<QDBusArgument>()
                ?decodeArgument(qvariant_cast<QDBusArgument>(v.value())):v.value();
        result[group.key()]=fields;
    }
    return result;
}
}
void Mobile::result(const QString &state,const QString &message){
    m_busy=false;m_operationTimeout.stop();m_connectionTarget=-1;m_verify={};
    m_message=message;m_operation={{"state",state},{"message",message},{"rollbackAvailable",!m_rollbackPath.isEmpty()},{"modeRollbackAvailable",m_modeRollback}};
    emit operationChanged();emit changed();
}
bool Mobile::beginOperation(const QString &description){
    if(busy())return false;
    m_busy=true;m_message=description;m_operation={{"state","Applying"},{"message",description}};
    emit changed();emit operationChanged();return true;
}
void Mobile::readProfile(const QString &path,std::function<void(bool,Settings,quint64)> done){
    call(NM,path,PROPS,"GetAll",{CI},[this,path,done](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage||r.arguments().isEmpty()){done(false,{},0);return;}
        const auto props=qdbus_cast<QVariantMap>(r.arguments()[0]);
        const auto version=props.value("VersionId").toULongLong();
        if(!version){done(false,{},0);return;} // No unsafe write fallback on older backends.
        call(NM,path,CI,"GetSettings",{},[this,path,done,version](const QDBusMessage &r){
            if(r.type()==QDBusMessage::ErrorMessage||r.arguments().isEmpty()){done(false,{},0);return;}
            const auto settings=qdbus_cast<Settings>(r.arguments()[0]);
            call(NM,path,PROPS,"GetAll",{CI},[settings,done,version](const QDBusMessage &r){
                if(r.type()==QDBusMessage::ErrorMessage||r.arguments().isEmpty()||qdbus_cast<QVariantMap>(r.arguments()[0]).value("VersionId").toULongLong()!=version){done(false,{},0);return;}
                done(true,settings,version);
            });
        });
    });
}
QVariantMap Mobile::profileFields(const QString &path,const Settings &s,quint64 version)const{
    const auto c=s.value("connection"),g=s.value("gsm"),v4=s.value("ipv4"),v6=s.value("ipv6");
    QString ip=v4.value("method").toString()=="disabled"?"IPv6":v6.value("method").toString()=="disabled"?"IPv4":"IPv4 + IPv6";
    return {{"path",path},{"version",QString::number(version)},{"uuid",c.value("uuid")},{"name",c.value("id")},{"apn",g.value("apn")},
        {"username",g.value("username",QString())},{"auth",auth(s)},{"ipType",ip},{"autoconnect",c.value("autoconnect",true)},
        {"priority",c.value("autoconnect-priority",0)},{"metric",v4.value("route-metric",qint64(-1))},
        {"roaming",!g.value("home-only").toBool()},{"internetRoute",!v4.value("never-default").toBool()||!v6.value("never-default").toBool()},
        {"dns4",dns(v4,false).join(", ")},{"dns6",dns(v6,true).join(", ")},
        {"manualDns",v4.value("ignore-auto-dns").toBool()||v6.value("ignore-auto-dns").toBool()},
        {"operatorCode",g.value("network-id",QString())},{"active",path==m_activeProfile},{"password",QString()}};
}
void Mobile::editConfiguration(const QString &path,bool duplicate){
    if(!beginOperation("Reading saved profile…"))return;
    if(path.isEmpty()){
        m_editBaseline.clear();m_editVersion=0;m_editPath.clear();m_duplicate=false;
        m_editor={{"path",""},{"name",""},{"apn",""},{"username",""},{"auth","Automatic"},{"ipType","IPv4 + IPv6"},
            {"autoconnect",false},{"priority",0},{"metric",900},{"roaming",false},{"internetRoute",false},{"manualDns",false},{"dns4",""},{"dns6",""},{"password",""}};
        result("Ready","New profile; nothing has been saved.");emit editorChanged();return;
    }
    if(!knownProfile(path)){result("Verification failed","Profile is no longer accessible. Refresh the list.");return;}
    readProfile(path,[this,path,duplicate](bool ok,Settings settings,quint64 version){
        if(!ok||settings.value("connection").value("type")!="gsm"){result("Unsupported","Cannot read a stable, versioned GSM profile. No configuration changed.");return;}
        m_editBaseline=settings;m_editVersion=version;m_editPath=path;m_duplicate=duplicate;
        m_editor=profileFields(path,settings,version);
        if(duplicate){m_editor["path"]="";m_editor["name"]=m_editor.value("name").toString()+" (copy)";m_editor["autoconnect"]=false;}
        result("Ready",duplicate?"Duplicate draft; credentials will be copied through NetworkManager only when saved.":"Saved configuration read. Passwords remain hidden.");emit editorChanged();
    });
}
void Mobile::saveConfiguration(const QVariantMap &f){
    if(!beginOperation("Saving and verifying configuration…"))return;
    const auto path=f.value("path").toString(),name=f.value("name").toString().trimmed(),apn=f.value("apn").toString().trimmed();
    if(name.isEmpty()||name.size()>80||!Policy::validApn(apn)||f.value("username").toString().size()>256||f.value("password").toString().size()>1024){result("Verification failed","Check the profile name, carrier APN and credential lengths.");return;}
    if(!path.isEmpty()&&f.value("changePassword").toBool()&&f.value("password").toString().isEmpty()){result("Unsupported","Use Clear stored secrets for explicit credential removal, or enter a non-empty replacement password.");return;}
    if(!QStringList{"Automatic","PAP","CHAP","PAP or CHAP"}.contains(f.value("auth").toString())||!QStringList{"IPv4","IPv6","IPv4 + IPv6"}.contains(f.value("ipType").toString())){result("Unsupported","Unsupported authentication or IP family.");return;}
    if(path!=(m_duplicate?QString():m_editPath)||(!path.isEmpty()&&f.value("version").toString()!=QString::number(m_editVersion))){result("Verification failed","The editor revision is stale. Reload the profile.");return;}
    if(f.value("priority").toInt() < -999||f.value("priority").toInt()>999||f.value("metric").toLongLong() < -1||f.value("metric").toLongLong()>4294967295LL){result("Verification failed","Priority or route metric is outside the supported range.");return;}
    Settings desired=m_editBaseline;
    const auto *account=getpwuid(getuid());if(!account){result("Permission denied","Cannot identify the current account.");return;}
    if(path.isEmpty()){
        desired["connection"]["uuid"]=QUuid::createUuid().toString(QUuid::WithoutBraces);
        desired["connection"]["permissions"]=QStringList{"user:"+QString::fromLocal8Bit(account->pw_name)+":"};
        desired["connection"].remove("interface-name");desired["connection"].remove("timestamp");
    }
    desired["connection"]["id"]=name;desired["connection"]["type"]="gsm";
    desired["connection"]["autoconnect"]=f.value("autoconnect").toBool();desired["connection"]["autoconnect-retries"]=1;
    desired["connection"]["autoconnect-priority"]=f.value("priority").toInt();
    desired["gsm"]["apn"]=apn;desired["gsm"]["username"]=f.value("username").toString();
    if(desired["gsm"]["username"].toString().isEmpty())desired["gsm"].remove("username");
    desired["gsm"]["home-only"]=!f.value("roaming").toBool();desired["gsm"]["auto-config"]=false;
    const auto a=f.value("auth").toString();
    for(const auto &method:QStringList{"eap","pap","chap","mschap","mschapv2"})
        desired["ppp"]["refuse-"+method]=a!="Automatic" && !((method=="pap"&&(a=="PAP"||a=="PAP or CHAP"))||(method=="chap"&&(a=="CHAP"||a=="PAP or CHAP")));
    for(bool v6:{false,true}){
        const auto key=v6?QString("ipv6"):QString("ipv4");auto &p=desired[key];
        bool disabled=f.value("ipType")== (v6?"IPv4":"IPv6");
        // Modifying static/VPN-like GSM settings through this automatic editor
        // would destroy unrelated routes/addresses. Require a separate profile.
        const auto old=p.value("method").toString();
        if(!old.isEmpty()&&old!="auto"&&old!="disabled"){result("Unsupported","This profile has custom IP configuration. Duplicate or use its original editor.");return;}
        p["method"]=disabled?"disabled":"auto";p["never-default"]=!f.value("internetRoute").toBool();p["route-metric"]=qint64(f.value("metric",900).toLongLong());
        p["ignore-auto-dns"]=f.value("manualDns").toBool();
        QList<quint32> dns4;QList<QByteArray> dns6;
        const auto input=f.value(v6?"dns6":"dns4").toString().split(QRegularExpression("[,;\\s]+"),Qt::SkipEmptyParts);
        for(const auto &entry:input){QHostAddress address(entry);if(address.isNull()||address.protocol()!=(v6?QAbstractSocket::IPv6Protocol:QAbstractSocket::IPv4Protocol)){result("Verification failed","DNS entries must be IP addresses of the matching family.");return;}
            if(v6){auto bytes=address.toIPv6Address();dns6<<QByteArray(reinterpret_cast<const char*>(bytes.c),16);}else dns4<<qToBigEndian(address.toIPv4Address());}
        p.remove("dns-data");p["dns"]=v6?QVariant::fromValue(dns6):QVariant::fromValue(dns4);
        if(disabled){p.remove("dns");p["ignore-auto-dns"]=false;}
    }
    auto write=[this,path,desired,f](Settings previous)mutable{
        if(f.value("changePassword").toBool())desired["gsm"]["password"]=f.value("password").toString();
        else if(previous.value("gsm").contains("password"))desired["gsm"]["password"]=previous.value("gsm").value("password");
        if(desired.value("gsm").value("password").toString().isEmpty())desired["gsm"].remove("password");
        desired["gsm"]["password-flags"]=quint32(0); // NetworkManager-owned protected storage.
        writeVerified(path,desired,path.isEmpty()?0:m_editVersion,path.isEmpty()?Settings{}:previous);
    };
    if(m_editPath.isEmpty()){write({});return;}
    const auto source=m_editPath;
    readProfile(source,[this,source,write](bool ok,Settings previous,quint64 version){
        if(!ok||version!=m_editVersion){result("Verification failed","Profile changed externally. Reload before saving; nothing was overwritten.");return;}
        call(NM,source,CI,"GetSecrets",{QString("gsm")},[this,source,previous,write](const QDBusMessage &r)mutable{
            const auto publicBefore=canonical(previous);
            if(r.type()==QDBusMessage::ErrorMessage&&!r.errorName().endsWith(".NoSecrets")){result("Permission denied","Existing credentials cannot be preserved ("+r.errorName()+"). No profile changed.");return;}
            if(r.type()!=QDBusMessage::ErrorMessage&&!r.arguments().isEmpty()){
                const auto secrets=qdbus_cast<Settings>(r.arguments()[0]).value("gsm");
                for(auto i=secrets.cbegin();i!=secrets.cend();++i)previous["gsm"][i.key()]=i.value();
            }
            readProfile(source,[this,previous,publicBefore,write](bool ok,Settings current,quint64 version)mutable{
                if(!ok||canonical(current)!=publicBefore){result("Verification failed","Configuration changed while credentials were read. Nothing was overwritten.");return;}
                m_editVersion=version;
                write(previous);
            });
        },true);
    });
}
void Mobile::writeVerified(const QString &path,Settings desired,quint64 version,Settings previous,bool rollback){
    QVariantList args;QString method,target;
    if(path.isEmpty()){method="AddConnection";target=NP+"/Settings";args={QVariant::fromValue(desired)};}
    else{method="Update2";target=path;args={QVariant::fromValue(desired),quint32(0x41),QVariantMap{{"version-id",QVariant::fromValue(qulonglong(version))}}};}
    call(NM,target,path.isEmpty()?NM+".Settings":CI,method,args,[this,path,desired,previous,rollback](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){const auto field=QRegularExpression("^([a-z0-9-]+\\.[a-z0-9-]+):").match(r.errorMessage()).captured(1);result(r.errorName().contains("Permission")||r.errorName().contains("Authoriz")?"Permission denied":"Verification failed","Save could not be confirmed ("+r.errorName()+")."+(field.isEmpty()?QString():" Check field: "+field+".")+" Reload before retrying; a timed-out write may have completed.");fetchProfiles();return;}
        const auto savedPath=path.isEmpty()?qvariant_cast<QDBusObjectPath>(r.arguments().value(0)).path():path;
        readProfile(savedPath,[this,savedPath,desired,previous,rollback](bool ok,Settings actual,quint64){
            auto expected=profileFields(savedPath,desired,0),observed=profileFields(savedPath,actual,0);
            expected.remove("active");observed.remove("active");
            if(!ok||expected!=observed){result("Verification failed","The profile write returned, but read-back differs. Reopen the profile before applying it.");fetchProfiles();return;}
            auto complete=[this,savedPath,actual,previous,rollback]{
                // NM may update its profile revision while resolving/caching
                // secrets. Capture the FINAL version after secret verification.
                readProfile(savedPath,[this,savedPath,actual,previous,rollback](bool ok,Settings latest,quint64 finalVersion){
                    if(!ok||profileFields(savedPath,latest,0)!=profileFields(savedPath,actual,0)){result("Verification failed","Profile changed during final verification. Reopen it before applying.");return;}
                    if(!rollback&&!previous.isEmpty()){m_rollbackPath=savedPath;m_rollbackSettings=previous;m_rollbackVersion=finalVersion;}
                    else{m_rollbackPath.clear();m_rollbackSettings.clear();}
                    m_editPath=savedPath;m_editBaseline=latest;m_editVersion=finalVersion;m_duplicate=false;
                    m_settings.insert(savedPath,latest);
                    m_editor=profileFields(savedPath,latest,finalVersion);
                    result("Saved",rollback?"Previous profile restored and verified. The active session was not reconfigured.":"Saved to NetworkManager and verified by read-back. Active session settings are separate.");
                    emit editorChanged();fetchProfiles();
                });
            };
            call(NM,savedPath,CI,"GetSecrets",{QString("gsm")},[this,desired,complete](const QDBusMessage &s){
                const auto expected=desired.value("gsm").value("password").toString();
                const bool absent=s.type()==QDBusMessage::ErrorMessage&&s.errorName().endsWith(".NoSecrets")&&expected.isEmpty();
                if(!absent&&(s.type()==QDBusMessage::ErrorMessage||s.arguments().isEmpty()||qdbus_cast<Settings>(s.arguments()[0]).value("gsm").value("password").toString()!=expected)){
                    result("Verification failed","Saved credentials could not be verified. They were not logged or displayed.");return;}
                complete();
            },true);
        });
    },true);
}
void Mobile::deleteConfiguration(const QString &path,const QString &version){
    if(!knownProfile(path)||!beginOperation("Checking profile before deletion…"))return;
    if(path==m_activeProfile){result("Verification failed","Disconnect this profile before deleting it.");return;}
    readProfile(path,[this,path,version](bool ok,Settings,quint64 actual){
        if(!ok||QString::number(actual)!=version){result("Verification failed","Profile changed externally. Reload before deleting.");return;}
        call(NM,path,CI,"Delete",{},[this,path](const QDBusMessage &r){
            if(r.type()==QDBusMessage::ErrorMessage){result("Permission denied","Deletion rejected ("+r.errorName()+").");return;}
            call(NM,path,CI,"GetSettings",{},[this,path](const QDBusMessage &r){
                if(r.type()!=QDBusMessage::ErrorMessage){result("Verification failed","Profile still exists after deletion.");return;}
                if(path==m_rollbackPath){m_rollbackPath.clear();m_rollbackSettings.clear();}
                result("Saved","Profile removal verified.");fetchProfiles();
            });
        },true);
    });
}
void Mobile::rollbackConfiguration(){
    if(m_rollbackPath.isEmpty()||!beginOperation("Checking saved revision before rollback…"))return;
    readProfile(m_rollbackPath,[this](bool ok,Settings,quint64 version){
        if(!ok||version!=m_rollbackVersion){result("Verification failed","Rollback refused: another process changed this profile. No values were restored.");return;}
        writeVerified(m_rollbackPath,m_rollbackSettings,version,{},true);
    });
}
void Mobile::clearConfigurationSecrets(const QString &path,const QString &version){
    if(!knownProfile(path)||!beginOperation("Checking profile before clearing its stored secrets…"))return;
    if(path==m_activeProfile){result("Verification failed","Disconnect this profile before clearing its secrets.");return;}
    readProfile(path,[this,path,version](bool ok,Settings previous,quint64 actual){
        if(!ok||QString::number(actual)!=version){result("Verification failed","Profile changed externally. Reopen before clearing secrets.");return;}
        for(auto group=previous.cbegin();group!=previous.cend();++group)if(!QStringList{"connection","gsm","ppp","ipv4","ipv6","proxy","serial"}.contains(group.key())){result("Unsupported","This profile contains additional settings. Use its original editor to clear secrets safely.");return;}
        call(NM,path,CI,"GetSecrets",{QString("gsm")},[this,path,previous](const QDBusMessage &r)mutable{
            if(r.type()==QDBusMessage::ErrorMessage){result("Permission denied","Cannot preserve credentials before clearing them.");return;}
            const auto publicBefore=previous;
            const auto secrets=qdbus_cast<Settings>(r.arguments().value(0));
            for(auto group=secrets.cbegin();group!=secrets.cend();++group)for(auto field=group.value().cbegin();field!=group.value().cend();++field)previous[group.key()][field.key()]=field.value();
            readProfile(path,[this,path,previous,publicBefore](bool ok,Settings current,quint64){
                if(!ok||canonical(current)!=canonical(publicBefore)||path==m_activeProfile){result("Verification failed","Profile changed before clearing secrets. Nothing was cleared.");return;}
                call(NM,path,CI,"ClearSecrets",{},[this,path,previous](const QDBusMessage &r){
                    if(r.type()==QDBusMessage::ErrorMessage){result("Permission denied","Stored secrets could not be cleared.");return;}
                    call(NM,path,CI,"GetSecrets",{QString("gsm")},[this,path,previous](const QDBusMessage &r){
                        const bool absent=r.type()==QDBusMessage::ErrorMessage&&r.errorName().endsWith(".NoSecrets");
                        const auto secrets=qdbus_cast<Settings>(r.arguments().value(0));bool empty=true;for(auto i=secrets.cbegin();i!=secrets.cend();++i)empty&=i.value().isEmpty();
                        if(!absent&&(r.type()==QDBusMessage::ErrorMessage||!empty)){result("Verification failed","Stored secret removal could not be verified.");return;}
                        readProfile(path,[this,path,previous](bool ok,Settings current,quint64 version){
                            if(!ok){result("Verification failed","Cannot read the final profile revision.");return;}
                            m_rollbackPath=path;m_rollbackSettings=previous;m_rollbackVersion=version;
                            m_editPath=path;m_editBaseline=current;m_editVersion=version;m_duplicate=false;m_editor=profileFields(path,current,version);
                            result("Saved","All stored profile secrets cleared and verified. The SIM PIN itself was not changed.");emit editorChanged();fetchProfiles();
                        });
                    },true);
                },true);
            });
        },true);
    });
}
void Mobile::restoreProviderDefaults(){
    result("Unsupported","No verified provider database adapter is installed. Existing carrier profiles are preserved; enter settings supplied by your carrier.");
}
void Mobile::changeProfilePreferences(const QString &path,const QString &version,bool autoconnect,bool roaming){
    if(!knownProfile(path)||!beginOperation("Reading saved policy before changing it…"))return;
    readProfile(path,[this,path,version,autoconnect,roaming](bool ok,Settings settings,quint64 actual){
        if(!ok||QString::number(actual)!=version){result("Verification failed","The saved policy changed externally. Refresh before editing.");return;}
        m_editPath=path;m_editVersion=actual;m_editBaseline=settings;m_duplicate=false;
        auto fields=profileFields(path,settings,actual);fields["autoconnect"]=autoconnect;fields["roaming"]=roaming;
        m_busy=false;saveConfiguration(fields);
    });
}
