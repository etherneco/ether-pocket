#pragma once
#include <QDBusArgument>
#include <QDBusObjectPath>
#include <QMap>
#include <QVariantMap>
using Settings = QMap<QString, QVariantMap>;
using ManagedObjects = QMap<QDBusObjectPath, Settings>;
Q_DECLARE_METATYPE(Settings)
Q_DECLARE_METATYPE(ManagedObjects)
struct RadioMode { quint32 allowed=0, preferred=0; };
Q_DECLARE_METATYPE(RadioMode)
Q_DECLARE_METATYPE(QList<RadioMode>)
struct ControlPort { QString name; quint32 type=0; };
Q_DECLARE_METATYPE(ControlPort)
Q_DECLARE_METATYPE(QList<ControlPort>)
inline QDBusArgument &operator<<(QDBusArgument &a,const ControlPort &p){a.beginStructure();a<<p.name<<p.type;a.endStructure();return a;}
inline const QDBusArgument &operator>>(const QDBusArgument &a,ControlPort &p){a.beginStructure();a>>p.name>>p.type;a.endStructure();return a;}
inline QDBusArgument &operator<<(QDBusArgument &a,const RadioMode &m){a.beginStructure();a<<m.allowed<<m.preferred;a.endStructure();return a;}
inline const QDBusArgument &operator>>(const QDBusArgument &a,RadioMode &m){a.beginStructure();a>>m.allowed>>m.preferred;a.endStructure();return a;}
inline QDBusArgument &operator<<(QDBusArgument &a, const Settings &v) {
    a.beginMap(QMetaType::fromType<QString>(), QMetaType::fromType<QVariantMap>());
    for(auto i=v.cbegin(); i!=v.cend(); ++i) { a.beginMapEntry(); a << i.key() << i.value(); a.endMapEntry(); }
    a.endMap(); return a;
}
inline const QDBusArgument &operator>>(const QDBusArgument &a, Settings &v) {
    v.clear(); a.beginMap(); while(!a.atEnd()) { QString k; QVariantMap x; a.beginMapEntry(); a >> k >> x; a.endMapEntry(); v.insert(k,x); } a.endMap(); return a;
}
inline QDBusArgument &operator<<(QDBusArgument &a, const ManagedObjects &v) {
    a.beginMap(QMetaType::fromType<QDBusObjectPath>(), QMetaType::fromType<Settings>());
    for(auto i=v.cbegin();i!=v.cend();++i) { a.beginMapEntry();a << i.key() << i.value();a.endMapEntry(); } a.endMap();return a;
}
inline const QDBusArgument &operator>>(const QDBusArgument &a, ManagedObjects &v) {
    v.clear();a.beginMap();while(!a.atEnd()) { QDBusObjectPath k;Settings x;a.beginMapEntry();a >> k >> x;a.endMapEntry();v.insert(k,x); }a.endMap();return a;
}
