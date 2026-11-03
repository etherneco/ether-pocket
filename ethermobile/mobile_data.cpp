#include "mobile.h"
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDateTime>
#include <QDBusVariant>

namespace {
const QString SD="org.freedesktop.systemd1", SP="/org/freedesktop/systemd1", PROPS="org.freedesktop.DBus.Properties";
QString textFile(const QString &path){QFile f(path);return f.open(QIODevice::ReadOnly)?QString::fromUtf8(f.readAll()).trimmed():QString();}
}

void Mobile::fetchIpaData(){
    if(!m_ipa || m_dataFetching)return;
    m_dataFetching=true;
    QFile f("/run/ethermobile-data-status.json");
    m_dataState.clear();
    if(f.open(QIODevice::ReadOnly)&&f.size()<65536){
        const auto data=QJsonDocument::fromJson(f.readAll()).object();
        if(data.value("schema").toInt()==1&&data.value("boot").toString()==textFile("/proc/sys/kernel/random/boot_id"))m_dataState=data.toVariantMap();
    }
    const QString path=SP+"/unit/ethermobile_2ddata_2eservice";
    call(SD,path,PROPS,"GetAll",{SD+".Unit"},[this,path](const QDBusMessage &r){
        m_dataUnit=r.type()==QDBusMessage::ErrorMessage?QVariantMap{{"ActiveState","unavailable"}}:qdbus_cast<QVariantMap>(r.arguments().value(0));
        call(SD,path,PROPS,"GetAll",{SD+".Service"},[this](const QDBusMessage &s){
            m_dataMainPid=s.type()==QDBusMessage::ErrorMessage?0:qdbus_cast<QVariantMap>(s.arguments().value(0)).value("MainPID").toUInt();
            m_dataFetching=false;
            recompute();
            if(m_ipaOperation&&m_status.value("dataError").toBool()){
                m_ipaOperation=false;
                result("Błąd połączenia",m_status.value("dataMessage").toString()+"\n"+m_status.value("dataErrorDetail").toString());
            }
        });
    });
}

void Mobile::mergeIpaData(){
    const auto unit=m_dataUnit.value("ActiveState").toString();
    const auto state=m_dataState.value("state").toString();
    const bool active=unit=="active"&&state=="connected"&&m_dataMainPid&&m_dataState.value("pid").toUInt()==m_dataMainPid&&QFile::exists("/sys/class/net/epcell0");
    const bool pending=unit=="activating"||(unit=="active"&&state=="connecting")||(m_ipaOperation&&m_connectionTarget==1&&!active&&unit!="failed");
    const bool stopping=unit=="deactivating";
    const bool failed=!active&&(unit=="failed"||(!pending&&state=="failed"));
    QString message=m_dataState.value("message").toString();
    QString detail=m_dataState.value("detail").toString();
    if(stopping)message="Rozłączam transmisję danych i zwalniam sesję modemu…";
    else if(pending&&(state=="failed"||message.isEmpty()))message="Próbuję połączyć: czekam na uruchomienie usługi transmisji danych…";
    else if(failed&&message.isEmpty())message="Usługa transmisji danych nie uruchomiła się. Sprawdź modem i interfejs IPA.";
    else if(!active&&!pending&&unit=="inactive")message="Transmisja danych rozłączona.";
    else if(unit=="unavailable")message="Brak usługi ethermobile-data. Nie można odczytać stanu ani rozpocząć połączenia.";
    if(!active&&!pending&&detail.isEmpty()&&unit=="active")detail="Usługa działa, ale nie potwierdzono gotowej sesji IP. Brak aktualnego statusu adaptera.";
    m_status["dataProvider"]="downstream-ipa";
    m_status["dataActive"]=active;m_status["dataPending"]=pending;m_status["dataStopping"]=stopping;m_status["dataError"]=failed;
    m_status["canDisconnect"]=active||pending;
    m_status["canConnect"]=m_status.value("available").toBool()&&!active&&!pending&&!stopping&&unit!="unavailable";
    m_status["state"]=active?"Połączono":pending?"Łączenie…":stopping?"Rozłączanie…":failed?"Błąd połączenia":"Rozłączono";
    m_status["dataMessage"]=message;m_status["dataErrorDetail"]=detail;m_status["dataErrorCode"]=m_dataState.value("code");
    m_status["dataStage"]=m_dataState.value("stage");m_status["dataHistory"]=m_dataState.value("history",QVariantList{});
    m_status["dataStarted"]=m_dataState.value("started");m_status["dataApn"]=m_dataState.value("apn","giffgaff.com");
    m_status["hasIp"]=active;m_status["interface"]=active?"epcell0":"";
    if(active){
        QVariantList addresses{QVariantMap{{"address",m_dataState.value("address")}}};
        QVariantList dns;for(const auto &v:m_dataState.value("dns").toList())dns<<QVariantMap{{"address",v}};
        m_status["network"]=QVariantMap{{"ipv4",QVariantMap{{"addresses",addresses},{"gateway",m_dataState.value("gateway")},{"dns",dns}}}};
        for(const auto &v:m_profiles)if(v.toMap().value("apn").toString()=="giffgaff.com"){m_status["activeProfile"]=v.toMap().value("path");break;}
    }
    m_status["explanation"]="Modem używa adaptera IPA. Standardowy ModemManager odrzuca ten sterownik QMI (Unsupported QMI kernel driver). Stan i przyciski korzystają z usługi ethermobile-data.";
}

void Mobile::ipaDataAction(bool connect,const QString &profile){
    if(busy())return;
    if(connect){
        if(!knownProfile(profile)){result("Błąd połączenia","Wybierz zapisany profil APN.");return;}
        if(m_settings.value(profile).value("gsm").value("apn").toString().compare("giffgaff.com",Qt::CaseInsensitive)!=0){
            result("Nieobsługiwany profil","Adapter IPA jest skonfigurowany dla APN giffgaff.com. Nie uruchomiono innego profilu.");return;
        }
        for(const auto &v:m_profiles)if(v.toMap().value("path")==profile&&v.toMap().value("ipType").toString().compare("IPv6",Qt::CaseInsensitive)==0){
            result("Nieobsługiwany profil","Ten adapter obsługuje sesję IPv4. Profil wyłącznie IPv6 nie może zostać uruchomiony.");return;
        }
        if(m_status.value("roaming").toBool()){result("Błąd połączenia","Adapter IPA blokuje połączenie w roamingu.");return;}
    }
    if(!beginOperation(connect?"Próbuję połączyć: przekazuję żądanie do usługi danych IPA…":"Rozłączam sesję danych IPA…"))return;
    m_ipaOperation=true;m_connectionTarget=connect?1:0;
    recompute();
    call(SD,SP,SD+".Manager",connect?"StartUnit":"StopUnit",{"ethermobile-data.service","replace"},[this,connect](const QDBusMessage &r){
        if(r.type()==QDBusMessage::ErrorMessage){
            m_ipaOperation=false;
            result("Błąd połączenia","Nie można "+QString(connect?"uruchomić":"zatrzymać")+" usługi danych ("+r.errorName()+"). Sprawdź uprawnienia i instalację usługi.");return;
        }
        m_verify=[this,connect]{return connect?m_status.value("dataActive").toBool():!m_status.value("dataActive").toBool()&&!m_status.value("dataPending").toBool()&&!m_status.value("dataStopping").toBool()&&m_dataUnit.value("ActiveState")=="inactive";};
        m_operationTimeout.start(connect?160000:45000);fetchIpaData();
    },true,20000);
}
