#pragma once
#include <QObject>
#include <QVariantMap>
class UpdateClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QVariantMap plan READ plan NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
public:
 explicit UpdateClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QVariantMap plan()const{return m_plan;}
 QString message()const{return m_message;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void check();
 Q_INVOKABLE void saveToken(QString);
 Q_INVOKABLE void removeToken();
 Q_INVOKABLE void download(const QString&);
 Q_INVOKABLE void prepare(const QString&);
 Q_INVOKABLE void install();
 Q_INVOKABLE void cancel();
 Q_INVOKABLE void channel(const QString&,const QString&,bool);
signals:void changed();
private slots:void update(const QString&);void event(const QString&,const QString&);
private:
 void request(const QString&,const QVariantList& args={});
 QVariantMap m_state,m_plan;QString m_message,m_approval;
};
