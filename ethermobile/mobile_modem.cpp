#include "mobile.h"
#include "policy.h"
#include <QDBusMetaType>
#include <QRegularExpression>
#include <QJsonDocument>

namespace {const QString MM="org.freedesktop.ModemManager1",MI=MM+".Modem", NM="org.freedesktop.NetworkManager",NP="/org/freedesktop/NetworkManager";}
void Mobile::finishObservedOperation(){
    if(!m_verify||!m_verify())return;
    m_verify={};
    if(m_ipaOperation){m_ipaOperation=false;result("Gotowe",m_connectionTarget==1?"Połączono przez adapter IPA. Adres IP, brama i DNS są gotowe.":"Transmisja danych rozłączona.");return;}
    if(!m_reconnectProfile.isEmpty()){
        const auto profile=m_reconnectProfile;m_reconnectProfile.clear();m_busy=false;m_operationTimeout.stop();connectProfile(profile);return;
    }
    result("Applied","Effective state verified from the backend. Internet access is a separate test.");
}
void Mobile::monitorConnection(bool connected){
    m_connectionTarget=connected?1:0;
    m_verify=[this,connected]{return connected?(m_activeProfile==m_activationProfile&&m_nmActivated&&m_hasIp&&m_status.value("dataActive").toBool()):(m_active.isEmpty()&&(m_reconnectProfile.isEmpty()||m_status.value("canConnect").toBool()));};
    m_operationTimeout.start(90000);refresh();
}
void Mobile::reconnectProfile(const QString &path){
    if(m_ipa){if(m_status.value("dataActive").toBool()){result("Najpierw rozłącz","Wyłącz transmisję danych IPA, a następnie uruchom wybrany profil ponownie.");return;}connectProfile(path);return;}
    if(!knownProfile(path)||busy())return;
    if(m_active.isEmpty()){connectProfile(path);return;}
    m_previousConnectionProfile=m_activeProfile;m_previousConnectionVersion=0;
    for(const auto &v:m_profiles)if(v.toMap().value("path").toString()==m_activeProfile)m_previousConnectionVersion=v.toMap().value("version").toString().toULongLong();
    m_reconnectProfile=path;disconnectData();
}
void Mobile::rollbackConnection(){
    if(busy())return;
    if(!m_active.isEmpty()||m_previousConnectionProfile.isEmpty()||!m_previousConnectionVersion){result("Verification failed","A new active session or missing previous revision prevents connection rollback.");return;}
    if(!beginOperation("Checking the previous APN before reconnecting…"))return;
    readProfile(m_previousConnectionProfile,[this](bool ok,Settings,quint64 version){
        if(!ok||version!=m_previousConnectionVersion||!m_active.isEmpty()){result("Verification failed","The previous profile or active connection changed. Rollback was refused.");return;}
        const auto path=m_previousConnectionProfile;m_busy=false;connectProfile(path);
    });
}
void Mobile::simAction(const QString &action,const QString &first,const QString &second){
    if(busy())return;
    if(m_sim.isEmpty()||m_sim=="/"||!m_status.value("available").toBool()){result("Unsupported","No accessible SIM is exported by the modem.");return;}
    const auto validPin=[](const QString &s){return QRegularExpression("^[0-9]{4,8}$").match(s).hasMatch();};
    QString method;QVariantList args;
    if(action=="pin"&&m_status.value("pinRequired").toBool()&&validPin(first)){method="SendPin";args={first};}
    else if(action=="puk"&&m_status.value("unlockRequired").toUInt()==4&&QRegularExpression("^[0-9]{8}$").match(first).hasMatch()&&validPin(second)){method="SendPuk";args={first,second};}
    else if((action=="enable"||action=="disable")&&m_status.value("simReady").toBool()&&validPin(first)){method="EnablePin";args={first,action=="enable"};}
    else if(action=="change"&&m_status.value("simReady").toBool()&&validPin(first)&&validPin(second)){method="ChangePin";args={first,second};}
    else{result("Verification failed","The SIM state or code format does not permit that operation. No attempt was sent.");return;}
    if(!beginOperation("Sending one explicit SIM request…"))return;
    call(MM,m_sim,MM+".Sim",method,args,[this,action](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result(r.errorName().contains("Unsupported")?"Unsupported":"Verification failed","SIM request failed ("+r.errorName()+"). Do not guess or automatically retry codes.");refresh();return;}
        if(action=="change"){result("Applied","The SIM accepted the PIN change. No additional verification attempt was made.");refresh();return;}
        m_verify=[this,action]{return action=="enable"?m_status.value("pinLock").toBool():action=="disable"?!m_status.value("pinLock").toBool():m_status.value("simReady").toBool();};
        m_operationTimeout.start(20000);refresh();
    },true,30000);
}
void Mobile::scanOperators(){
    if(busy())return;
    if(!m_status.value("canScan").toBool()){result("Unsupported","This modem has no available 3GPP network selection interface.");return;}
    if(!beginOperation("Scanning real networks; existing cellular service may be interrupted…"))return;
    m_operators.clear();emit changed();
    call(MM,m_selected,MI+".Modem3gpp","Scan",{},[this](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result(r.errorName().contains("Unsupported")?"Unsupported":"Verification failed","Network scan failed ("+r.errorName()+"). No results were invented.");return;}
        const auto rows=qdbus_cast<QList<QVariantMap>>(r.arguments().value(0));
        for(const auto &row:rows)m_operators<<QVariantMap{{"name",row.value("operator-long",row.value("operator-short","Unknown"))},
            {"code",row.value("operator-code")},{"technology",Policy::technology(row.value("access-technology").toUInt())},
            {"availability",row.value("status")}};
        result("Applied","Network scan completed. Select an operator explicitly to request registration.");
    },true,120000);
}
void Mobile::registerOperator(const QString &code){
    if(busy())return;
    if(!m_status.value("canScan").toBool()||(!code.isEmpty()&&!QRegularExpression("^[0-9]{5,6}$").match(code).hasMatch())){result("Unsupported","Select an available operator or automatic registration.");return;}
    if(!code.isEmpty()){
        bool found=false;for(const auto &row:m_operators)if(row.toMap().value("code").toString()==code&&row.toMap().value("availability").toUInt()!=3)found=true;
        if(!found){result("Verification failed","Run a scan and select a non-forbidden operator from its results.");return;}
    }
    if(!beginOperation("Requesting network registration…"))return;
    call(MM,m_selected,MI+".Modem3gpp","Register",{code},[this,code](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result("Verification failed","Registration rejected ("+r.errorName()+").");refresh();return;}
        m_verify=[this,code]{auto state=m_status.value("registration").toUInt();return (state==1||state==5)&&(code.isEmpty()||m_status.value("operatorCode").toString()==code);};
        m_operationTimeout.start(90000);refresh();
    },true,90000);
}
void Mobile::applyMode(const QString &id){
    if(busy())return;
    RadioMode requested;bool supported=false;
    for(const auto &v:m_modes){auto row=v.toMap();if(row.value("id").toString()==id){requested={row.value("allowed").toUInt(),row.value("preferred").toUInt()};supported=true;}}
    if(!supported||(requested.allowed&16)){result("Unsupported","This mode is not in the current modem's exposed non-NR mode list.");return;}
    if(!beginOperation("Applying a supported radio mode…"))return;
    const auto p=m_objects.value(QDBusObjectPath(m_selected)).value(MI);
    const auto previous=qdbus_cast<RadioMode>(p.value("CurrentModes"));
    call(MM,m_selected,MI,"SetCurrentModes",{QVariant::fromValue(requested)},[this,requested,previous](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result(r.errorName().contains("Unsupported")?"Unsupported":"Verification failed","Radio mode was rejected ("+r.errorName()+"). No automatic fallback was applied.");return;}
        m_previousMode=previous;m_appliedMode=requested;m_modeRollback=true;
        m_verify=[this,requested]{return m_status.value("currentMode").toString()==QString::number(requested.allowed)+"/"+QString::number(requested.preferred);};
        m_operationTimeout.start(30000);refresh();
    },true,45000);
}
void Mobile::rollbackMode(){
    if(busy())return;
    const auto actual=qdbus_cast<RadioMode>(m_objects.value(QDBusObjectPath(m_selected)).value(MI).value("CurrentModes"));
    if(!m_modeRollback||actual.allowed!=m_appliedMode.allowed||actual.preferred!=m_appliedMode.preferred){result("Verification failed","The effective radio mode changed externally. Rollback refused.");return;}
    // Rollback may restore a previous backend-reported automatic mode, but never
    // exposes an NR-only mode in the UI or guesses an unsupported mode pair.
    bool exists=false;for(const auto &mode:qdbus_cast<QList<RadioMode>>(m_objects.value(QDBusObjectPath(m_selected)).value(MI).value("SupportedModes")))if(mode.allowed==m_previousMode.allowed&&mode.preferred==m_previousMode.preferred)exists=true;
    if(!exists||!beginOperation("Restoring previous effective radio mode…"))return;
    const auto old=m_previousMode;
    call(MM,m_selected,MI,"SetCurrentModes",{QVariant::fromValue(old)},[this,old](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result("Verification failed","The modem rejected radio-mode rollback.");return;}
        m_modeRollback=false;m_verify=[this,old]{return m_status.value("currentMode").toString()==QString::number(old.allowed)+"/"+QString::number(old.preferred);};m_operationTimeout.start(30000);refresh();
    },true,45000);
}
void Mobile::selectSimSlot(int slot){
    if(busy())return;
    if(!m_status.value("canSelectSlot").toBool()||slot<1||slot>m_status.value("slots").toInt()){result("Unsupported","Multiple usable SIM slots have not been exposed by this modem.");return;}
    const auto simPaths=qdbus_cast<QList<QDBusObjectPath>>(m_objects.value(QDBusObjectPath(m_selected)).value(MI).value("SimSlots"));
    if(slot>simPaths.size()||simPaths[slot-1].path()=="/"){result("Unsupported","That slot has no usable SIM exposed by the backend.");return;}
    if(!beginOperation("Selecting the SIM slot; the modem may temporarily disappear…"))return;
    call(MM,m_selected,MI,"SetPrimarySimSlot",{quint32(slot)},[this,slot](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){result("Unsupported","SIM slot selection was rejected ("+r.errorName()+").");return;}
        m_verify=[this,slot]{return m_status.value("simSlot").toInt()==slot&&m_status.value("available").toBool();};m_operationTimeout.start(60000);refresh();
    },true,60000);
}
