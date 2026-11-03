#pragma once
#include <QString>
#include <QRegularExpression>
#include <QDate>
namespace Policy {
inline bool countUsageDelta(bool sameInterface,bool sameDay,qint64 previous,qint64 now,quint64 rx,quint64 tx,quint64 oldRx,quint64 oldTx){
    return sameInterface&&sameDay&&previous>0&&now>=previous&&now-previous<=65000&&rx>=oldRx&&tx>=oldTx;
}
inline QDate billingStart(QDate today,int day){
    auto anchor=[day](QDate d){return QDate(d.year(),d.month(),qMin(qBound(1,day,31),d.daysInMonth()));};
    auto start=anchor(today);return start>today?anchor(today.addMonths(-1)):start;
}
inline bool validApn(const QString &s) {
    if(s.isEmpty() || s.size()>100) return false;
    const auto parts=s.split('.');
    for(const auto &p:parts)
        if(p.size()>63 || !QRegularExpression("^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$").match(p).hasMatch()) return false;
    return true;
}
inline QString state(int mm, bool bearer, bool activated, bool hasIp, bool roaming) {
    if(mm==-1) return "Failed";
    if(mm==2) return "Locked";
    if(mm==3) return "Disabled";
    if(mm==1 || mm==4 || mm==5) return "Initializing";
    if(mm==6) return "Searching · radio enabled";
    if(mm==7) return "Searching";
    if(mm==10) return "Connecting";
    if(mm==11 && bearer && activated && hasIp) return roaming ? "Connected · roaming" : "Connected";
    if(mm==11) return "Data session · IP not verified";
    if(mm==9) return "Disconnecting";
    if(mm==8) return roaming ? "Roaming" : "Registered";
    return "Not detected";
}
inline QString technology(quint32 t) {
    QStringList labels;
    if(t & (1u<<15)) labels << "5G NR";
    if(t & (1u<<14)) labels << "LTE";
    if(t & (1u<<16)) labels << "LTE Cat-M";
    if(t & (1u<<17)) labels << "LTE NB-IoT";
    if(t & ((1u<<6)|(1u<<7)|(1u<<8)|(1u<<9))) labels << "HSPA";
    else if(t & (1u<<5)) labels << "UMTS";
    if(t & ((1u<<1)|(1u<<2)|(1u<<3)|(1u<<4))) labels << "GSM/EDGE";
    if(t & ((1u<<10)|(1u<<11)|(1u<<12)|(1u<<13))) labels << "CDMA/EVDO";
    return labels.isEmpty()?QString("Unavailable"):labels.join(" + ");
}
}
