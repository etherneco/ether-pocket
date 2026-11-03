#pragma once
#include <QObject>
#include <QVariantMap>
#include <QProcess>
#include <QTimer>
class AudioClient:public QObject {
 Q_OBJECT
 Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
 Q_PROPERTY(QString message READ message NOTIFY changed)
 Q_PROPERTY(bool busy READ busy NOTIFY changed)
 Q_PROPERTY(double level READ level NOTIFY changed)
 Q_PROPERTY(bool sampleAvailable READ sampleAvailable NOTIFY changed)
public:
 explicit AudioClient(QObject *parent=nullptr);
 ~AudioClient();
 QVariantMap state()const{return m_state;}
 QString message()const{return m_message;}
 bool busy()const{return m_pending>0||m_state.value("busy").toBool();}
 double level()const{return m_level;}
 bool sampleAvailable()const{return m_sample;}
 Q_INVOKABLE void refresh();
 Q_INVOKABLE void command(const QString&,const QString&,const QVariantMap& data={});
 Q_INVOKABLE void recordTest();
 Q_INVOKABLE void playSample();
 Q_INVOKABLE void deleteSample();
signals:void changed();void notice(const QString&,const QString&);
private slots:void update(const QString&);void event(const QString&,const QString&);
private:
 void call(const QString&,const QVariantList& args={});
 QVariantMap m_state;QString m_message;int m_pending=0;double m_level=0;bool m_sample=false;
 QProcess m_recorder,m_player;QByteArray m_pcm;QTimer m_deleteTimer;
};
