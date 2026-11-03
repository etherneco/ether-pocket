#pragma once
#include "agent.h"
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QMap>
#include <QSet>
#include <QSettings>
#include <QVariantList>
#include <functional>
using Interfaces=QMap<QString,QVariantMap>;
using Objects=QMap<QDBusObjectPath,Interfaces>;
Q_DECLARE_METATYPE(Interfaces)
Q_DECLARE_METATYPE(Objects)
class Bluetooth : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList adapters READ adapters NOTIFY changed)
    Q_PROPERTY(QVariantList devices READ devices NOTIFY changed)
    Q_PROPERTY(QString adapter MEMBER selected NOTIFY changed)
    Q_PROPERTY(QString error MEMBER error NOTIFY changed)
    Q_PROPERTY(QVariantMap pairing READ pairing NOTIFY pairingChanged)
    Q_PROPERTY(QVariantMap diagnosis MEMBER diagnosis NOTIFY diagnosisChanged)
    Q_PROPERTY(bool diagnosing MEMBER diagnosing NOTIFY diagnosisChanged)
    Q_PROPERTY(QVariantList gatt MEMBER gatt NOTIFY changed)
    Q_PROPERTY(bool recoveryAvailable READ recoveryAvailable CONSTANT)
    Q_PROPERTY(bool notifications READ notifications WRITE setNotifications NOTIFY changed)
public:
    explicit Bluetooth(QObject *parent=nullptr,bool sendNotifications=true);
    ~Bluetooth();
    QVariantList adapters() const;
    QVariantList devices() const;
    QVariantMap pairing() const {return agent.prompt;}
    bool recoveryAvailable() const;
    bool notifications() const {return settings.value("notifications",true).toBool();}
    void setNotifications(bool enabled){settings.setValue("notifications",enabled);emit changed();}
    Q_INVOKABLE void selectAdapter(const QString &path);
    Q_INVOKABLE void power(bool enabled);
    Q_INVOKABLE void scan(bool enabled);
    Q_INVOKABLE void discoverable(bool enabled);
    Q_INVOKABLE void action(const QString &path,const QString &operation,const QString &value={});
    Q_INVOKABLE void answer(bool accept,const QString &value={}) {agent.answer(accept,value);}
    Q_INVOKABLE void diagnose();
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void inspectGatt(const QString &device);
    Q_INVOKABLE void readGatt(const QString &path);
    Q_INVOKABLE void notifyGatt(const QString &path,bool enabled);
    Q_INVOKABLE void recover(const QString &action);
signals:
    void changed();
    void pairingChanged();
    void diagnosisChanged();
private slots:
    void added(const QDBusObjectPath &,const Interfaces &);
    void removed(const QDBusObjectPath &,const QStringList &);
    void properties(const QString &,const QVariantMap &,const QStringList &,const QDBusMessage &);
private:
    void call(const QString &,const QString &,const QString &,const QVariantList &args={},std::function<void(bool)> done={});
    void set(const QString &,const QString &,const QString &,const QVariant &);
    void update(const QString &,const QString &,const QVariantMap &);
    void retry(const QString &);
    bool powered(const QString &) const;
    void registerAgent();
    void notify(const QString &summary,const QString &body);
    QDBusConnection bus=QDBusConnection::systemBus();
    Objects objects;
    Agent agent;
    QSettings settings;
    QTimer scanTimeout;
    QString selected,error,scanOwner;
    QMap<QString,QString> transient;
    QMap<QString,QString> deviceErrors;
    QMap<QString,int> attempts;
    QMap<QString,QTimer*> retries;
    QSet<QString> manual, busy;
    QVariantMap diagnosis;
    QVariantList gatt;
    bool diagnosing=false, refreshing=false;
    bool notificationsAllowed=true;
    quint64 generation=0;
};
