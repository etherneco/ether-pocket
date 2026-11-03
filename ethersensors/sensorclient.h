#pragma once
#include <QObject>
#include <QVariantMap>
#include <QTimer>
class SensorClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QVariantMap management READ management NOTIFY changed)
 Q_PROPERTY(QVariantMap sample READ sample NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
public:
 explicit SensorClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QVariantMap management()const{return m_management;}
 QVariantMap sample()const{return m_sample;}
 QString message()const{return m_message;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void configure(const QVariantMap&);
 Q_INVOKABLE void review();
 Q_INVOKABLE void resolve(const QString&,bool);
 Q_INVOKABLE void revoke(const QString&);
 Q_INVOKABLE void test(const QString&);
 Q_INVOKABLE void stopTest();
 Q_INVOKABLE void diagnostics();
signals:void changed();
private slots:void update(const QString&);
private:
 void request(const QString&,const QVariantList& args={});
 QVariantMap m_state,m_management,m_sample;QString m_message,m_token;QTimer m_timer;int m_reads=0;
};
