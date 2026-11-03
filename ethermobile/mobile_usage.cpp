#include "mobile.h"
#include "policy.h"
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>
#include <QStandardPaths>
#include <QJsonDocument>
#include <QJsonObject>
#include <QDir>
#include <QDate>
#include <QDateTime>
#include <QLockFile>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <cmath>

namespace {
QString location(){return QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)+"/ethermobile/usage.json";}
QString readText(const QString &path){QFile f(path);return f.open(QIODevice::ReadOnly)?QString::fromUtf8(f.readAll()).trimmed():QString();}
bool save(const QJsonObject &root){QSaveFile f(location());f.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);if(!f.open(QIODevice::WriteOnly))return false;f.write(QJsonDocument(root).toJson());return f.commit();}
}
void Mobile::sampleUsage(){
    const auto path=location();QDir().mkpath(QFileInfo(path).absolutePath());
    QLockFile lock(path+".lock");if(!lock.tryLock(0))return;
    auto root=QJsonDocument::fromJson(readText(path).toUtf8()).object();
    if(!root.isEmpty()&&root.value("schema").toInt()!=1){m_usage={{"available",false},{"note","Unknown history schema; existing history was preserved."}};emit usageChanged();return;}
    auto days=root.value("days").toObject();const auto options=root.value("options").toObject();
    const auto today=QDate::currentDate();const auto day=today.toString(Qt::ISODate);
    const auto usageInterface=m_status.value("interface").toString();
    const bool active=m_status.value("dataActive").toBool()&&!usageInterface.isEmpty()&&QRegularExpression("^[a-zA-Z0-9_.:-]+$").match(usageInterface).hasMatch();
    bool measured=false,reset=false;
    quint64 rx=0,tx=0;
    QString key;
    if(active){
        bool okRx=false,okTx=false;const auto base="/sys/class/net/"+usageInterface;
        rx=readText(base+"/statistics/rx_bytes").toULongLong(&okRx);tx=readText(base+"/statistics/tx_bytes").toULongLong(&okTx);
        key=QString::fromLatin1(QCryptographicHash::hash((readText("/proc/sys/kernel/random/boot_id")+":"+readText(base+"/ifindex")+":"+m_ipInterface).toUtf8(),QCryptographicHash::Sha256).toHex());
        if(okRx&&okTx){
            auto old=root.value("baseline").toObject();auto oldRx=old.value("rx").toString().toULongLong(),oldTx=old.value("tx").toString().toULongLong();
            const auto now=QDateTime::currentDateTimeUtc().toMSecsSinceEpoch();
            const auto previousTime=old.value("time").toString().toLongLong();
            if(Policy::countUsageDelta(old.value("key").toString()==key,old.value("day").toString()==day,previousTime,now,rx,tx,oldRx,oldTx)){
                auto totals=days.value(day).toObject();totals["rx"]=QString::number(totals.value("rx").toString().toULongLong()+rx-oldRx);totals["tx"]=QString::number(totals.value("tx").toString().toULongLong()+tx-oldTx);days[day]=totals;
            }else reset=true;
            root["schema"]=1;root["days"]=days;root["baseline"]=QJsonObject{{"key",key},{"rx",QString::number(rx)},{"tx",QString::number(tx)},{"day",day},{"time",QString::number(now)}};
            measured=save(root);
        }
    }
    const int billing=qBound(1,options.value("billingDay").toInt(1),31);
    const auto start=Policy::billingStart(today,billing);
    quint64 monthRx=0,monthTx=0;for(auto i=days.begin();i!=days.end();++i){auto date=QDate::fromString(i.key(),Qt::ISODate);if(date>=start&&date<=today){monthRx+=i.value().toObject().value("rx").toString().toULongLong();monthTx+=i.value().toObject().value("tx").toString().toULongLong();}}
    const auto daily=days.value(day).toObject();const double warning=options.value("warningMB").toDouble(0);
    const bool newSession=m_usage.value("counterKey").toString()!=key||reset;
    const quint64 baselineRx=newSession?rx:m_usage.value("baselineRx").toString().toULongLong(),baselineTx=newSession?tx:m_usage.value("baselineTx").toString().toULongLong();
    m_usage={{"available",measured},{"hasHistory",!days.isEmpty()},{"interface",m_ipInterface},{"counterKey",key},
        {"baselineRx",QString::number(baselineRx)},{"baselineTx",QString::number(baselineTx)},
        {"sessionRx",QString::number(rx>=baselineRx?rx-baselineRx:0)},{"sessionTx",QString::number(tx>=baselineTx?tx-baselineTx:0)},
        {"dailyRx",daily.value("rx").toString("0")},{"dailyTx",daily.value("tx").toString("0")},
        {"monthlyRx",QString::number(monthRx)},{"monthlyTx",QString::number(monthTx)},
        {"billingDay",billing},{"cycleStart",start.toString(Qt::ISODate)},{"warningMB",warning},{"warning",warning>0&&(monthRx+monthTx)>=warning*1000000.0},
        {"note","Local interface accounting while EtherMobile/EtherShell runs. Sampling gaps are excluded; resets start a new baseline. Session starts with this app's observed interface. These are not carrier-billed totals. No automatic disconnection."}};
    emit usageChanged();
}
void Mobile::setUsageOptions(int billingDay,double warningMegabytes){
    if(billingDay<1||billingDay>31||!std::isfinite(warningMegabytes)||warningMegabytes<0||warningMegabytes>1000000000){result("Verification failed","Check the billing day and warning threshold.");return;}
    const auto path=location();QDir().mkpath(QFileInfo(path).absolutePath());QLockFile lock(path+".lock");if(!lock.tryLock(0)){result("Verification failed","Usage history is busy. Try again.");return;}
    auto root=QJsonDocument::fromJson(readText(path).toUtf8()).object();if(!root.isEmpty()&&root.value("schema").toInt()!=1){result("Unsupported","Unknown usage history schema was preserved.");return;}
    root["schema"]=1;root["options"]=QJsonObject{{"billingDay",billingDay},{"warningMB",warningMegabytes}};
    if(!save(root)){result("Verification failed","Usage preferences could not be saved.");return;}
    lock.unlock();sampleUsage();result("Saved","Usage warning preferences saved. Warnings never disconnect data.");
}
