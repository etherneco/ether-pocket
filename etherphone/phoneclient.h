#pragma once
#include <QObject>
#include <QVariantMap>
class PhoneClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
public:
 explicit PhoneClient(QObject *parent=nullptr);
 QVariantMap state()const{return m_state;}
 QString message()const{return m_message;}
 bool busy()const{return m_pending>0;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void command(const QString&,const QString& target={},const QVariantMap& data={});
 Q_INVOKABLE QString pasteNumber()const;
 Q_INVOKABLE void importVcard(const QString&);
 Q_INVOKABLE void exportFile(const QString&);
signals:
 void changed();void incoming();void openHistory();void notice(const QString&,const QString&);
private slots:
 void update(const QString&);void event(const QString&,const QString&);
private:
 void call(const QString&,const QVariantList& args={},const QString& exportKind={});
 QVariantMap m_state;QString m_message;int m_pending=0;
};
