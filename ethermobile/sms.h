#pragma once
#include <QObject>
#include <QVariantMap>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QSet>
#include <functional>
class Mobile;
bool smsCreationRejected(const QString &errorName);
class ISmsTransport : public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap capabilities READ capabilities NOTIFY capabilitiesChanged)
public:
 using QObject::QObject;
 virtual QVariantMap capabilities() const=0;
 virtual void send(const QString &id,const QString &number,const QString &text,bool report)=0;
signals:
 void capabilitiesChanged();
 void incoming(const QVariantMap &message);
 void stateChanged(const QString &id,const QString &state,const QString &key,const QString &error);
};
class MobileSmsTransport final : public ISmsTransport {
 Q_OBJECT
public:
 explicit MobileSmsTransport(Mobile *mobile,QObject *parent=nullptr,bool receiveMessages=true);
 QVariantMap capabilities() const override {return m_caps;}
 void send(const QString &,const QString &,const QString &,bool) override;
private slots:
 void discover();
 void scan();
 void added(const QDBusObjectPath &path,bool received,const QDBusMessage &message);
 void properties(const QString &iface,const QVariantMap &changed,const QStringList &invalidated,const QDBusMessage &message);
private:
 void read(const QString &path);
 void call(const QString &path,const QString &iface,const QString &method,const QVariantList &args,std::function<void(QDBusMessage)> done);
 bool m_receiveMessages;Mobile *m_mobile;QString m_path,m_owner;QVariantMap m_caps;QSet<QString> m_knownPaths;QMap<QString,QString> m_pending;QMap<QString,QVariantMap> m_reports;quint64 m_generation=0;bool m_scanning=false;
};
