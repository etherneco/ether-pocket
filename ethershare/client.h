#pragma once
#include <QObject>
#include <QVariantMap>
class ShareClient : public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
 Q_PROPERTY(QString hotspotPassword READ hotspotPassword NOTIFY changed)
 public:
 explicit ShareClient(QObject *parent=nullptr);
 QVariantMap state() const{return m_state;}
 bool busy() const{return m_pending||m_state.value("busy").toBool();}
 QString hotspotPassword() const{return m_password;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void start(const QString &method,const QString &interface,bool replaceWifi=false);
 Q_INVOKABLE void stop(const QString &method);
 Q_INVOKABLE void configure(const QVariantMap &values);
 Q_INVOKABLE void checkInternet();
 Q_INVOKABLE void startConcurrentHotspot(const QString &parent);
 Q_INVOKABLE void revealPassword();
 Q_INVOKABLE void renameClient(const QString &mac,const QString &name);
 signals:void changed();void notice(const QString &title,const QString &message);
 private slots:void update(const QString &json);void backendNotice(const QString &,const QString &);
 private:void call(const QString &,const QVariantList &args={});
 QVariantMap m_state;bool m_pending=false;QString m_password;
};
