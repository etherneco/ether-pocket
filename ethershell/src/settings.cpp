#include "core.h"
#include "bluetooth.h"
#include <QFile>
#include <QDir>
#include <QStorageInfo>
#include <QSysInfo>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QRegularExpression>
#include <QStandardPaths>

namespace {QString readSettingFile(const QString &path){QFile f(path);return f.open(QIODevice::ReadOnly)?QString::fromUtf8(f.readAll()).remove(QChar(0)).trimmed():QString();}}
QObject *Core::bluetooth()const{return m_bluetooth;}
void Core::inspectSettings(const QString &page){
    if(page=="system"||page=="storage"||page=="security"||page=="power"||page=="devices"){
        QStorageInfo disk(QDir::homePath());
        m_settingsData["system"]=QVariantMap{{"device",readSettingFile("/proc/device-tree/model")},{"os",QSysInfo::prettyProductName()},
          {"kernel",QSysInfo::kernelVersion()},{"architecture",QSysInfo::currentCpuArchitecture()},{"cpu",readSettingFile("/proc/cpuinfo").section('\n',0,3)},
          {"memory",readSettingFile("/proc/meminfo").section('\n',0,2)},{"date",QDateTime::currentDateTime().toString(Qt::ISODate)},
          {"timezone",QDateTime::currentDateTime().timeZoneAbbreviation()}};
        m_settingsData["storage"]=QVariantMap{{"path",disk.rootPath()},{"type",QString::fromUtf8(disk.fileSystemType())},
          {"total",QString::number(disk.bytesTotal())},{"available",QString::number(disk.bytesAvailable())},{"valid",disk.isValid()}};
        emit settingsDataChanged();
    }
    if(page=="wifi"||page=="network"){
        run("nmcli",{"-t","-f","WIFI","general"},[this](int c,QString out){m_settingsData["wifiRadio"]=c?QString("Unavailable"):out;emit settingsDataChanged();},false);
        run("nmcli",{"-t","-f","GENERAL.DEVICE,GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,IP6.ADDRESS,IP6.GATEWAY,IP6.DNS","device","show"},[this](int c,QString out){
            QVariantList rows;bool wifi=false;for(auto line:out.split('\n')){
                auto key=line.section(':',0,0),value=line.section(':',1).replace("\\:",":");
                if(key=="GENERAL.DEVICE")wifi=value.startsWith("wlan")||value.startsWith("wlp");
                if(wifi&&!value.isEmpty())rows<<QVariantMap{{"title",key},{"value",value}};
            }m_settingsData["wifiDetails"]=rows;m_settingsData["wifiError"]=c?"NetworkManager device details unavailable":"";emit settingsDataChanged();
        },false);
        run("nmcli",{"-t","--escape","no","-f","UUID,TYPE,NAME","connection","show"},[this](int c,QString out){
            QVariantList rows;if(!c)for(auto line:out.split('\n')){const auto parts=line.split(':');if(parts.value(1)=="802-11-wireless")rows<<QVariantMap{{"uuid",parts[0]},{"name",parts.mid(2).join(':')}};}
            m_settingsData["savedWifi"]=rows;emit settingsDataChanged();
        },false);
    }
    if(page=="sound"){
        for(const auto &kind:QStringList{"sinks","sources"})run("pactl",{"-f","json","list",kind},[this,kind](int c,QString out){
            QVariantList rows;for(auto item:QJsonDocument::fromJson(out.toUtf8()).array()){
                auto v=item.toObject();rows<<QVariantMap{{"name",v["name"].toString()},{"description",v["description"].toString()},{"mute",v["mute"].toBool()}};
            }m_settingsData[kind]=rows;m_settingsData["audioError"]=c?"Audio service unavailable":"";emit settingsDataChanged();
        },false);
        for(const auto &kind:QStringList{"sink","source"})run("pactl",{"get-default-"+kind},[this,kind](int c,QString out){m_settingsData["default-"+kind]=c?"Unavailable":out;emit settingsDataChanged();},false);
    }
    if(page=="storage")run("lsblk",{"-J","-b","-o","NAME,SIZE,FSTYPE,MOUNTPOINTS,TYPE,RO"},[this](int c,QString out){QVariantList volumes;std::function<void(QJsonArray)> flatten=[&](QJsonArray rows){for(auto value:rows){auto row=value.toObject();volumes<<row.toVariantMap();flatten(row.value("children").toArray());}};if(!c)flatten(QJsonDocument::fromJson(out.toUtf8()).object().value("blockdevices").toArray());m_settingsData["volumes"]=volumes;emit settingsDataChanged();},false);
    if(page=="system")run("systemctl",{"list-units","--type=service","--state=running","--no-legend","--no-pager","--plain"},[this](int c,QString out){m_settingsData["services"]=c?"Service listing unavailable":out;emit settingsDataChanged();},false);
    if(page=="input"||page=="devices")run("xinput",{"list","--name-only"},[this](int c,QString out){m_settingsData["inputDevices"]=c?"Input service unavailable":out;emit settingsDataChanged();},false);
    if(page=="apps"){
        m_settingsData["startupEditorAvailable"]=!QStandardPaths::findExecutable("xfce4-session-settings").isEmpty();
        run("xdg-settings",{"get","default-web-browser"},[this](int c,QString out){m_settingsData["browser"]=c?"Unavailable":out;emit settingsDataChanged();},false);
        QVariantList startups;for(const auto &dir:QStringList{"/etc/xdg/autostart",QDir::homePath()+"/.config/autostart"})for(const auto &file:QDir(dir).entryList({"*.desktop"},QDir::Files))startups<<file;
        m_settingsData["startupApps"]=startups;emit settingsDataChanged();
    }
}
void Core::defaultBrowser(const QString &desktopId){
    bool known=false;for(auto row:m_apps){const auto app=row.toMap();known|=app.value("id").toString()==desktopId&&app.value("category").toString().contains("WebBrowser");}
    if(!known){status("Select an installed web browser.");return;}
    run("xdg-settings",{"set","default-web-browser",desktopId},[this,desktopId](int c,QString){if(c){status("Default browser request was rejected.");return;}run("xdg-settings",{"get","default-web-browser"},[this,desktopId](int c,QString out){status(!c&&out==desktopId?"Default browser saved and verified.":"Default browser verification failed.");inspectSettings("apps");},false);},false);
}
void Core::wifiProfileAction(const QString &uuid,const QString &action){
    if(!QRegularExpression("^[0-9a-fA-F-]{36}$").match(uuid).hasMatch()||!QStringList{"up","down","delete"}.contains(action))return;
    bool known=false;for(auto row:m_settingsData.value("savedWifi").toList())known|=row.toMap().value("uuid").toString()==uuid;
    if(!known){status("Wi-Fi profile changed. Refresh before applying.");return;}
    run("nmcli",{"--wait","30","connection",action,"uuid",uuid},[this](int c,QString){status(c?"Wi-Fi action failed. Check permissions and current connection.":"NetworkManager completed the request; checking effective state.");refresh();inspectSettings("wifi");},false);
}
void Core::audioDevice(const QString &kind,const QString &name){
    if(kind!="sink"&&kind!="source")return;bool known=false;
    for(auto row:m_settingsData.value(kind=="sink"?"sinks":"sources").toList())known|=row.toMap().value("name").toString()==name;
    if(!known){status("Audio device is no longer available.");return;}
    run("pactl",{"set-default-"+kind,name},[this,kind,name](int c,QString){
        if(c){status("Audio routing request was rejected.");return;}
        run("pactl",{"get-default-"+kind},[this,name](int c,QString out){status(!c&&out==name?"Audio device applied and verified.":"Audio routing verification failed.");inspectSettings("sound");},false);
    },false);
}

