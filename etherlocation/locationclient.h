#pragma once
#include <QObject>
#include <QVariantMap>
#include <QTimer>
class LocationClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QVariantMap management READ management NOTIFY changed)
 Q_PROPERTY(QVariantMap position READ position NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
public:
 explicit LocationClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QVariantMap management()const{return m_management;}
 QVariantMap position()const{return m_position;}
 QString message()const{return m_message;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void configure(const QVariantMap&);
 Q_INVOKABLE void review();
 Q_INVOKABLE void resolve(const QString&,const QString&,const QString&,bool);
 Q_INVOKABLE void revoke(const QString&,const QString&);
 Q_INVOKABLE void testGnss();
 Q_INVOKABLE void requestPermission(bool precise);
 Q_INVOKABLE void startUpdates(bool precise);
 Q_INVOKABLE void stopUpdates();
 Q_INVOKABLE void historyExport(const QString&);
 Q_INVOKABLE void deleteHistory(const QString&);
 Q_INVOKABLE void diagnostics(bool);
 Q_INVOKABLE void zone(const QString&,const QVariantMap&);
 Q_INVOKABLE void deleteZone(const QString&);
 Q_INVOKABLE void manual(double,double);
 Q_INVOKABLE void mapHistory(bool);
signals:void changed();
private slots:void update(const QString&);
private:
 void request(const QString&,const QVariantList& args={});
 QVariantMap m_state,m_management,m_position;QString m_message,m_token;QTimer m_timer;
};
