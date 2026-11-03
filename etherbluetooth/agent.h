#pragma once
#include <QObject>
#include <QDBusContext>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QTimer>
#include <QVariantMap>
class Agent : public QObject, protected QDBusContext {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.bluez.Agent1")
public:
    explicit Agent(QObject *parent=nullptr);
    void answer(bool accept, const QString &value);
    QVariantMap prompt;
signals:
    void changed();
public slots:
    void Release();
    QString RequestPinCode(const QDBusObjectPath &device);
    uint RequestPasskey(const QDBusObjectPath &device);
    void DisplayPinCode(const QDBusObjectPath &device, const QString &pin);
    void DisplayPasskey(const QDBusObjectPath &device, uint key, ushort entered);
    void RequestConfirmation(const QDBusObjectPath &device, uint key);
    void RequestAuthorization(const QDBusObjectPath &device);
    void AuthorizeService(const QDBusObjectPath &device, const QString &uuid);
    void Cancel();
private:
    void request(const QDBusObjectPath &, const QString &, const QString &value={});
    bool allowed();
    QDBusMessage pending;
    QTimer timeout;
};
